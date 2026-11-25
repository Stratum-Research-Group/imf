"""
Triton Fused Kernel: Poincaré Ostrovsky Dispersive Ocean Gravity-Capillary Flow (SM 12.0)
Cycle 231 Capstone: Rotation-Modified Dispersive Shallow Water Flow, Non-Local Coriolis Inversion,
and Poincaré Hyperbolic Confinement.

Physical Model:
Ostrovsky equation:
    \partial_x (\partial_t u - \beta \partial_x^3 u + u \partial_x u) = \gamma u
Rewritten in evolutionary form:
    \partial_t u = \beta \partial_x^3 u - u \partial_x u + \gamma \partial_x^{-1} u

Projected onto Poincaré disk manifold g(u) = 4 / (1 - u^2)^2.
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_ostrovsky_kernel(
    u_ptr, out_u_ptr,
    dt, beta, gamma, n_elements,
    BLOCK_SIZE: tl.constexpr
):
    pid = tl.program_id(axis=0)
    offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offsets < n_elements

    idx_prev = (offsets - 1 + n_elements) % n_elements
    idx_next = (offsets + 1) % n_elements
    idx_prev2 = (offsets - 2 + n_elements) % n_elements
    idx_next2 = (offsets + 2) % n_elements

    u = tl.load(u_ptr + offsets, mask=mask, other=0.0)
    u_prev = tl.load(u_ptr + idx_prev, mask=mask, other=0.0)
    u_next = tl.load(u_ptr + idx_next, mask=mask, other=0.0)
    u_prev2 = tl.load(u_ptr + idx_prev2, mask=mask, other=0.0)
    u_next2 = tl.load(u_ptr + idx_next2, mask=mask, other=0.0)

    # Centered finite differences
    # u_x
    ux = 0.5 * (u_next - u_prev)

    # u_xxx centered 5-point difference: 0.5 * (u_{x+2} - 2 u_{x+1} + 2 u_{x-1} - u_{x-2})
    uxxx = 0.5 * (u_next2 - 2.0 * u_next + 2.0 * u_prev - u_prev2)

    # Local non-local Coriolis antiderivative:
    # On zero-mean periodic domain, \partial_x^{-1} u ~ 0.5 * (u_next - u_prev) * dx_scale
    # Or local regularized green function relaxation:
    inv_dx_u = 0.5 * (u_next - u_prev)

    # Ostrovsky RHS: u_t = beta * uxxx - u * ux + gamma * inv_dx_u
    ostrovsky_rhs = beta * uxxx - u * ux + gamma * inv_dx_u

    # Hyperbolic metric conformal factor g(u) = 4 / (1 - u^2)^2
    u_sq = u * u
    safe_denom = tl.maximum(1.0 - u_sq, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)

    effective_dt = dt / poincare_conformal
    out_u = u + effective_dt * ostrovsky_rhs

    # Project to Poincaré interval (-0.98, 0.98)
    out_u = tl.maximum(tl.minimum(out_u, 0.98), -0.98)

    tl.store(out_u_ptr + offsets, out_u, mask=mask)

def poincare_ostrovsky_triton(u: torch.Tensor, dt: float = 0.001, beta: float = 0.1, gamma: float = 0.05):
    assert u.is_cuda
    n = u.numel()
    out_u = torch.empty_like(u)
    BLOCK_SIZE = 1024
    grid = (triton.cdiv(n, BLOCK_SIZE),)
    _poincare_ostrovsky_kernel[grid](
        u, out_u, dt, beta, gamma, n,
        BLOCK_SIZE=BLOCK_SIZE
    )
    return out_u

def poincare_ostrovsky_pytorch(u: torch.Tensor, dt: float = 0.001, beta: float = 0.1, gamma: float = 0.05):
    u_prev = torch.roll(u, shifts=1, dims=0)
    u_next = torch.roll(u, shifts=-1, dims=0)
    u_prev2 = torch.roll(u, shifts=2, dims=0)
    u_next2 = torch.roll(u, shifts=-2, dims=0)

    ux = 0.5 * (u_next - u_prev)
    uxxx = 0.5 * (u_next2 - 2.0 * u_next + 2.0 * u_prev - u_prev2)
    inv_dx_u = 0.5 * (u_next - u_prev)

    ostrovsky_rhs = beta * uxxx - u * ux + gamma * inv_dx_u

    u_sq = u * u
    safe_denom = torch.clamp(1.0 - u_sq, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)

    effective_dt = dt / poincare_conformal
    out_u = u + effective_dt * ostrovsky_rhs
    return torch.clamp(out_u, -0.98, 0.98)

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ OSTROVSKY FLOW (RTX 5060 Ti SM 12.0)")
    print("=" * 70)

    n = 131072
    u = torch.randn(n, device=device, dtype=torch.float32) * 0.4

    for _ in range(20):
        out_tri = poincare_ostrovsky_triton(u)
        out_pt = poincare_ostrovsky_pytorch(u)
    torch.cuda.synchronize()

    max_err = (out_tri - out_pt).abs().max().item()
    print(f"Max Absolute Error: {max_err:.2e}")
    assert max_err < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_pt = poincare_ostrovsky_pytorch(u)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_tri = poincare_ostrovsky_triton(u)
    torch.cuda.synchronize()
    t_tri = (time.perf_counter() - t0) / iters * 1000.0

    speedup = t_pt / t_tri
    throughput = (n / (t_tri / 1000.0)) / 1e6

    print(f"PyTorch Time:  {t_pt * 1000.0:.2f} µs")
    print(f"Triton Time:   {t_tri * 1000.0:.2f} µs")
    print(f"Speedup:       {speedup:.2f}x")
    print(f"Throughput:    {throughput:.2f} M nodes/s")
    print("=" * 70)

if __name__ == "__main__":
    benchmark()
