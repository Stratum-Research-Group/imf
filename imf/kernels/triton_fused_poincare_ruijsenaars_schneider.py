"""
Triton Fused Kernel: Poincaré Ruijsenaars-Schneider Relativistic Soliton Flow (SM 8.9)
Cycle 239 Capstone: Relativistic Calogero-Moser Generalization, Hyperbolic Velocity Saturation,
and Poincaré Hyperbolic Confinement.

Physical Model:
Ruijsenaars-Schneider relativistic Hamiltonian:
    H = \sum_j \cosh(p_j) \prod_{k \neq j} \left( 1 - \frac{\sinh^2(\lambda)}{\sinh^2(\mu (q_j - q_k))} \right)^{1/2}

Equations of motion under local spatial discretization / nearest-neighbor projection:
    \dot{q}_j = \sinh(p_j) V_j(q)
    \dot{p}_j = - \cosh(p_j) \partial_{q_j} V_j(q)

Projected onto Poincaré disk manifold g(u) = 4 / (1 - u^2)^2.
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_ruijsenaars_schneider_kernel(
    q_ptr, p_ptr,
    out_q_ptr, out_p_ptr,
    dt, lambda_param, mu, n_particles,
    BLOCK_N: tl.constexpr
):
    pid = tl.program_id(axis=0)
    offsets = pid * BLOCK_N + tl.arange(0, BLOCK_N)
    mask = offsets < n_particles

    idx_prev = (offsets - 1 + n_particles) % n_particles
    idx_next = (offsets + 1) % n_particles

    q = tl.load(q_ptr + offsets, mask=mask, other=0.0)
    p = tl.load(p_ptr + offsets, mask=mask, other=0.0)
    q_prev = tl.load(q_ptr + idx_prev, mask=mask, other=0.0)
    q_next = tl.load(q_ptr + idx_next, mask=mask, other=0.0)

    # Relativistic velocity factors
    # cosh(p) = 0.5 * (exp(p) + exp(-p)), sinh(p) = 0.5 * (exp(p) - exp(-p))
    p_clamped = tl.maximum(tl.minimum(p, 4.0), -4.0)
    exp_p = tl.exp(p_clamped)
    exp_neg_p = tl.exp(-p_clamped)
    cosh_p = 0.5 * (exp_p + exp_neg_p)
    sinh_p = 0.5 * (exp_p - exp_neg_p)

    # Local Ruijsenaars-Schneider potential factor V_j(q)
    diff_l = tl.maximum(tl.abs(q - q_prev), 0.05)
    diff_r = tl.maximum(tl.abs(q_next - q), 0.05)

    v_left = 1.0 - (lambda_param * lambda_param) / (diff_l * diff_l)
    v_right = 1.0 - (lambda_param * lambda_param) / (diff_r * diff_r)
    v_left = tl.maximum(v_left, 0.01)
    v_right = tl.maximum(v_right, 0.01)

    v_j = tl.sqrt(v_left * v_right)

    # Force gradient ~ cosh(p) * d(V_j)/dq
    dv_dq = (1.0 / diff_r - 1.0 / diff_l) * 0.1
    force = - cosh_p * dv_dq

    # Hyperbolic metric conformal factor g(u) = 4 / (1 - u^2)^2
    q_sq = q * q
    safe_denom = tl.maximum(1.0 - q_sq, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_p = p + effective_dt * force
    out_q = q + effective_dt * (sinh_p * v_j)

    # Project to Poincare interval (-0.98, 0.98)
    out_q = tl.maximum(tl.minimum(out_q, 0.98), -0.98)

    tl.store(out_q_ptr + offsets, out_q, mask=mask)
    tl.store(out_p_ptr + offsets, out_p, mask=mask)

def poincare_ruijsenaars_schneider_triton(q: torch.Tensor, p: torch.Tensor, dt: float = 0.001, lambda_param: float = 0.05, mu: float = 1.0):
    assert q.is_cuda and p.is_cuda
    n = q.numel()
    out_q = torch.empty_like(q)
    out_p = torch.empty_like(p)
    BLOCK_N = 1024
    grid = (triton.cdiv(n, BLOCK_N),)
    _poincare_ruijsenaars_schneider_kernel[grid](
        q, p, out_q, out_p,
        dt, lambda_param, mu, n,
        BLOCK_N=BLOCK_N
    )
    return out_q, out_p

def poincare_ruijsenaars_schneider_pytorch(q: torch.Tensor, p: torch.Tensor, dt: float = 0.001, lambda_param: float = 0.05, mu: float = 1.0):
    q_prev = torch.roll(q, shifts=1, dims=0)
    q_next = torch.roll(q, shifts=-1, dims=0)

    p_clamped = torch.clamp(p, -4.0, 4.0)
    cosh_p = torch.cosh(p_clamped)
    sinh_p = torch.sinh(p_clamped)

    diff_l = torch.clamp(torch.abs(q - q_prev), min=0.05)
    diff_r = torch.clamp(torch.abs(q_next - q), min=0.05)

    v_left = torch.clamp(1.0 - (lambda_param ** 2) / (diff_l ** 2), min=0.01)
    v_right = torch.clamp(1.0 - (lambda_param ** 2) / (diff_r ** 2), min=0.01)
    v_j = torch.sqrt(v_left * v_right)

    dv_dq = (1.0 / diff_r - 1.0 / diff_l) * 0.1
    force = - cosh_p * dv_dq

    q_sq = q * q
    safe_denom = torch.clamp(1.0 - q_sq, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_p = p + effective_dt * force
    out_q = q + effective_dt * (sinh_p * v_j)
    return torch.clamp(out_q, -0.98, 0.98), out_p

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ RUIJSENAARS-SCHNEIDER FLOW (RTX 5060 Ti SM 8.9)")
    print("=" * 70)

    n = 131072
    q = torch.randn(n, device=device, dtype=torch.float32) * 0.3
    p = torch.randn(n, device=device, dtype=torch.float32) * 0.1

    for _ in range(20):
        out_q_tri, out_p_tri = poincare_ruijsenaars_schneider_triton(q, p)
        out_q_pt, out_p_pt = poincare_ruijsenaars_schneider_pytorch(q, p)
    torch.cuda.synchronize()

    max_err_q = (out_q_tri - out_q_pt).abs().max().item()
    max_err_p = (out_p_tri - out_p_pt).abs().max().item()
    print(f"Max Absolute Error Q: {max_err_q:.2e}")
    print(f"Max Absolute Error P: {max_err_p:.2e}")
    assert max_err_q < 1e-4 and max_err_p < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_q_pt, out_p_pt = poincare_ruijsenaars_schneider_pytorch(q, p)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_q_tri, out_p_tri = poincare_ruijsenaars_schneider_triton(q, p)
    torch.cuda.synchronize()
    t_tri = (time.perf_counter() - t0) / iters * 1000.0

    speedup = t_pt / t_tri
    throughput = (n / (t_tri / 1000.0)) / 1e6

    print(f"PyTorch Time:  {t_pt * 1000.0:.2f} µs")
    print(f"Triton Time:   {t_tri * 1000.0:.2f} µs")
    print(f"Speedup:       {speedup:.2f}x")
    print(f"Throughput:    {throughput:.2f} M particles/s")
    print("=" * 70)

if __name__ == "__main__":
    benchmark()
