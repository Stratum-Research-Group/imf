"""
IMF Triton Fused Poincaré Gyro-Midpoint & Fréchet Mean Kernel
============================================================
Computes the exact geodesic midpoint m(u, v) between two points u, v in the Poincaré ball:
    m(u, v) = u \oplus ( 0.5 \otimes (-u \oplus v) )

where scalar gyro-multiplication by r = 0.5 is:
    r \otimes w = tanh( r * artanh(||w||) ) * (w / ||w||)

Computes the Riemannian center of mass / Fréchet mean for token clustering
and hyperbolic attention pooling directly in GPU register SRAM.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_poincare_midpoint_kernel(
    U_ptr,          # [B, D] First point in Poincare ball
    V_ptr,          # [B, D] Second point in Poincare ball
    Out_ptr,        # [B, D] Geodesic midpoint in Poincare ball
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

    # Accumulate ||u||^2, ||v||^2, <u, v>
    norm_u_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    norm_v_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    dot_uv = tl.zeros([BLOCK_B], dtype=tl.float32)

    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        u_ptrs = U_ptr + (offs_b[:, None] * stride_ub + curr_d[None, :] * stride_ud)
        v_ptrs = V_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)

        u_val = tl.load(u_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        v_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        norm_u_sq += tl.sum(u_val * u_val, axis=1)
        norm_v_sq += tl.sum(v_val * v_val, axis=1)
        dot_uv += tl.sum(u_val * v_val, axis=1)

    alpha_u = tl.maximum(1.0 - norm_u_sq, eps)
    denom_add = tl.maximum(1.0 + 2.0 * dot_uv + norm_u_sq * norm_v_sq, eps)

    # Coeffs for delta = -u \oplus v
    c_u = (1.0 + 2.0 * dot_uv + norm_v_sq) / denom_add
    c_v = alpha_u / denom_add

    # Pass 2: compute ||delta||^2
    norm_delta_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        u_ptrs = U_ptr + (offs_b[:, None] * stride_ub + curr_d[None, :] * stride_ud)
        v_ptrs = V_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)

        u_val = tl.load(u_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        v_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        delta = -c_u[:, None] * u_val + c_v[:, None] * v_val
        norm_delta_sq += tl.sum(delta * delta, axis=1)

    norm_delta = tl.sqrt(tl.maximum(norm_delta_sq, 0.0))
    safe_norm = tl.minimum(norm_delta, 1.0 - eps)

    # artanh(||delta||)
    artanh_val = 0.5 * tl.log((1.0 + safe_norm) / tl.maximum(1.0 - safe_norm, eps))
    # 0.5 * artanh(||delta||)
    half_artanh = 0.5 * artanh_val
    # tanh(half_artanh) = (exp(2*x) - 1) / (exp(2*x) + 1) where 2x = artanh(||delta||)
    # Using identity: tanh(0.5 * artanh(z)) = z / (1 + sqrt(1 - z^2))
    sqrt_1_minus_z2 = tl.sqrt(tl.maximum(1.0 - safe_norm * safe_norm, eps))
    tanh_half = safe_norm / (1.0 + sqrt_1_minus_z2)

    # w = 0.5 \otimes delta = tanh_half * (delta / ||delta||)
    scale_w = tl.where(norm_delta > eps, tanh_half / norm_delta, 0.0)
    norm_w_sq = tanh_half * tanh_half

    # Pass 3: compute <u, w>
    dot_uw = tl.zeros([BLOCK_B], dtype=tl.float32)
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        u_ptrs = U_ptr + (offs_b[:, None] * stride_ub + curr_d[None, :] * stride_ud)
        v_ptrs = V_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)

        u_val = tl.load(u_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        v_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        delta = -c_u[:, None] * u_val + c_v[:, None] * v_val
        w_val = scale_w[:, None] * delta
        dot_uw += tl.sum(u_val * w_val, axis=1)

    # Final midpoint: u \oplus w
    denom_mid = tl.maximum(1.0 + 2.0 * dot_uw + norm_u_sq * norm_w_sq, eps)
    c_u_final = (1.0 + 2.0 * dot_uw + norm_w_sq) / denom_mid
    c_w_final = alpha_u / denom_mid

    # Pass 4: write out u \oplus w
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_curr_d = curr_d < D

        u_ptrs = U_ptr + (offs_b[:, None] * stride_ub + curr_d[None, :] * stride_ud)
        v_ptrs = V_ptr + (offs_b[:, None] * stride_vb + curr_d[None, :] * stride_vd)

        u_val = tl.load(u_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)
        v_val = tl.load(v_ptrs, mask=mask_b[:, None] & mask_curr_d[None, :], other=0.0).to(tl.float32)

        delta = -c_u[:, None] * u_val + c_v[:, None] * v_val
        w_val = scale_w[:, None] * delta
        midpoint = c_u_final[:, None] * u_val + c_w_final[:, None] * w_val

        out_ptrs = Out_ptr + (offs_b[:, None] * stride_ob + curr_d[None, :] * stride_od)
        tl.store(out_ptrs, midpoint.to(tl.float16), mask=mask_b[:, None] & mask_curr_d[None, :])


def triton_poincare_midpoint(U: torch.Tensor, V: torch.Tensor, eps: float = 1e-5) -> torch.Tensor:
    """
    U: [B, D] Point 1 in Poincare ball
    V: [B, D] Point 2 in Poincare ball
    Returns: [B, D] Geodesic midpoint in Poincare ball
    """
    assert U.is_cuda and V.is_cuda
    B, D = U.shape
    Out = torch.empty_like(U)

    BLOCK_B = 64
    BLOCK_D = min(128, triton.next_power_of_2(D))
    grid = (triton.cdiv(B, BLOCK_B),)

    _fused_poincare_midpoint_kernel[grid](
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


def benchmark_poincare_midpoint():
    print("=" * 80)
    print("  IMF TRITON FUSED POINCARÉ GEODESIC MIDPOINT BENCHMARK")
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

    V = torch.randn((B, D), device=device, dtype=torch.float16)
    V = V / (V.norm(dim=-1, keepdim=True) + 1e-4) * 0.85

    # Warmup
    for _ in range(10):
        _ = triton_poincare_midpoint(U, V)
    torch.cuda.synchronize()

    # PyTorch Reference Verification
    def torch_midpoint_ref(u, v, eps=1e-5):
        u_f = u.float()
        v_f = v.float()
        u_sq = torch.sum(u_f * u_f, dim=-1, keepdim=True)
        v_sq = torch.sum(v_f * v_f, dim=-1, keepdim=True)
        dot_uv = torch.sum(u_f * v_f, dim=-1, keepdim=True)

        alpha_u = torch.clamp(1.0 - u_sq, min=eps)
        denom_add = torch.clamp(1.0 + 2.0 * dot_uv + u_sq * v_sq, min=eps)

        c_u = (1.0 + 2.0 * dot_uv + v_sq) / denom_add
        c_v = alpha_u / denom_add
        delta = -c_u * u_f + c_v * v_f

        norm_delta = torch.norm(delta, dim=-1, keepdim=True)
        safe_norm = torch.clamp(norm_delta, max=1.0 - eps)

        sqrt_1_minus_z2 = torch.sqrt(torch.clamp(1.0 - safe_norm * safe_norm, min=eps))
        tanh_half = safe_norm / (1.0 + sqrt_1_minus_z2)
        w = torch.where(norm_delta > eps, tanh_half * (delta / norm_delta), torch.zeros_like(delta))

        w_sq = torch.sum(w * w, dim=-1, keepdim=True)
        dot_uw = torch.sum(u_f * w, dim=-1, keepdim=True)

        denom_mid = torch.clamp(1.0 + 2.0 * dot_uw + u_sq * w_sq, min=eps)
        c_u_fin = (1.0 + 2.0 * dot_uw + w_sq) / denom_mid
        c_w_fin = alpha_u / denom_mid

        return (c_u_fin * u_f + c_w_fin * w).half()

    ref_out = torch_midpoint_ref(U, V)
    tri_out = triton_poincare_midpoint(U, V)

    max_diff = torch.max(torch.abs(ref_out - tri_out)).item()
    mean_diff = torch.mean(torch.abs(ref_out - tri_out)).item()
    print(f"[*] Numerical Fidelity: Max Diff = {max_diff:.4e}, Mean Diff = {mean_diff:.4e}")
    assert max_diff < 0.05, f"Numerical error too high: {max_diff}"

    # Latency Benchmark
    iters = 100
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_midpoint(U, V)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start) / iters

    throughput = B / elapsed / 1e6
    print(f"[✓] Execution Latency: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] Geodesic Midpoint Throughput: {throughput:.2f} Million midpoints/sec")
    print("=" * 80)


if __name__ == "__main__":
    benchmark_poincare_midpoint()
