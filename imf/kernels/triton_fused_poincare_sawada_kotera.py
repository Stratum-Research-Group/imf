"""
Triton Fused Kernel: Poincaré Sawada-Kotera Fifth-Order Dispersive Flow (SM 8.9)
Cycle 234 Capstone: High-Order Dispersive Integrability, Non-Local Lie Point Symmetries,
and Poincaré Hyperbolic Confinement.

Physical Model:
Sawada-Kotera (SK) equation:
    u_t + 45 u^2 u_x + 15 u_x u_{xx} + 15 u u_{xxx} + u_{xxxxx} = 0
Rewritten in evolutionary form:
    u_t = - (u_{xxxxx} + 15 u u_{xxx} + 15 u_x u_{xx} + 45 u^2 u_x)

Projected onto Poincaré disk manifold g(u) = 4 / (1 - u^2)^2.
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_sawada_kotera_kernel(
    u_ptr, out_u_ptr,
    dt, n_elements,
    BLOCK_SIZE: tl.constexpr
):
    pid = tl.program_id(axis=0)
    offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offsets < n_elements

    idx_p1 = (offsets - 1 + n_elements) % n_elements
    idx_n1 = (offsets + 1) % n_elements
    idx_p2 = (offsets - 2 + n_elements) % n_elements
    idx_n2 = (offsets + 2) % n_elements
    idx_p3 = (offsets - 3 + n_elements) % n_elements
    idx_n3 = (offsets + 3) % n_elements

    u = tl.load(u_ptr + offsets, mask=mask, other=0.0)
    u_p1 = tl.load(u_ptr + idx_p1, mask=mask, other=0.0)
    u_n1 = tl.load(u_ptr + idx_n1, mask=mask, other=0.0)
    u_p2 = tl.load(u_ptr + idx_p2, mask=mask, other=0.0)
    u_n2 = tl.load(u_ptr + idx_n2, mask=mask, other=0.0)
    u_p3 = tl.load(u_ptr + idx_p3, mask=mask, other=0.0)
    u_n3 = tl.load(u_ptr + idx_n3, mask=mask, other=0.0)

    # Centered finite differences (dx=1.0)
    # u_x: 0.5 * (u_{n1} - u_{p1})
    ux = 0.5 * (u_n1 - u_p1)

    # u_xx: u_{n1} - 2 u + u_{p1}
    uxx = u_n1 - 2.0 * u + u_p1

    # u_xxx: 0.5 * (u_{n2} - 2 u_{n1} + 2 u_{p1} - u_{p2})
    uxxx = 0.5 * (u_n2 - 2.0 * u_n1 + 2.0 * u_p1 - u_p2)

    # u_xxxxx: 0.5 * (u_{n3} - 4 u_{n2} + 5 u_{n1} - 5 u_{p1} + 4 u_{p2} - u_{p3})
    uxxxxx = 0.5 * (u_n3 - 4.0 * u_n2 + 5.0 * u_n1 - 5.0 * u_p1 + 4.0 * u_p2 - u_p3)

    # Sawada-Kotera convective terms:
    # 45 u^2 ux + 15 ux uxx + 15 u uxxx + uxxxxx
    sk_rhs = - (uxxxxx + 15.0 * u * uxxx + 15.0 * ux * uxx + 45.0 * u * u * ux)

    # Hyperbolic metric conformal factor g(u) = 4 / (1 - u^2)^2
    u_sq = u * u
    safe_denom = tl.maximum(1.0 - u_sq, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)

    effective_dt = dt / poincare_conformal
    out_u = u + effective_dt * sk_rhs

    # Project to Poincaré interval (-0.98, 0.98)
    out_u = tl.maximum(tl.minimum(out_u, 0.98), -0.98)

    tl.store(out_u_ptr + offsets, out_u, mask=mask)

def poincare_sawada_kotera_triton(u: torch.Tensor, dt: float = 0.0001):
    assert u.is_cuda
    n = u.numel()
    out_u = torch.empty_like(u)
    BLOCK_SIZE = 1024
    grid = (triton.cdiv(n, BLOCK_SIZE),)
    _poincare_sawada_kotera_kernel[grid](
        u, out_u, dt, n,
        BLOCK_SIZE=BLOCK_SIZE
    )
    return out_u

def poincare_sawada_kotera_pytorch(u: torch.Tensor, dt: float = 0.0001):
    u_p1 = torch.roll(u, shifts=1, dims=0)
    u_n1 = torch.roll(u, shifts=-1, dims=0)
    u_p2 = torch.roll(u, shifts=2, dims=0)
    u_n2 = torch.roll(u, shifts=-2, dims=0)
    u_p3 = torch.roll(u, shifts=3, dims=0)
    u_n3 = torch.roll(u, shifts=-3, dims=0)

    ux = 0.5 * (u_n1 - u_p1)
    uxx = u_n1 - 2.0 * u + u_p1
    uxxx = 0.5 * (u_n2 - 2.0 * u_n1 + 2.0 * u_p1 - u_p2)
    uxxxxx = 0.5 * (u_n3 - 4.0 * u_n2 + 5.0 * u_n1 - 5.0 * u_p1 + 4.0 * u_p2 - u_p3)

    sk_rhs = - (uxxxxx + 15.0 * u * uxxx + 15.0 * ux * uxx + 45.0 * u * u * ux)

    u_sq = u * u
    safe_denom = torch.clamp(1.0 - u_sq, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)

    effective_dt = dt / poincare_conformal
    out_u = u + effective_dt * sk_rhs
    return torch.clamp(out_u, -0.98, 0.98)

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ SAWADA-KOTERA FLOW (RTX 5060 Ti SM 8.9)")
    print("=" * 70)

    n = 131072
    u = torch.randn(n, device=device, dtype=torch.float32) * 0.3

    for _ in range(20):
        out_tri = poincare_sawada_kotera_triton(u)
        out_pt = poincare_sawada_kotera_pytorch(u)
    torch.cuda.synchronize()

    max_err = (out_tri - out_pt).abs().max().item()
    print(f"Max Absolute Error: {max_err:.2e}")
    assert max_err < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_pt = poincare_sawada_kotera_pytorch(u)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_tri = poincare_sawada_kotera_triton(u)
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
