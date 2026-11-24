"""
Triton Fused Dual-Path Polytope LayerNorm & Residual Retraction Kernel
======================================================================
Computes fused RMSNorm with residual accumulation and Riemannian Poincaré retraction:
    x_res = x + residual
    norm_x = x_res / sqrt(mean(x_res^2) + eps) * weight
    y = norm_x * min(1.0, 0.999 / max(||norm_x||_2, 1e-6))
Executed in a single pass in GPU vector registers with zero intermediate DRAM round-trips.
"""

import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_polytope_layernorm_kernel(
    x_ptr,                 # [BATCH, DIM] fp16
    residual_ptr,          # [BATCH, DIM] fp16
    weight_ptr,            # [DIM] fp16 (gain parameter)
    out_ptr,               # [BATCH, DIM] fp16 (retracted output)
    stride_xb, stride_xd,
    stride_rb, stride_rd,
    stride_ob, stride_od,
    BATCH_SIZE,
    DIM: tl.constexpr,     # e.g. 512, 1024, or 2048
    BLOCK_SIZE: tl.constexpr,
    EPS: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= BATCH_SIZE:
        return

    offs_d = tl.arange(0, BLOCK_SIZE)
    mask_d = offs_d < DIM

    # 1. Load x and residual, compute x_res = x + res
    x_ptrs = x_ptr + pid * stride_xb + offs_d * stride_xd
    r_ptrs = residual_ptr + pid * stride_rb + offs_d * stride_rd

    x_val = tl.load(x_ptrs, mask=mask_d, other=0.0).to(tl.float32)
    r_val = tl.load(r_ptrs, mask=mask_d, other=0.0).to(tl.float32)
    x_res = x_val + r_val

    # 2. Compute RMSNorm variance: mean(x_res^2)
    var = tl.sum(x_res * x_res, axis=0) / DIM
    rsqrt_var = tl.math.rsqrt(var + EPS)

    # 3. Apply affine gain weight
    w_val = tl.load(weight_ptr + offs_d, mask=mask_d, other=1.0).to(tl.float32)
    norm_x = x_res * rsqrt_var * w_val

    # 4. Riemannian Poincaré Retraction: clamp norm to 0.999 boundary
    l2_sq = tl.sum(norm_x * norm_x, axis=0)
    l2_norm = tl.sqrt(l2_sq)
    inv_norm = tl.where(l2_norm > 0.999, 0.999 / tl.maximum(l2_norm, 1e-6), 1.0)
    y = norm_x * inv_norm

    # 5. Store result
    out_ptrs = out_ptr + pid * stride_ob + offs_d * stride_od
    tl.store(out_ptrs, y.to(tl.float16), mask=mask_d)


def triton_fused_polytope_layernorm(
    x: torch.Tensor,
    residual: torch.Tensor,
    weight: torch.Tensor,
    eps: float = 1e-6,
) -> torch.Tensor:
    """
    x, residual: [BATCH, DIM] fp16
    weight: [DIM] fp16
    Returns: [BATCH, DIM] fp16
    """
    assert x.is_cuda and residual.is_cuda and weight.is_cuda
    batch_size, dim = x.shape
    out = torch.empty_like(x)

    BLOCK_SIZE = triton.next_power_of_2(dim)
    grid = (batch_size,)

    _fused_polytope_layernorm_kernel[grid](
        x,
        residual,
        weight,
        out,
        x.stride(0), x.stride(1),
        residual.stride(0), residual.stride(1),
        out.stride(0), out.stride(1),
        batch_size,
        DIM=dim,
        BLOCK_SIZE=BLOCK_SIZE,
        EPS=eps,
    )
    return out


def benchmark_polytope_layernorm():
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    device = torch.device("cuda:0")
    batch_size = 32768  # 32k tokens in flight
    dim = 1024          # Transformer hidden dimension

    print(f"[*] Benchmarking Fused Polytope LayerNorm & Residual Retraction (B={batch_size:,}, D={dim})...")

    x = torch.randn(batch_size, dim, device=device, dtype=torch.float16)
    residual = torch.randn(batch_size, dim, device=device, dtype=torch.float16) * 0.5
    weight = torch.ones(dim, device=device, dtype=torch.float16)

    # Warmup
    for _ in range(5):
        _ = triton_fused_polytope_layernorm(x, residual, weight)
    torch.cuda.synchronize()

    # Timed run
    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out = triton_fused_polytope_layernorm(x, residual, weight)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - t0) / iters

    tok_sec = batch_size / elapsed
    bandwidth_gb_s = (x.nbytes + residual.nbytes + out.nbytes) / elapsed / 1e9

    print(f"[✓] Execution Time: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] Throughput: {tok_sec / 1e6:.2f} M tokens/sec ({tok_sec * dim / 1e9:.2f} B features/sec)")
    print(f"[✓] Effective Memory Bandwidth: {bandwidth_gb_s:.2f} GB/s")

    # PyTorch reference validation
    x_res = x.float() + residual.float()
    rms = x_res * torch.rsqrt(x_res.pow(2).mean(dim=-1, keepdim=True) + 1e-6) * weight.float()
    norm_rms = torch.norm(rms, p=2, dim=-1, keepdim=True)
    scale = torch.where(norm_rms > 0.999, 0.999 / torch.clamp(norm_rms, min=1e-6), torch.ones_like(norm_rms))
    ref_out = (rms * scale).half()

    max_err = (out - ref_out).abs().max().item()
    print(f"[✓] Max Absolute Difference vs PyTorch Analytical Ref: {max_err:.6e}")
    assert max_err < 1e-2, f"Numerical error too high: {max_err}"
    print("[✓] Correctness verification passed!")


if __name__ == "__main__":
    benchmark_polytope_layernorm()
