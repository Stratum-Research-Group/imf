"""
IMF High-Performance Fused Poincare Non-Linear Laplacian Eigenmaps Kernel
========================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 8.9 / Ada Lovelace)
Mathematical Foundation:
  Hyperbolic Laplacian Eigenmaps and spectral manifold embedding on (D^d_c, g_c).
  Given a sequence of token representations X in R^{B x D} in the Poincaré ball.
  1. Conformal metric factor:
     lambda_i = 2 / (1 - c ||x_i||^2).
  2. Pairwise hyperbolic geodesic distance:
     d_H^2(x_i, x_j) = (1/c) * arcosh( 1 + 2c ||x_i - x_j||^2 / ((1 - c ||x_i||^2)(1 - c ||x_j||^2)) )^2.
  3. Hyperbolic heat kernel affinity:
     W_{ij} = exp( - d_H^2(x_i, x_j) / (4 t) ) * sqrt(lambda_i * lambda_j).
  4. Degree normalization and Laplacian quadratic form:
     D_i = sum_j W_{ij}.
     Normalized affinity: S_{ij} = W_{ij} / sqrt(D_i * D_j).
  5. Power iteration / spectral embedding update:
     Given initial spectral projection vector v in R^B:
     v_{new} = S * v.
     Orthogonalization against constant trivial eigenvector and Rayleigh quotient energy evaluation:
     R(v) = v^T (I - S) v / ||v||^2.
  This fused kernel computes the row-wise hyperbolic affinities, evaluates row degrees D_i,
  and executes the normalized spectral operator step v_{new} completely in GPU thread registers.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_laplacian_eigenmaps_kernel(
    X_ptr,          # [B, D] input points on Poincaré ball
    V_ptr,          # [B] input spectral eigenvector candidate
    OutV_ptr,       # [B] updated spectral eigenvector S * v
    Deg_ptr,        # [B] row degree D_i
    B: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    t_scale: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    offset_i = pid * D + tl.arange(0, BLOCK_SIZE)
    mask = tl.arange(0, BLOCK_SIZE) < D

    xi = tl.load(X_ptr + offset_i, mask=mask, other=0.0)

    # Conformal factor for row i
    xi_sq = tl.sum(xi * xi, axis=0)
    max_sq = (1.0 - 1e-4) / c
    clamped_xi_sq = tl.minimum(xi_sq, max_sq)
    one_minus_c_xi2 = tl.maximum(1.0 - c * clamped_xi_sq, 1e-6)
    lambda_i = 2.0 / one_minus_c_xi2

    # Accumulate degree D_i and unnormalized spectral output
    deg_i = 0.0
    accum_v = 0.0

    # Loop over all columns j in B
    for j in range(B):
        offset_j = j * D + tl.arange(0, BLOCK_SIZE)
        xj = tl.load(X_ptr + offset_j, mask=mask, other=0.0)
        vj = tl.load(V_ptr + j)

        xj_sq = tl.sum(xj * xj, axis=0)
        clamped_xj_sq = tl.minimum(xj_sq, max_sq)
        one_minus_c_xj2 = tl.maximum(1.0 - c * clamped_xj_sq, 1e-6)
        lambda_j = 2.0 / one_minus_c_xj2

        # Geodesic distance calculation
        diff = xi - xj
        diff_sq = tl.sum(diff * diff, axis=0)
        denom_h = tl.maximum(one_minus_c_xi2 * one_minus_c_xj2, 1e-7)
        delta = 2.0 * c * diff_sq / denom_h

        u = 1.0 + delta
        arg = u + tl.sqrt(tl.maximum(u * u - 1.0, 0.0))
        dist_h = tl.log(tl.maximum(arg, 1.0))
        dist_h_sq = dist_h * dist_h

        # Heat kernel weight: W_{ij} = exp(-dist_h_sq / (4*t)) * sqrt(lambda_i * lambda_j)
        w_ij = tl.exp(-dist_h_sq / (4.0 * t_scale)) * tl.sqrt(lambda_i * lambda_j)
        deg_i += w_ij
        accum_v += w_ij * vj

    tl.store(Deg_ptr + pid, deg_i)

    # Normalized operator: (D_i)^{-1} * sum_j W_{ij} v_j
    norm_v = accum_v / tl.maximum(deg_i, 1e-6)
    tl.store(OutV_ptr + pid, norm_v)


def triton_poincare_non_linear_laplacian_eigenmaps(
    x: torch.Tensor,
    v: torch.Tensor,
    c: float = 1.0,
    t_scale: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Non-Linear Laplacian Eigenmaps Step.
    Args:
        x: [B, D] manifold coordinates in Poincaré ball
        v: [B] current spectral eigenvector estimate
        c: manifold curvature
        t_scale: heat kernel time scale
    Returns:
        (v_next, degrees)
    """
    assert x.is_cuda and v.is_cuda
    B, D = x.shape
    BLOCK_SIZE = triton.next_power_of_2(D)

    out_v = torch.empty_like(v)
    deg = torch.empty((B,), device=x.device, dtype=torch.float32)

    grid = (B,)
    _poincare_laplacian_eigenmaps_kernel[grid](
        x,
        v,
        out_v,
        deg,
        B=B,
        D=D,
        c=c,
        t_scale=t_scale,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out_v, deg


def reference_poincare_laplacian_eigenmaps(
    x: torch.Tensor,
    v: torch.Tensor,
    c: float = 1.0,
    t_scale: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of Hyperbolic Laplacian Eigenmaps."""
    B, D = x.shape

    x_sq = torch.sum(x * x, dim=-1)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = torch.clamp(x_sq, max=max_sq)
    one_minus_cx2 = torch.clamp(1.0 - c * clamped_x_sq, min=1e-6)
    lambda_x = 2.0 / one_minus_cx2

    # Pairwise differences
    x_i = x.unsqueeze(1) # [B, 1, D]
    x_j = x.unsqueeze(0) # [1, B, D]
    diff = x_i - x_j
    diff_sq = torch.sum(diff * diff, dim=-1) # [B, B]

    lam_i = one_minus_cx2.unsqueeze(1)
    lam_j = one_minus_cx2.unsqueeze(0)
    denom_h = torch.clamp(lam_i * lam_j, min=1e-7)

    delta = 2.0 * c * diff_sq / denom_h
    u = 1.0 + delta
    arg = u + torch.sqrt(torch.clamp(u * u - 1.0, min=0.0))
    dist_h = torch.log(torch.clamp(arg, min=1.0))
    dist_h_sq = dist_h * dist_h

    conf_scale = torch.sqrt(lambda_x.unsqueeze(1) * lambda_x.unsqueeze(0))
    w_mat = torch.exp(-dist_h_sq / (4.0 * t_scale)) * conf_scale

    deg = torch.sum(w_mat, dim=-1)
    norm_w = w_mat / torch.clamp(deg.unsqueeze(-1), min=1e-6)
    out_v = torch.matmul(norm_w, v)

    return out_v, deg


def benchmark_laplacian_eigenmaps():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping.")
        return

    prop = torch.cuda.get_device_properties(0)
    print(f"[*] Physical Device: {prop.name} (Compute Capability {prop.major}.{prop.minor})")

    B = 2048
    D = 128
    c = 1.0
    t_scale = 1.0

    x = torch.randn(B, D, device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * 0.65
    v = torch.randn(B, device=device, dtype=torch.float32)
    v = v / torch.norm(v)

    # 1. Numerical verification
    v_tri, deg_tri = triton_poincare_non_linear_laplacian_eigenmaps(x, v, c=c, t_scale=t_scale)
    v_ref, deg_ref = reference_poincare_laplacian_eigenmaps(x, v, c=c, t_scale=t_scale)

    max_err_v = torch.max(torch.abs(v_tri - v_ref)).item()
    max_err_deg = torch.max(torch.abs(deg_tri - deg_ref)).item()

    rel_err_deg = (torch.abs(deg_tri - deg_ref) / torch.clamp(deg_ref, min=1.0)).max().item()
    print(f"[✓] Numerical Verification:")
    print(f"    Max Spectral Vector Error: {max_err_v:.2e}")
    print(f"    Max Degree Matrix Error:   {max_err_deg:.2e} (Relative: {rel_err_deg:.2e})")
    assert max_err_v < 1e-4, f"Vector error too high: {max_err_v}"
    assert rel_err_deg < 1e-4, f"Relative degree error too high: {rel_err_deg}"

    # 2. Timing benchmark
    for _ in range(10):
        _ = triton_poincare_non_linear_laplacian_eigenmaps(x, v, c=c, t_scale=t_scale)
        _ = reference_poincare_laplacian_eigenmaps(x, v, c=c, t_scale=t_scale)
    torch.cuda.synchronize()

    iters = 50
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_non_linear_laplacian_eigenmaps(x, v, c=c, t_scale=t_scale)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_laplacian_eigenmaps(x, v, c=c, t_scale=t_scale)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - start) / iters

    speedup = ref_time / triton_time
    throughput = (B * B) / (triton_time * 1e6)

    print(f"[✓] Performance Benchmark (B={B}, D={D}):")
    print(f"    Reference PyTorch Latency: {ref_time * 1e6:.2f} µs")
    print(f"    Triton Fused Latency:     {triton_time * 1e6:.2f} µs")
    print(f"    Fused Speedup:             {speedup:.2f}x")
    print(f"    Throughput:                {throughput:.2f} M pairwise affinity evaluations/sec")


if __name__ == "__main__":
    benchmark_laplacian_eigenmaps()
