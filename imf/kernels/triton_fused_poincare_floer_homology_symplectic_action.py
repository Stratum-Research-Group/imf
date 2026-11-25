"""
IMF High-Performance Fused Poincare Floer Homology Symplectic Action Kernel
==========================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 12.0 / Blackwell)
Mathematical Foundation:
  Hamiltonian Floer homology and symplectic action gradient trajectories on T*(D^d_c).
  Given a loop trajectory gamma(t) = (q(t), p(t)) in cotangent phase space over the Poincaré ball.
  The symplectic action functional is:
      A_H(gamma) = \int_0^1 ( p(t) . \dot{q}(t) - H(t, q(t), p(t)) ) dt.
  Gradient flow lines in loop space satisfy the Floer pseudoholomorphic trajectory equation:
      \partial_s u + J(u) ( \partial_t u - X_H(u) ) = 0,
  where J is the canonical compatible almost complex structure: J(dq) = dp, J(dp) = -dq.
  1. Conformal metric factor: lambda_q = 2 / (1 - c ||q||^2),  inv_lambda_sq = ((1 - c ||q||^2) / 2)^2.
  2. Symplectic form pairing: omega(v_1, v_2) = p_1 . q_2 - p_2 . q_1.
  3. Hamiltonian energy: H(q, p) = (1/2) inv_lambda_sq ||p||^2 + V(q).
  4. Floer gradient flow step:
     dq/ds = \dot{q} - \partial_p H(q, p) = \dot{q} - inv_lambda_sq * p.
     dp/ds = \dot{p} + \partial_q H(q, p) = \dot{p} + \nabla V(q) - c * inv_lambda_sq * ||p||^2 * q.
  5. Symplectic Action dissipation density:
     dA/ds = - ||\partial_s u||_J^2 = - ( ||dq/ds||^2 + inv_lambda_sq * ||dp/ds||^2 ).
  This fused Triton kernel evaluates the symplectic action density, Cauchy-Riemann Floer gradients,
  and updates phase trajectories directly in GPU registers in a single pass.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_floer_homology_kernel(
    Q_ptr,          # [B, D] position coordinates q in D^d_c
    P_ptr,          # [B, D] conjugate momentum p
    DotQ_ptr,       # [B, D] velocity \dot{q}
    DotP_ptr,       # [B, D] momentum rate \dot{p}
    OutQ_ptr,       # [B, D] evolved position q_{s+ds}
    OutP_ptr,       # [B, D] evolved momentum p_{s+ds}
    ActionDens_ptr, # [B] symplectic action gradient dissipation
    B: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    ds: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    offset = pid * D + tl.arange(0, BLOCK_SIZE)
    mask = tl.arange(0, BLOCK_SIZE) < D

    q = tl.load(Q_ptr + offset, mask=mask, other=0.0)
    p = tl.load(P_ptr + offset, mask=mask, other=0.0)
    dot_q = tl.load(DotQ_ptr + offset, mask=mask, other=0.0)
    dot_p = tl.load(DotP_ptr + offset, mask=mask, other=0.0)

    # 1. Conformal metric factor on Poincaré ball
    q_sq = tl.sum(q * q, axis=0)
    max_sq = (1.0 - 1e-4) / c
    clamped_q_sq = tl.minimum(q_sq, max_sq)
    one_minus_cq2 = tl.maximum(1.0 - c * clamped_q_sq, 1e-6)
    inv_lambda_sq = (one_minus_cq2 * 0.5) * (one_minus_cq2 * 0.5)

    p_sq = tl.sum(p * p, axis=0)

    # 2. Floer gradient flow components:
    # dq/ds = dot_q - inv_lambda_sq * p
    grad_s_q = dot_q - inv_lambda_sq * p

    # dp/ds = dot_p + q - c * inv_lambda_sq * p_sq * q (with harmonic V(q) = 0.5 ||q||^2)
    grad_s_p = dot_p + q - (c * inv_lambda_sq * p_sq) * q

    # 3. Action dissipation density: ||grad_s_q||^2 + inv_lambda_sq * ||grad_s_p||^2
    norm_gq_sq = tl.sum(grad_s_q * grad_s_q, axis=0)
    norm_gp_sq = tl.sum(grad_s_p * grad_s_p, axis=0)
    dissipation = norm_gq_sq + inv_lambda_sq * norm_gp_sq
    tl.store(ActionDens_ptr + pid, dissipation)

    # 4. Integrate trajectory along gradient flow line
    q_next = q - ds * grad_s_q
    p_next = p - ds * grad_s_p

    # Boundary projection for position in D^d_c
    q_next_sq = tl.sum(q_next * q_next, axis=0)
    scale = 1.0
    if q_next_sq > max_sq:
        scale = tl.sqrt(max_sq / q_next_sq)
    q_next = q_next * scale

    tl.store(OutQ_ptr + offset, q_next, mask=mask)
    tl.store(OutP_ptr + offset, p_next, mask=mask)


def triton_poincare_floer_homology(
    q: torch.Tensor,
    p: torch.Tensor,
    dot_q: torch.Tensor,
    dot_p: torch.Tensor,
    c: float = 1.0,
    ds: float = 0.01,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Floer Homology Symplectic Action Kernel.
    Args:
        q: [B, D] position coordinates in Poincaré ball
        p: [B, D] conjugate momentum vectors
        dot_q: [B, D] velocity \dot{q}
        dot_p: [B, D] momentum rate \dot{p}
        c: manifold curvature
        ds: flow step size
    Returns:
        (q_next, p_next, action_dissipation)
    """
    assert q.is_cuda and p.is_cuda and dot_q.is_cuda and dot_p.is_cuda
    B, D = q.shape
    BLOCK_SIZE = triton.next_power_of_2(D)

    out_q = torch.empty_like(q)
    out_p = torch.empty_like(p)
    action_dens = torch.empty((B,), device=q.device, dtype=torch.float32)

    grid = (B,)
    _poincare_floer_homology_kernel[grid](
        q,
        p,
        dot_q,
        dot_p,
        out_q,
        out_p,
        action_dens,
        B=B,
        D=D,
        c=c,
        ds=ds,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out_q, out_p, action_dens


def reference_poincare_floer(
    q: torch.Tensor,
    p: torch.Tensor,
    dot_q: torch.Tensor,
    dot_p: torch.Tensor,
    c: float = 1.0,
    ds: float = 0.01,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of Floer Symplectic Action Flow."""
    B, D = q.shape
    q_sq = torch.sum(q * q, dim=-1, keepdim=True)
    max_sq = (1.0 - 1e-4) / c
    clamped_q_sq = torch.clamp(q_sq, max=max_sq)
    one_minus_cq2 = torch.clamp(1.0 - c * clamped_q_sq, min=1e-6)
    inv_lambda_sq = ((one_minus_cq2 * 0.5) ** 2)

    p_sq = torch.sum(p * p, dim=-1, keepdim=True)

    grad_s_q = dot_q - inv_lambda_sq * p
    grad_s_p = dot_p + q - (c * inv_lambda_sq * p_sq) * q

    dissipation = torch.sum(grad_s_q * grad_s_q, dim=-1) + (inv_lambda_sq.squeeze(-1) * torch.sum(grad_s_p * grad_s_p, dim=-1))

    q_next = q - ds * grad_s_q
    p_next = p - ds * grad_s_p

    q_next_sq = torch.sum(q_next * q_next, dim=-1, keepdim=True)
    scale = torch.where(q_next_sq > max_sq, torch.sqrt(max_sq / q_next_sq), torch.ones_like(q_next_sq))
    q_next = q_next * scale

    return q_next, p_next, dissipation


def benchmark_floer():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping.")
        return

    prop = torch.cuda.get_device_properties(0)
    print(f"[*] Physical Device: {prop.name} (Compute Capability {prop.major}.{prop.minor})")

    B = 8192
    D = 128
    c = 1.0
    ds = 0.01

    q = torch.randn(B, D, device=device, dtype=torch.float32)
    q = q / (torch.norm(q, dim=-1, keepdim=True) + 1e-5) * 0.65
    p = torch.randn(B, D, device=device, dtype=torch.float32)
    dot_q = torch.randn(B, D, device=device, dtype=torch.float32)
    dot_p = torch.randn(B, D, device=device, dtype=torch.float32)

    # 1. Numerical verification
    q_tri, p_tri, diss_tri = triton_poincare_floer_homology(q, p, dot_q, dot_p, c=c, ds=ds)
    q_ref, p_ref, diss_ref = reference_poincare_floer(q, p, dot_q, dot_p, c=c, ds=ds)

    max_err_q = torch.max(torch.abs(q_tri - q_ref)).item()
    max_err_p = torch.max(torch.abs(p_tri - p_ref)).item()
    max_err_diss = torch.max(torch.abs(diss_tri - diss_ref)).item()

    print(f"[✓] Numerical Verification:")
    print(f"    Max Position Output Error:    {max_err_q:.2e}")
    print(f"    Max Momentum Output Error:    {max_err_p:.2e}")
    print(f"    Max Action Dissipation Error: {max_err_diss:.2e}")
    assert max_err_q < 1e-4, f"Q error too high: {max_err_q}"
    assert max_err_p < 1e-4, f"P error too high: {max_err_p}"
    assert max_err_diss < 1e-3, f"Dissipation error too high: {max_err_diss}"

    # 2. Timing benchmark
    for _ in range(20):
        _ = triton_poincare_floer_homology(q, p, dot_q, dot_p, c=c, ds=ds)
        _ = reference_poincare_floer(q, p, dot_q, dot_p, c=c, ds=ds)
    torch.cuda.synchronize()

    iters = 200
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_floer_homology(q, p, dot_q, dot_p, c=c, ds=ds)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_floer(q, p, dot_q, dot_p, c=c, ds=ds)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - start) / iters

    speedup = ref_time / triton_time
    throughput = (B * D * 2) / (triton_time * 1e6)

    print(f"[✓] Performance Benchmark (B={B}, D={D}):")
    print(f"    Reference PyTorch Latency: {ref_time * 1e6:.2f} µs")
    print(f"    Triton Fused Latency:     {triton_time * 1e6:.2f} µs")
    print(f"    Fused Speedup:             {speedup:.2f}x")
    print(f"    Throughput:                {throughput:.2f} M phase space elements/sec")


if __name__ == "__main__":
    benchmark_floer()
