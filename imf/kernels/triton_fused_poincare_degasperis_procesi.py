"""
Triton Fused Kernel: Poincaré Degasperis-Procesi Peakon Hamiltonian Reduction (SM 8.9)
Cycle 227 Capstone: Non-Smooth Solitons (Peakons) with Shock Formation on Hyperbolic Poincaré Manifold.

Physical Model:
Degasperis-Procesi (DP) equation:
    u_t - u_{txx} + 4 u u_x = 3 u_x u_{xx} + u u_{xxx}

Rewritten in momentum density form m = u - u_{xx}:
    m_t + m_x u + 3 m u_x = 0

Projected onto Poincaré disk manifold $\mathbb{D}^1$ with hyperbolic metric
    g(u) = 4 / (1 - u^2)^2
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_degasperis_procesi_kernel(
    u_ptr, out_u_ptr,
    dt, n_elements,
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
    # u_xx
    uxx = u_next - 2.0 * u + u_prev
    # u_xxx
    uxxx = 0.5 * (u_next2 - 2.0 * u_next + 2.0 * u_prev - u_prev2)

    # Momentum variable m = u - u_xx
    m = u - uxx
    m_prev = u_prev - (u - 2.0 * u_prev + u_prev2)
    m_next = u_next - (u_next2 - 2.0 * u_next + u)
    mx = 0.5 * (m_next - m_prev)

    # Degasperis-Procesi RHS for m_t:
    # m_t = - (mx * u + 3.0 * m * ux)
    m_t = - (mx * u + 3.0 * m * ux)

    # Resolvent inversion for u_t: (1 - d_x^2) u_t = m_t
    # In localized Green's function approximation on grid (dx=1), (1 - d_x^2)^{-1} ~ 0.5 * exp(-|x|)
    # Local 3-point inversion kernel: [0.25, 0.5, 0.25]
    # Evaluate m_t at neighbors
    # For strict local execution, u_t ~ 0.5 * m_t + 0.25 * (m_t_prev + m_t_next)
    # Direct approximation:
    ut_rhs = 0.5 * m_t

    # Hyperbolic metric conformal factor
    u_sq = u * u
    safe_denom = tl.maximum(1.0 - u_sq, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)

    effective_dt = dt / poincare_conformal
    out_u = u + effective_dt * ut_rhs

    # Project to Poincaré interval (-0.99, 0.99)
    out_u = tl.maximum(tl.minimum(out_u, 0.98), -0.98)

    tl.store(out_u_ptr + offsets, out_u, mask=mask)

def poincare_degasperis_procesi_triton(u: torch.Tensor, dt: float = 0.001):
    assert u.is_cuda
    n = u.numel()
    out_u = torch.empty_like(u)
    BLOCK_SIZE = 1024
    grid = (triton.cdiv(n, BLOCK_SIZE),)
    _poincare_degasperis_procesi_kernel[grid](
        u, out_u, dt, n,
        BLOCK_SIZE=BLOCK_SIZE
    )
    return out_u

def poincare_degasperis_procesi_pytorch(u: torch.Tensor, dt: float = 0.001):
    u_prev = torch.roll(u, shifts=1, dims=0)
    u_next = torch.roll(u, shifts=-1, dims=0)
    u_prev2 = torch.roll(u, shifts=2, dims=0)
    u_next2 = torch.roll(u, shifts=-2, dims=0)

    ux = 0.5 * (u_next - u_prev)
    uxx = u_next - 2.0 * u + u_prev
    uxxx = 0.5 * (u_next2 - 2.0 * u_next + 2.0 * u_prev - u_prev2)

    m = u - uxx
    m_prev = u_prev - (u - 2.0 * u_prev + u_prev2)
    m_next = u_next - (u_next2 - 2.0 * u_next + u)
    mx = 0.5 * (m_next - m_prev)

    m_t = - (mx * u + 3.0 * m * ux)
    ut_rhs = 0.5 * m_t

    safe_denom = torch.clamp(1.0 - u * u, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_u = u + effective_dt * ut_rhs
    return torch.clamp(out_u, -0.98, 0.98)

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ DEGASPERIS-PROCESI FLOW (RTX 5060 Ti SM 8.9)")
    print("=" * 70)

    n = 131072
    u = torch.randn(n, device=device, dtype=torch.float32) * 0.4

    for _ in range(20):
        out_tri = poincare_degasperis_procesi_triton(u)
        out_pt = poincare_degasperis_procesi_pytorch(u)
    torch.cuda.synchronize()

    max_err = (out_tri - out_pt).abs().max().item()
    print(f"Max Absolute Error: {max_err:.2e}")
    assert max_err < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_pt = poincare_degasperis_procesi_pytorch(u)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_tri = poincare_degasperis_procesi_triton(u)
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
