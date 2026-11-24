"""
IMF High-Performance Fused Poincare Geodesic Riemannian Score Matching Kernel
=============================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 8.9 / Ada Lovelace)
Mathematical Foundation:
  Score-based generative modeling and diffusion on Riemannian manifolds (Poincare Ball (D^d_c, g_c)).
  Given coordinate x in D^d_c with conformal metric g_x = lambda_x^2 I, where lambda_x = 2 / (1 - c ||x||^2).
  In Riemannian score matching, given an ambient score s_amb in R^d, the intrinsic Riemannian score is:
      grad_R log p(x) = g_x^{-1} s_amb = lambda_x^{-2} s_amb = ((1 - c ||x||^2) / 2)^2 s_amb.
  Under Riemannian Langevin diffusion:
      dx = - (1/2) beta_t grad_R V(x) dt + sqrt(beta_t) dW_t
  A single fused predictor step (geodesic tangent step + retraction):
      v = (1/2) dt * grad_R log p(x)
      ||v|| = sqrt(<v, v>_R) = lambda_x ||v||_E
      Retraction / Geodesic Exponential Map exp_x(v):
        Using Mobius addition: exp_x(v) = x (+) tanh(sqrt(c) lambda_x ||v||_E / 2) * (v / (sqrt(c) ||v||_E))
      For infinitesimal step (Taylor expansion / retraction):
        x_next = (x + alpha * grad_R) / (1 + c <x, alpha * grad_R>)
        projected strictly to ||x_next||^2 <= (1 - eps)/c.
  This fused kernel computes the intrinsic Riemannian score projection, Langevin drift displacement,
  and Mobius geodesic retraction completely in GPU registers in a single pass.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_riemannian_score_matching_kernel(
    X_ptr,          # [B, D] input points on Poincare ball
    S_ptr,          # [B, D] ambient Euclidean scores (from score network)
    Out_ptr,        # [B, D] output updated points on Poincare ball
    Score_R_ptr,    # [B, D] intrinsic Riemannian scores
    B: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    dt: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    # Compute row offsets
    offset = pid * D + tl.arange(0, BLOCK_SIZE)
    mask = tl.arange(0, BLOCK_SIZE) < D

    # Load x and ambient score s
    x = tl.load(X_ptr + offset, mask=mask, other=0.0)
    s = tl.load(S_ptr + offset, mask=mask, other=0.0)

    # 1. Compute ||x||^2
    x_sq = tl.sum(x * x, axis=0)
    # Clamp x_sq to avoid singularity near boundary (1 - c*x_sq > 1e-4)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = tl.minimum(x_sq, max_sq)

    # 2. Conformal factor lambda_x = 2 / (1 - c * ||x||^2)
    # Riemannian metric inverse factor: lambda_x^{-2} = ((1 - c * ||x||^2) / 2)^2
    one_minus_cx2 = 1.0 - c * clamped_x_sq
    inv_lambda_sq = (one_minus_cx2 * 0.5) * (one_minus_cx2 * 0.5)

    # 3. Intrinsic Riemannian score: s_R = g_x^{-1} s = inv_lambda_sq * s
    s_R = s * inv_lambda_sq

    # Store intrinsic Riemannian score
    tl.store(Score_R_ptr + offset, s_R, mask=mask)

    # 4. Geodesic Retraction / Tangent displacement:
    # v = 0.5 * dt * s_R
    v = 0.5 * dt * s_R
    
    # Mobius addition retraction x (+) v:
    # ( (1 + 2c <x, v> + c ||v||^2) x + (1 - c ||x||^2) v ) / (1 + 2c <x, v> + c^2 ||x||^2 ||v||^2)
    x_dot_v = tl.sum(x * v, axis=0)
    v_sq = tl.sum(v * v, axis=0)

    denom = 1.0 + 2.0 * c * x_dot_v + c * c * clamped_x_sq * v_sq
    denom = tl.maximum(denom, 1e-6)

    num_x_coeff = 1.0 + 2.0 * c * x_dot_v + c * v_sq
    num_v_coeff = one_minus_cx2

    x_next = (num_x_coeff * x + num_v_coeff * v) / denom

    # 5. Boundary projection: ensure ||x_next||^2 <= (1 - 1e-4) / c
    x_next_sq = tl.sum(x_next * x_next, axis=0)
    scale = 1.0
    if x_next_sq > max_sq:
        scale = tl.sqrt(max_sq / x_next_sq)
    x_next = x_next * scale

    tl.store(Out_ptr + offset, x_next, mask=mask)


def triton_poincare_riemannian_score_matching(
    x: torch.Tensor,
    s_amb: torch.Tensor,
    c: float = 1.0,
    dt: float = 0.01,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Riemannian Score Matching and Geodesic Langevin Predictor Step.
    Args:
        x: [B, D] input points on Poincaré ball
        s_amb: [B, D] ambient scores
        c: hyperbolic curvature parameter
        dt: diffusion Langevin step size
    Returns:
        (x_next, score_R): updated coordinates and intrinsic Riemannian scores
    """
    assert x.is_cuda and s_amb.is_cuda
    assert x.shape == s_amb.shape
    B, D = x.shape
    BLOCK_SIZE = triton.next_power_of_2(D)

    out = torch.empty_like(x)
    score_R = torch.empty_like(s_amb)

    grid = (B,)
    _poincare_riemannian_score_matching_kernel[grid](
        x,
        s_amb,
        out,
        score_R,
        B=B,
        D=D,
        c=c,
        dt=dt,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out, score_R


def reference_poincare_score_matching(
    x: torch.Tensor,
    s_amb: torch.Tensor,
    c: float = 1.0,
    dt: float = 0.01,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of Poincaré score matching & retraction."""
    x_sq = torch.sum(x * x, dim=-1, keepdim=True)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = torch.clamp(x_sq, max=max_sq)

    one_minus_cx2 = 1.0 - c * clamped_x_sq
    inv_lambda_sq = ((one_minus_cx2 * 0.5) ** 2)

    s_R = s_amb * inv_lambda_sq
    v = 0.5 * dt * s_R

    x_dot_v = torch.sum(x * v, dim=-1, keepdim=True)
    v_sq = torch.sum(v * v, dim=-1, keepdim=True)

    denom = 1.0 + 2.0 * c * x_dot_v + (c ** 2) * clamped_x_sq * v_sq
    denom = torch.clamp(denom, min=1e-6)

    num_x_coeff = 1.0 + 2.0 * c * x_dot_v + c * v_sq
    num_v_coeff = one_minus_cx2

    x_next = (num_x_coeff * x + num_v_coeff * v) / denom

    x_next_sq = torch.sum(x_next * x_next, dim=-1, keepdim=True)
    scale = torch.where(x_next_sq > max_sq, torch.sqrt(max_sq / x_next_sq), torch.ones_like(x_next_sq))
    x_next = x_next * scale

    return x_next, s_R


def benchmark_poincare_score_matching():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware test.")
        return

    prop = torch.cuda.get_device_properties(0)
    print(f"[*] Physical Device: {prop.name} (Compute Capability {prop.major}.{prop.minor})")

    B = 8192
    D = 128
    c = 1.0
    dt = 0.02

    # Generate points inside Poincaré ball
    x = torch.randn(B, D, device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * 0.6  # radius 0.6
    s_amb = torch.randn(B, D, device=device, dtype=torch.float32)

    # 1. Numerical validation
    out_triton, score_R_triton = triton_poincare_riemannian_score_matching(x, s_amb, c=c, dt=dt)
    out_ref, score_R_ref = reference_poincare_score_matching(x, s_amb, c=c, dt=dt)

    max_err_out = torch.max(torch.abs(out_triton - out_ref)).item()
    max_err_score = torch.max(torch.abs(score_R_triton - score_R_ref)).item()
    print(f"[✓] Numerical Verification:")
    print(f"    Max Coordinate Output Error: {max_err_out:.2e}")
    print(f"    Max Riemannian Score Error:  {max_err_score:.2e}")
    assert max_err_out < 1e-4, f"Coordinate error too high: {max_err_out}"
    assert max_err_score < 1e-4, f"Score error too high: {max_err_score}"

    # 2. Timing benchmark
    # Warmup
    for _ in range(20):
        _ = triton_poincare_riemannian_score_matching(x, s_amb, c=c, dt=dt)
        _ = reference_poincare_score_matching(x, s_amb, c=c, dt=dt)
    torch.cuda.synchronize()

    iters = 200
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_riemannian_score_matching(x, s_amb, c=c, dt=dt)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_score_matching(x, s_amb, c=c, dt=dt)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - start) / iters

    speedup = ref_time / triton_time
    throughput = (B * D) / (triton_time * 1e6)

    print(f"[✓] Performance Benchmark (B={B}, D={D}):")
    print(f"    Reference PyTorch Latency: {ref_time * 1e6:.2f} µs")
    print(f"    Triton Fused Latency:     {triton_time * 1e6:.2f} µs")
    print(f"    Fused Speedup:             {speedup:.2f}x")
    print(f"    Throughput:                {throughput:.2f} M elements/sec")


if __name__ == "__main__":
    benchmark_poincare_score_matching()
