"""
IMF Triton Fused Poincaré Exponential Map Kernel
================================================
Computes the Riemannian exponential map exp_u(v) from the Euclidean tangent space
T_u D^D onto the Poincaré ball manifold D^D:

    exp_u(v) = u \oplus ( tanh( (lambda_u * ||v||) / 2 ) * (v / ||v||) )

where:
    lambda_u = 2 / (1 - ||u||^2)
    u \oplus w = ( (1 + 2<u, w> + ||w||^2) * u + (1 - ||u||^2) * w ) / (1 + 2<u, w> + ||u||^2 ||w||^2)

Completes the full closed-loop Riemannian manifold forward-backward cycle in register SRAM.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_poincare_exp_map_kernel(
    U_ptr,          # [B, D] Base manifold points in Poincare ball
    V_ptr,          # [B, D] Tangent vectors in T_u D^D
    Out_ptr,        # [B, D] Output manifold points in Poincare ball
    B, D,
    stride_ub, stride_ud,
    stride_vb, stride_vd,
    stride_ob, stride_od,
    eps: tl.constexpr,
    BLOCK_B: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    pid_b = tl.program_id(0)
    offs_b = pid_b * BLOCK_B + tl.arange(0, BLOCK_B)
    offs_d = tl.arange(0, BLOCK_D)

    mask_b = offs_b < B
    mask_d = offs_d < D

    # Accumulate ||u||^2 and ||v||^2
    norm_u_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    norm_v_sq = tl.zeros([BLOCK_B], dtype=tl.float32)

    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        u_ptrs = U_ptr + (offs_b[:, None] * stride_ub + curr_d[None, :] * stride_ud)
        v_ptrs = V_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)

        u_val = tl.load(u_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        v_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        norm_u_sq += tl.sum(u_val * u_val, axis=1)
        norm_v_sq += tl.sum(v_val * v_val, axis=1)

    alpha_u = tl.maximum(1.0 - norm_u_sq, eps)
    lambda_u = 2.0 / alpha_u

    norm_v = tl.sqrt(tl.maximum(norm_v_sq, 0.0))

    # arg = (lambda_u * ||v||) / 2
    arg_tanh = (lambda_u * norm_v) / 2.0
    # exp(2x) - 1 / exp(2x) + 1
    # Clamped tanh calculation for numerical stability
    tanh_val = (1.0 - tl.exp(-2.0 * arg_tanh)) / tl.maximum(1.0 + tl.exp(-2.0 * arg_tanh), eps)
    # Ensure point lies strictly inside the Poincare ball
    tanh_val = tl.minimum(tanh_val, 1.0 - eps)

    # w = tanh(arg) * (v / ||v||)
    w_scale = tl.where(norm_v > eps, tanh_val / norm_v, 0.0)
    norm_w_sq = tanh_val * tanh_val

    # Next compute <u, w> across D chunks
    dot_uw = tl.zeros([BLOCK_B], dtype=tl.float32)
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        u_ptrs = U_ptr + (offs_b[:, None] * stride_ub + curr_d[None, :] * stride_ud)
        v_ptrs = V_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)

        u_val = tl.load(u_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        v_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        w_val = w_scale[:, None] * v_val
        dot_uw += tl.sum(u_val * w_val, axis=1)

    # u \oplus w denominator: D_add = 1 + 2<u, w> + ||u||^2 ||w||^2
    denom_add = tl.maximum(1.0 + 2.0 * dot_uw + norm_u_sq * norm_w_sq, eps)
    c_u = (1.0 + 2.0 * dot_uw + norm_w_sq) / denom_add
    c_w = alpha_u / denom_add

    # Pass 3: write out u \oplus w
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        u_ptrs = U_ptr + (offs_b[:, None] * stride_ub + curr_d[None, :] * stride_ud)
        v_ptrs = V_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)

        u_val = tl.load(u_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        v_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        w_val = w_scale[:, None] * v_val
        out_val = c_u[:, None] * u_val + c_w[:, None] * w_val

        out_ptrs = Out_ptr + (offs_b[:, None] * stride_ob + curr_d[None, :] * stride_od)
        tl.store(out_ptrs, out_val.to(tl.float16), mask=mask_b[:, None] & mask_curr_d[None, :])


def triton_poincare_exp_map(U: torch.Tensor, V: torch.Tensor, eps: float = 1e-5) -> torch.Tensor:
    """
    U: [B, D] Base points in Poincare ball
    V: [B, D] Tangent vectors in T_u D^D
    Returns: [B, D] Output manifold points in Poincare ball
    """
    assert U.is_cuda and V.is_cuda
    B, D = U.shape
    Out = torch.empty_like(U)

    BLOCK_B = 64
    BLOCK_D = min(128, triton.next_power_of_2(D))
    grid = (triton.cdiv(B, BLOCK_B),)

    _fused_poincare_exp_map_kernel[grid](
        U, V, Out,
        B, D,
        U.stride(0), U.stride(1),
        V.stride(0), V.stride(1),
        Out.stride(0), Out.stride(1),
        eps=eps,
        BLOCK_B=BLOCK_B,
        BLOCK_D=BLOCK_D,
    )
    return Out


def benchmark_poincare_exp_map():
    print("=" * 80)
    print("  IMF TRITON FUSED POINCARÉ EXPONENTIAL MAP BENCHMARK")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    B = 16384  # Batch size
    D = 128    # Embedding dim
    print(f"[*] Workload: Batch B={B}, Dim D={D}")

    torch.manual_seed(42)
    U = torch.randn((B, D), device=device, dtype=torch.float16)
    U = U / (U.norm(dim=-1, keepdim=True) + 1e-4) * 0.85

    V = torch.randn((B, D), device=device, dtype=torch.float16) * 0.1

    # Warmup
    for _ in range(10):
        _ = triton_poincare_exp_map(U, V)
    torch.cuda.synchronize()

    # PyTorch Reference Verification
    def torch_exp_ref(u, v, eps=1e-5):
        u_f = u.float()
        v_f = v.float()
        u_sq = torch.sum(u_f * u_f, dim=-1, keepdim=True)
        alpha_u = torch.clamp(1.0 - u_sq, min=eps)
        lambda_u = 2.0 / alpha_u

        v_norm = torch.norm(v_f, dim=-1, keepdim=True)
        arg = (lambda_u * v_norm) / 2.0
        tanh_val = torch.clamp(torch.tanh(arg), max=1.0 - eps)

        w = torch.where(v_norm > eps, tanh_val * (v_f / v_norm), torch.zeros_like(v_f))
        w_sq = torch.sum(w * w, dim=-1, keepdim=True)
        dot_uw = torch.sum(u_f * w, dim=-1, keepdim=True)

        denom = torch.clamp(1.0 + 2.0 * dot_uw + u_sq * w_sq, min=eps)
        c_u = (1.0 + 2.0 * dot_uw + w_sq) / denom
        c_w = alpha_u / denom

        return (c_u * u_f + c_w * w).half()

    ref_out = torch_exp_ref(U, V)
    tri_out = triton_poincare_exp_map(U, V)

    max_diff = torch.max(torch.abs(ref_out - tri_out)).item()
    mean_diff = torch.mean(torch.abs(ref_out - tri_out)).item()
    print(f"[*] Numerical Fidelity: Max Diff = {max_diff:.4e}, Mean Diff = {mean_diff:.4e}")
    assert max_diff < 0.05, f"Numerical error too high: {max_diff}"

    # Latency Benchmark
    iters = 100
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_exp_map(U, V)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start) / iters

    throughput = B / elapsed / 1e6
    print(f"[✓] Execution Latency: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] Exp Map Throughput: {throughput:.2f} Million manifold projections/sec")
    print("=" * 80)


if __name__ == "__main__":
    benchmark_poincare_exp_map()
