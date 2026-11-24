r"""
IMF Triton Fused Poincaré Gyro-MatMul Linear Projection Kernel (Full Dimension Fused)
======================================================================================
Hardware-accelerated Möbius matrix-vector multiplication (Gyro-MatMul) directly
on the Poincaré ball \mathbb{B}_c^D.
"""

import time
import torch
import triton
import triton.language as tl


@torch.no_grad()
def poincare_matmul_torch(
    x: torch.Tensor,        # [B, D_in]
    w: torch.Tensor,        # [D_out, D_in]
    eps: float = 1e-5,
) -> torch.Tensor:
    norm_x = torch.norm(x, dim=-1, keepdim=True).clamp(min=1e-7, max=1.0 - eps)
    artanh_x = torch.atanh(norm_x)
    v = artanh_x * (x / norm_x)

    u = torch.matmul(v, w.t()) # [B, D_out]

    norm_u = torch.norm(u, dim=-1, keepdim=True).clamp(min=1e-7)
    x_out = torch.tanh(norm_u) * (u / norm_u)
    return x_out


@triton.jit
def _poincare_matmul_full_kernel(
    X_ptr, W_ptr, Out_ptr,
    eps,
    B: tl.constexpr, D_in: tl.constexpr, D_out: tl.constexpr,
    BLOCK_M: tl.constexpr, BLOCK_IN: tl.constexpr, BLOCK_OUT: tl.constexpr,
):
    pid_m = tl.program_id(0)
    offs_m = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
    mask_m = offs_m < B

    offs_in = tl.arange(0, BLOCK_IN)
    mask_in = offs_in < D_in
    offs_out = tl.arange(0, BLOCK_OUT)
    mask_out = offs_out < D_out

    # 1. Load x: [BLOCK_M, BLOCK_IN]
    x_ptrs = X_ptr + tl.expand_dims(offs_m, 1) * D_in + tl.expand_dims(offs_in, 0)
    mask_min = tl.expand_dims(mask_m, 1) & tl.expand_dims(mask_in, 0)
    x = tl.load(x_ptrs, mask=mask_min, other=0.0)

    x_sq = tl.sum(tl.where(mask_min, x * x, 0.0), axis=1) # [BLOCK_M]
    norm_x = tl.sqrt(x_sq)
    norm_x_clamped = tl.minimum(tl.maximum(norm_x, 1e-7), 1.0 - eps)

    artanh_x = 0.5 * tl.log((1.0 + norm_x_clamped) / (1.0 - norm_x_clamped))
    scale_in = tl.expand_dims(artanh_x / norm_x_clamped, 1) # [BLOCK_M, 1]
    v = x * scale_in # [BLOCK_M, BLOCK_IN]

    # 2. Load full W: [BLOCK_OUT, BLOCK_IN]
    w_ptrs = W_ptr + tl.expand_dims(offs_out, 1) * D_in + tl.expand_dims(offs_in, 0)
    mask_win = tl.expand_dims(mask_out, 1) & tl.expand_dims(mask_in, 0)
    w = tl.load(w_ptrs, mask=mask_win, other=0.0)

    # 3. GEMM: u = v @ w.T -> [BLOCK_M, BLOCK_OUT]
    u = tl.dot(v, tl.trans(w))

    # 4. Row-wise norm of full u vector across ALL D_out dimensions!
    mask_mout = tl.expand_dims(mask_m, 1) & tl.expand_dims(mask_out, 0)
    u_sq = tl.sum(tl.where(mask_mout, u * u, 0.0), axis=1) # [BLOCK_M]
    norm_u = tl.sqrt(u_sq)
    norm_u_clamped = tl.maximum(norm_u, 1e-7)

    exp_2u = tl.exp(2.0 * norm_u_clamped)
    tanh_u = (exp_2u - 1.0) / (exp_2u + 1.0)
    scale_out = tl.expand_dims(tanh_u / norm_u_clamped, 1) # [BLOCK_M, 1]

    x_out = u * scale_out

    out_ptrs = Out_ptr + tl.expand_dims(offs_m, 1) * D_out + tl.expand_dims(offs_out, 0)
    tl.store(out_ptrs, x_out, mask=mask_mout)


def triton_fused_poincare_matmul(
    x: torch.Tensor,        # [B, D_in]
    w: torch.Tensor,        # [D_out, D_in]
    eps: float = 1e-5,
) -> torch.Tensor:
    B, D_in = x.shape
    D_out, _ = w.shape
    assert x.is_cuda and w.is_cuda, "Tensors must be on CUDA"

    x = x.contiguous()
    w = w.contiguous()
    out = torch.empty((B, D_out), device=x.device, dtype=torch.float32)

    BLOCK_M = 32
    BLOCK_IN = 1
    while BLOCK_IN < D_in:
        BLOCK_IN *= 2

    BLOCK_OUT = 1
    while BLOCK_OUT < D_out:
        BLOCK_OUT *= 2

    grid = (triton.cdiv(B, BLOCK_M),)

    _poincare_matmul_full_kernel[grid](
        x, w, out,
        eps=float(eps),
        B=B, D_in=D_in, D_out=D_out,
        BLOCK_M=BLOCK_M, BLOCK_IN=BLOCK_IN, BLOCK_OUT=BLOCK_OUT,
        num_warps=4,
    )

    return out


if __name__ == "__main__":
    print("=" * 80)
    print("IMF Triton Fused Poincaré Gyro-MatMul Linear Projection Benchmark (Block-M Fused)")
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print("=" * 80)

    torch.manual_seed(42)
    device = "cuda"

    B = 16384
    D_in = 128
    D_out = 128

    x = torch.randn((B, D_in), device=device, dtype=torch.float32)
    norm = torch.norm(x, dim=-1, keepdim=True).clamp(min=1e-5)
    x = (x / norm) * torch.rand((B, 1), device=device) * 0.85

    w = torch.randn((D_out, D_in), device=device, dtype=torch.float32) * 0.1

    # 1. Numerical Correctness
    print(f"1. Validating Numerical Equivalence against PyTorch Reference (B={B}, D_in={D_in}, D_out={D_out})...")
    out_ref = poincare_matmul_torch(x, w)
    out_tri = triton_fused_poincare_matmul(x, w)

    max_err = torch.max(torch.abs(out_ref - out_tri)).item()
    print(f"   Max Abs Error: {max_err:.2e}")
    assert max_err < 5e-4, f"Numerical divergence in Poincaré MatMul: {max_err}"
    print("   ✓ 100.0% Numerical Parity Confirmed.")

    # 2. Hardware Benchmarking
    print("\n2. Executing Workstation Hardware Benchmark (RTX 5060 Ti)...")
    warmup = 10
    iters = 50

    for _ in range(warmup):
        _ = poincare_matmul_torch(x, w)
        _ = triton_fused_poincare_matmul(x, w)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_matmul_torch(x, w)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_fused_poincare_matmul(x, w)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    tp_torch = B / t_torch
    tp_triton = B / t_triton
    speedup = t_torch / t_triton

    print(f"   PyTorch Baseline Latency: {t_torch*1e6:8.2f} us | Throughput: {tp_torch/1e6:6.2f} M tokens/s")
    print(f"   Triton Fused Latency:     {t_triton*1e6:8.2f} us | Throughput: {tp_triton/1e6:6.2f} M tokens/s")
    print(f"   Hardware Speedup:         {speedup:8.2f}x")
    print("=" * 80)
