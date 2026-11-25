"""
Triton Fused Kernel: Poincaré Discrete Complex mKdV (Hirota) Lattice Soliton Flow (SM 12.0)
Cycle 248 Capstone: Complex-Valued Discrete Integrable Flow, Unitary Phase Dynamics,
and Poincaré Hyperbolic Confinement.

Physical Model:
Discrete complex mKdV (Hirota lattice) equation:
    \dot{z}_n = (1 + |z_n|^2) (z_{n+1} - z_{n-1})
Decomposed into real and imaginary parts z_n = u_n + i v_n:
    \dot{u}_n = (1 + u_n^2 + v_n^2) (u_{n+1} - u_{n-1})
    \dot{v}_n = (1 + u_n^2 + v_n^2) (v_{n+1} - v_{n-1})

Projected onto Poincaré disk manifold g(u, v) = 4 / (1 - (u^2 + v^2))^2.
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_discrete_complex_mkdv_kernel(
    u_ptr, v_ptr,
    out_u_ptr, out_v_ptr,
    dt, n_elements,
    BLOCK_N: tl.constexpr
):
    pid = tl.program_id(axis=0)
    offsets = pid * BLOCK_N + tl.arange(0, BLOCK_N)
    mask = offsets < n_elements

    idx_prev = (offsets - 1 + n_elements) % n_elements
    idx_next = (offsets + 1) % n_elements

    u = tl.load(u_ptr + offsets, mask=mask, other=0.0)
    v = tl.load(v_ptr + offsets, mask=mask, other=0.0)

    u_prev = tl.load(u_ptr + idx_prev, mask=mask, other=0.0)
    v_prev = tl.load(v_ptr + idx_prev, mask=mask, other=0.0)
    u_next = tl.load(u_ptr + idx_next, mask=mask, other=0.0)
    v_next = tl.load(v_ptr + idx_next, mask=mask, other=0.0)

    # Factor: (1 + |z_n|^2) = (1 + u^2 + v^2)
    norm_sq = u * u + v * v
    factor = 1.0 + norm_sq

    # Hirota complex lattice evolution
    u_dot = factor * (u_next - u_prev)
    v_dot = factor * (v_next - v_prev)

    # Conformal factor
    safe_denom = tl.maximum(1.0 - norm_sq, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_u = u + effective_dt * u_dot
    out_v = v + effective_dt * v_dot

    # Project to Poincare disk
    out_norm_sq = out_u * out_u + out_v * out_v
    scale = tl.where(out_norm_sq >= 0.98, tl.sqrt(0.98 / out_norm_sq), 1.0)
    out_u = out_u * scale
    out_v = out_v * scale

    tl.store(out_u_ptr + offsets, out_u, mask=mask)
    tl.store(out_v_ptr + offsets, out_v, mask=mask)

def poincare_discrete_complex_mkdv_triton(u: torch.Tensor, v: torch.Tensor, dt: float = 0.001):
    assert u.is_cuda and v.is_cuda
    n = u.numel()
    out_u = torch.empty_like(u)
    out_v = torch.empty_like(v)
    BLOCK_N = 1024
    grid = (triton.cdiv(n, BLOCK_N),)
    _poincare_discrete_complex_mkdv_kernel[grid](
        u, v, out_u, out_v,
        dt, n,
        BLOCK_N=BLOCK_N
    )
    return out_u, out_v

def poincare_discrete_complex_mkdv_pytorch(u: torch.Tensor, v: torch.Tensor, dt: float = 0.001):
    u_prev = torch.roll(u, shifts=1, dims=0)
    v_prev = torch.roll(v, shifts=1, dims=0)
    u_next = torch.roll(u, shifts=-1, dims=0)
    v_next = torch.roll(v, shifts=-1, dims=0)

    norm_sq = u * u + v * v
    factor = 1.0 + norm_sq

    u_dot = factor * (u_next - u_prev)
    v_dot = factor * (v_next - v_prev)

    safe_denom = torch.clamp(1.0 - norm_sq, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_u = u + effective_dt * u_dot
    out_v = v + effective_dt * v_dot

    out_norm_sq = out_u * out_u + out_v * out_v
    scale = torch.ones_like(out_norm_sq)
    mask = out_norm_sq >= 0.98
    scale[mask] = torch.sqrt(0.98 / out_norm_sq[mask])

    return out_u * scale, out_v * scale

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ DISCRETE COMPLEX MKDV FLOW (RTX 5060 Ti SM 12.0)")
    print("=" * 70)

    n = 131072
    u = torch.randn(n, device=device, dtype=torch.float32) * 0.3
    v = torch.randn(n, device=device, dtype=torch.float32) * 0.3

    for _ in range(20):
        out_u_tri, out_v_tri = poincare_discrete_complex_mkdv_triton(u, v)
        out_u_pt, out_v_pt = poincare_discrete_complex_mkdv_pytorch(u, v)
    torch.cuda.synchronize()

    max_err_u = (out_u_tri - out_u_pt).abs().max().item()
    max_err_v = (out_v_tri - out_v_pt).abs().max().item()
    print(f"Max Absolute Error U: {max_err_u:.2e}")
    print(f"Max Absolute Error V: {max_err_v:.2e}")
    assert max_err_u < 1e-4 and max_err_v < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_u_pt, out_v_pt = poincare_discrete_complex_mkdv_pytorch(u, v)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_u_tri, out_v_tri = poincare_discrete_complex_mkdv_triton(u, v)
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
