"""
Triton Fused Kernel: Poincaré Discrete Sine-Gordon (Frenkel-Kontorova) Dislocation Flow (SM 12.0)
Cycle 245 Capstone: Topological Kink Solitons, Periodic Peierls-Nabarro Barrier,
and Poincaré Hyperbolic Confinement.

Physical Model:
Frenkel-Kontorova (discrete sine-Gordon) equations:
    \ddot{\phi}_n = (\phi_{n+1} - 2\phi_n + \phi_{n-1}) - \sin(\phi_n)
Rewritten in symplectic phase-space form (\phi_n, p_n):
    \dot{\phi}_n = p_n
    \dot{p}_n = (\phi_{n+1} - 2\phi_n + \phi_{n-1}) - \sin(\phi_n)

Projected onto Poincaré disk manifold g(\phi, p) = 4 / (1 - (\phi^2 + p^2))^2.
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_frenkel_kontorova_kernel(
    phi_ptr, p_ptr,
    out_phi_ptr, out_p_ptr,
    dt, n_elements,
    BLOCK_N: tl.constexpr
):
    pid = tl.program_id(axis=0)
    offsets = pid * BLOCK_N + tl.arange(0, BLOCK_N)
    mask = offsets < n_elements

    idx_prev = (offsets - 1 + n_elements) % n_elements
    idx_next = (offsets + 1) % n_elements

    phi = tl.load(phi_ptr + offsets, mask=mask, other=0.0)
    p = tl.load(p_ptr + offsets, mask=mask, other=0.0)

    phi_prev = tl.load(phi_ptr + idx_prev, mask=mask, other=0.0)
    phi_next = tl.load(phi_ptr + idx_next, mask=mask, other=0.0)

    # Elastic coupling + periodic substrate potential:
    # force = (phi_{n+1} - 2 phi_n + phi_{n-1}) - sin(phi_n)
    coupling = phi_next - 2.0 * phi + phi_prev
    force = coupling - tl.sin(phi)

    # Conformal factor
    norm_sq = phi * phi + p * p
    safe_denom = tl.maximum(1.0 - norm_sq, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_p = p + effective_dt * force
    out_phi = phi + effective_dt * out_p

    # Project to Poincare unit disk
    out_norm_sq = out_phi * out_phi + out_p * out_p
    scale = tl.where(out_norm_sq >= 0.98, tl.sqrt(0.98 / out_norm_sq), 1.0)
    out_phi = out_phi * scale
    out_p = out_p * scale

    tl.store(out_phi_ptr + offsets, out_phi, mask=mask)
    tl.store(out_p_ptr + offsets, out_p, mask=mask)

def poincare_frenkel_kontorova_triton(phi: torch.Tensor, p: torch.Tensor, dt: float = 0.001):
    assert phi.is_cuda and p.is_cuda
    n = phi.numel()
    out_phi = torch.empty_like(phi)
    out_p = torch.empty_like(p)
    BLOCK_N = 1024
    grid = (triton.cdiv(n, BLOCK_N),)
    _poincare_frenkel_kontorova_kernel[grid](
        phi, p, out_phi, out_p,
        dt, n,
        BLOCK_N=BLOCK_N
    )
    return out_phi, out_p

def poincare_frenkel_kontorova_pytorch(phi: torch.Tensor, p: torch.Tensor, dt: float = 0.001):
    phi_prev = torch.roll(phi, shifts=1, dims=0)
    phi_next = torch.roll(phi, shifts=-1, dims=0)

    coupling = phi_next - 2.0 * phi + phi_prev
    force = coupling - torch.sin(phi)

    norm_sq = phi * phi + p * p
    safe_denom = torch.clamp(1.0 - norm_sq, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_p = p + effective_dt * force
    out_phi = phi + effective_dt * out_p

    out_norm_sq = out_phi * out_phi + out_p * out_p
    scale = torch.ones_like(out_norm_sq)
    mask = out_norm_sq >= 0.98
    scale[mask] = torch.sqrt(0.98 / out_norm_sq[mask])

    return out_phi * scale, out_p * scale

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ FRENKEL-KONTOROVA FLOW (RTX 5060 Ti SM 12.0)")
    print("=" * 70)

    n = 131072
    phi = torch.randn(n, device=device, dtype=torch.float32) * 0.3
    p = torch.randn(n, device=device, dtype=torch.float32) * 0.1

    for _ in range(20):
        out_phi_tri, out_p_tri = poincare_frenkel_kontorova_triton(phi, p)
        out_phi_pt, out_p_pt = poincare_frenkel_kontorova_pytorch(phi, p)
    torch.cuda.synchronize()

    max_err_phi = (out_phi_tri - out_phi_pt).abs().max().item()
    max_err_p = (out_p_tri - out_p_pt).abs().max().item()
    print(f"Max Absolute Error Phi: {max_err_phi:.2e}")
    print(f"Max Absolute Error P:   {max_err_p:.2e}")
    assert max_err_phi < 1e-4 and max_err_p < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_phi_pt, out_p_pt = poincare_frenkel_kontorova_pytorch(phi, p)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_phi_tri, out_p_tri = poincare_frenkel_kontorova_triton(phi, p)
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
