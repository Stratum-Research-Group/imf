"""
Triton Fused Kernel: Poincaré Toda Lattice Exponential Multi-Particle Soliton Flow (SM 12.0)
Cycle 238 Capstone: Exponential Nearest-Neighbor Interactions, Flaschka Jacobi Lax Evolution,
and Poincaré Hyperbolic Confinement.

Physical Model:
Toda lattice Hamiltonian:
    H = \sum_n \left[ \frac{1}{2} p_n^2 + e^{-(q_{n+1} - q_n)} \right]
Equations of motion:
    \dot{q}_n = p_n
    \dot{p}_n = e^{-(q_n - q_{n-1})} - e^{-(q_{n+1} - q_n)}

Projected onto Poincaré disk manifold g(u) = 4 / (1 - u^2)^2.
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_toda_lattice_kernel(
    q_ptr, p_ptr,
    out_q_ptr, out_p_ptr,
    dt, n_particles,
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

    # Exponential forces: F_left = exp(-(q - q_prev)), F_right = exp(-(q_next - q))
    diff_left = tl.maximum(tl.minimum(q - q_prev, 5.0), -5.0)
    diff_right = tl.maximum(tl.minimum(q_next - q, 5.0), -5.0)

    f_left = tl.exp(-diff_left)
    f_right = tl.exp(-diff_right)

    # Toda net force: \dot{p} = f_left - f_right
    force = f_left - f_right

    # Hyperbolic metric conformal factor g(u) = 4 / (1 - u^2)^2
    q_sq = q * q
    safe_denom = tl.maximum(1.0 - q_sq, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_p = p + effective_dt * force
    out_q = q + effective_dt * out_p

    # Project to Poincare interval (-0.98, 0.98)
    out_q = tl.maximum(tl.minimum(out_q, 0.98), -0.98)

    tl.store(out_q_ptr + offsets, out_q, mask=mask)
    tl.store(out_p_ptr + offsets, out_p, mask=mask)

def poincare_toda_lattice_triton(q: torch.Tensor, p: torch.Tensor, dt: float = 0.001):
    assert q.is_cuda and p.is_cuda
    n = q.numel()
    out_q = torch.empty_like(q)
    out_p = torch.empty_like(p)
    BLOCK_N = 1024
    grid = (triton.cdiv(n, BLOCK_N),)
    _poincare_toda_lattice_kernel[grid](
        q, p, out_q, out_p,
        dt, n,
        BLOCK_N=BLOCK_N
    )
    return out_q, out_p

def poincare_toda_lattice_pytorch(q: torch.Tensor, p: torch.Tensor, dt: float = 0.001):
    q_prev = torch.roll(q, shifts=1, dims=0)
    q_next = torch.roll(q, shifts=-1, dims=0)

    diff_left = torch.clamp(q - q_prev, -5.0, 5.0)
    diff_right = torch.clamp(q_next - q, -5.0, 5.0)

    f_left = torch.exp(-diff_left)
    f_right = torch.exp(-diff_right)
    force = f_left - f_right

    q_sq = q * q
    safe_denom = torch.clamp(1.0 - q_sq, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_p = p + effective_dt * force
    out_q = q + effective_dt * out_p
    return torch.clamp(out_q, -0.98, 0.98), out_p

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ TODA LATTICE FLOW (RTX 5060 Ti SM 12.0)")
    print("=" * 70)

    n = 131072  # 128k particles
    q = torch.randn(n, device=device, dtype=torch.float32) * 0.3
    p = torch.randn(n, device=device, dtype=torch.float32) * 0.1

    for _ in range(20):
        out_q_tri, out_p_tri = poincare_toda_lattice_triton(q, p)
        out_q_pt, out_p_pt = poincare_toda_lattice_pytorch(q, p)
    torch.cuda.synchronize()

    max_err_q = (out_q_tri - out_q_pt).abs().max().item()
    max_err_p = (out_p_tri - out_p_pt).abs().max().item()
    print(f"Max Absolute Error Q: {max_err_q:.2e}")
    print(f"Max Absolute Error P: {max_err_p:.2e}")
    assert max_err_q < 1e-4 and max_err_p < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_q_pt, out_p_pt = poincare_toda_lattice_pytorch(q, p)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_q_tri, out_p_tri = poincare_toda_lattice_triton(q, p)
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
