"""
Triton Fused Kernel: Poincaré Ablowitz-Ladik Discrete Integrable Soliton Lattice (SM 8.9)
Cycle 240 Capstone: Canonical Discrete NLS Integrability, Complex-Valued Pairwise Coupling,
and Poincaré Hyperbolic Confinement.

Physical Model:
Ablowitz-Ladik (AL) lattice equation:
    i \dot{\psi}_n + (\psi_{n+1} - 2 \psi_n + \psi_{n-1}) + |\psi_n|^2 (\psi_{n+1} + \psi_{n-1}) = 0
Rewritten in real and imaginary components \psi_n = u_n + i v_n:
    \dot{u}_n = - [ (v_{n+1} - 2 v_n + v_{n-1}) + (u_n^2 + v_n^2)(v_{n+1} + v_{n-1}) ]
    \dot{v}_n = [ (u_{n+1} - 2 u_n + u_{n-1}) + (u_n^2 + v_n^2)(u_{n+1} + u_{n-1}) ]

Projected onto Poincaré disk manifold g(u, v) = 4 / (1 - (u^2 + v^2))^2.
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_ablowitz_ladik_kernel(
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

    # Intensity |\psi_n|^2
    intensity = u * u + v * v

    # Linear dispersion: \psi_{n+1} - 2 \psi_n + \psi_{n-1}
    disp_u = u_next - 2.0 * u + u_prev
    disp_v = v_next - 2.0 * v + v_prev

    # Nonlinear coupling: |\psi_n|^2 (\psi_{n+1} + \psi_{n-1})
    sum_u = u_next + u_prev
    sum_v = v_next + v_prev

    nl_u = intensity * sum_u
    nl_v = intensity * sum_v

    # Equations of motion:
    # \dot{u} = - (disp_v + nl_v)
    # \dot{v} = (disp_u + nl_u)
    u_dot = - (disp_v + nl_v)
    v_dot = disp_u + nl_u

    # Hyperbolic metric conformal factor g(u, v) = 4 / (1 - (u^2 + v^2))^2
    safe_denom = tl.maximum(1.0 - intensity, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_u = u + effective_dt * u_dot
    out_v = v + effective_dt * v_dot

    # Project to Poincare unit disk
    norm_sq = out_u * out_u + out_v * out_v
    scale = tl.where(norm_sq >= 0.98, tl.sqrt(0.98 / norm_sq), 1.0)
    out_u = out_u * scale
    out_v = out_v * scale

    tl.store(out_u_ptr + offsets, out_u, mask=mask)
    tl.store(out_v_ptr + offsets, out_v, mask=mask)

def poincare_ablowitz_ladik_triton(u: torch.Tensor, v: torch.Tensor, dt: float = 0.001):
    assert u.is_cuda and v.is_cuda
    n = u.numel()
    out_u = torch.empty_like(u)
    out_v = torch.empty_like(v)
    BLOCK_N = 1024
    grid = (triton.cdiv(n, BLOCK_N),)
    _poincare_ablowitz_ladik_kernel[grid](
        u, v, out_u, out_v,
        dt, n,
        BLOCK_N=BLOCK_N
    )
    return out_u, out_v

def poincare_ablowitz_ladik_pytorch(u: torch.Tensor, v: torch.Tensor, dt: float = 0.001):
    u_prev = torch.roll(u, shifts=1, dims=0)
    v_prev = torch.roll(v, shifts=1, dims=0)
    u_next = torch.roll(u, shifts=-1, dims=0)
    v_next = torch.roll(v, shifts=-1, dims=0)

    intensity = u * u + v * v

    disp_u = u_next - 2.0 * u + u_prev
    disp_v = v_next - 2.0 * v + v_prev

    sum_u = u_next + u_prev
    sum_v = v_next + v_prev

    nl_u = intensity * sum_u
    nl_v = intensity * sum_v

    u_dot = - (disp_v + nl_v)
    v_dot = disp_u + nl_u

    safe_denom = torch.clamp(1.0 - intensity, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_u = u + effective_dt * u_dot
    out_v = v + effective_dt * v_dot

    norm_sq = out_u * out_u + out_v * out_v
    scale = torch.ones_like(norm_sq)
    mask = norm_sq >= 0.98
    scale[mask] = torch.sqrt(0.98 / norm_sq[mask])

    return out_u * scale, out_v * scale

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ ABLOWITZ-LADIK FLOW (RTX 5060 Ti SM 8.9)")
    print("=" * 70)

    n = 131072  # 128k lattice nodes
    u = torch.randn(n, device=device, dtype=torch.float32) * 0.3
    v = torch.randn(n, device=device, dtype=torch.float32) * 0.3

    for _ in range(20):
        out_u_tri, out_v_tri = poincare_ablowitz_ladik_triton(u, v)
        out_u_pt, out_v_pt = poincare_ablowitz_ladik_pytorch(u, v)
    torch.cuda.synchronize()

    max_err_u = (out_u_tri - out_u_pt).abs().max().item()
    max_err_v = (out_v_tri - out_v_pt).abs().max().item()
    print(f"Max Absolute Error U: {max_err_u:.2e}")
    print(f"Max Absolute Error V: {max_err_v:.2e}")
    assert max_err_u < 1e-4 and max_err_v < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_u_pt, out_v_pt = poincare_ablowitz_ladik_pytorch(u, v)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_u_tri, out_v_tri = poincare_ablowitz_ladik_triton(u, v)
    torch.cuda.synchronize()
    t_tri = (time.perf_counter() - t0) / iters * 1000.0

    speedup = t_pt / t_tri
    throughput = (n / (t_tri / 1000.0)) / 1e6

    print(f"PyTorch Time:  {t_pt * 1000.0:.2f} µs")
    print(f"Triton Time:   {t_tri * 1000.0:.2f} µs")
    print(f"Speedup:       {speedup:.2f}x")
    print(f"Throughput:    {throughput:.2f} M lattice-nodes/s")
    print("=" * 70)

if __name__ == "__main__":
    benchmark()
