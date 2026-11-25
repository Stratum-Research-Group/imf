"""
Triton Fused Kernel: Poincaré Ito Seventh-Order Integrable Soliton Hierarchy (SM 12.0)
Cycle 236 Capstone: Ultra-High Dispersive Order, Multi-Convective Stencil Balance,
and Poincaré Hyperbolic Confinement.

Physical Model:
Ito 7th-order equation:
    u_t + \partial_x [ u_{xxxxxx} + 14 u u_{xxxx} + 21 u_x u_{xxx} + 14 (u_{xx})^2 + 70 u^2 u_{xx} + 70 u (u_x)^2 + 70 u^4 ] = 0

Projected onto Poincaré disk manifold g(u) = 4 / (1 - u^2)^2.
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_ito_seventh_order_kernel(
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
    idx_p4 = (offsets - 4 + n_elements) % n_elements
    idx_n4 = (offsets + 4) % n_elements

    u = tl.load(u_ptr + offsets, mask=mask, other=0.0)
    u_p1 = tl.load(u_ptr + idx_p1, mask=mask, other=0.0)
    u_n1 = tl.load(u_ptr + idx_n1, mask=mask, other=0.0)
    u_p2 = tl.load(u_ptr + idx_p2, mask=mask, other=0.0)
    u_n2 = tl.load(u_ptr + idx_n2, mask=mask, other=0.0)
    u_p3 = tl.load(u_ptr + idx_p3, mask=mask, other=0.0)
    u_n3 = tl.load(u_ptr + idx_n3, mask=mask, other=0.0)
    u_p4 = tl.load(u_ptr + idx_p4, mask=mask, other=0.0)
    u_n4 = tl.load(u_ptr + idx_n4, mask=mask, other=0.0)

    # Centered finite differences
    ux = 0.5 * (u_n1 - u_p1)
    uxx = u_n1 - 2.0 * u + u_p1
    uxxx = 0.5 * (u_n2 - 2.0 * u_n1 + 2.0 * u_p1 - u_p2)
    uxxxx = u_n2 - 4.0 * u_n1 + 6.0 * u - 4.0 * u_p1 + u_p2
    uxxxxx = 0.5 * (u_n3 - 4.0 * u_n2 + 5.0 * u_n1 - 5.0 * u_p1 + 4.0 * u_p2 - u_p3)
    # 7th derivative
    uxxxxxxx = 0.5 * (u_n4 - 6.0 * u_n3 + 14.0 * u_n2 - 14.0 * u_n1 + 14.0 * u_p1 - 14.0 * u_p2 + 6.0 * u_p3 - u_p4)

    # Ito 7th-order convective terms:
    # \partial_x [ uxxxxxx + 14 u uxxxx + 21 ux uxxx + 14 (uxx)^2 + 70 u^2 uxx + 70 u (ux)^2 + 70 u^4 ]
    # Leading terms evaluated:
    term_disp = uxxxxxxx
    term_14 = 14.0 * (ux * uxxxx + u * uxxxxx)
    term_21 = 21.0 * (uxx * uxxx + ux * uxxxx)
    term_70 = 70.0 * (2.0 * u * ux * uxx + u * u * uxxx + ux * ux * ux + 2.0 * u * ux * uxx + 4.0 * u * u * u * ux)

    ito_rhs = - (term_disp + term_14 + term_21 + term_70)

    # Hyperbolic metric conformal factor g(u) = 4 / (1 - u^2)^2
    u_sq = u * u
    safe_denom = tl.maximum(1.0 - u_sq, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)

    effective_dt = dt / poincare_conformal
    out_u = u + effective_dt * ito_rhs

    # Project to Poincaré interval (-0.98, 0.98)
    out_u = tl.maximum(tl.minimum(out_u, 0.98), -0.98)

    tl.store(out_u_ptr + offsets, out_u, mask=mask)

def poincare_ito_seventh_order_triton(u: torch.Tensor, dt: float = 0.00001):
    assert u.is_cuda
    n = u.numel()
    out_u = torch.empty_like(u)
    BLOCK_SIZE = 1024
    grid = (triton.cdiv(n, BLOCK_SIZE),)
    _poincare_ito_seventh_order_kernel[grid](
        u, out_u, dt, n,
        BLOCK_SIZE=BLOCK_SIZE
    )
    return out_u

def poincare_ito_seventh_order_pytorch(u: torch.Tensor, dt: float = 0.00001):
    u_p1 = torch.roll(u, shifts=1, dims=0)
    u_n1 = torch.roll(u, shifts=-1, dims=0)
    u_p2 = torch.roll(u, shifts=2, dims=0)
    u_n2 = torch.roll(u, shifts=-2, dims=0)
    u_p3 = torch.roll(u, shifts=3, dims=0)
    u_n3 = torch.roll(u, shifts=-3, dims=0)
    u_p4 = torch.roll(u, shifts=4, dims=0)
    u_n4 = torch.roll(u, shifts=-4, dims=0)

    ux = 0.5 * (u_n1 - u_p1)
    uxx = u_n1 - 2.0 * u + u_p1
    uxxx = 0.5 * (u_n2 - 2.0 * u_n1 + 2.0 * u_p1 - u_p2)
    uxxxx = u_n2 - 4.0 * u_n1 + 6.0 * u - 4.0 * u_p1 + u_p2
    uxxxxx = 0.5 * (u_n3 - 4.0 * u_n2 + 5.0 * u_n1 - 5.0 * u_p1 + 4.0 * u_p2 - u_p3)
    uxxxxxxx = 0.5 * (u_n4 - 6.0 * u_n3 + 14.0 * u_n2 - 14.0 * u_n1 + 14.0 * u_p1 - 14.0 * u_p2 + 6.0 * u_p3 - u_p4)

    term_disp = uxxxxxxx
    term_14 = 14.0 * (ux * uxxxx + u * uxxxxx)
    term_21 = 21.0 * (uxx * uxxx + ux * uxxxx)
    term_70 = 70.0 * (2.0 * u * ux * uxx + u * u * uxxx + ux * ux * ux + 2.0 * u * ux * uxx + 4.0 * u * u * u * ux)

    ito_rhs = - (term_disp + term_14 + term_21 + term_70)

    u_sq = u * u
    safe_denom = torch.clamp(1.0 - u_sq, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)

    effective_dt = dt / poincare_conformal
    out_u = u + effective_dt * ito_rhs
    return torch.clamp(out_u, -0.98, 0.98)

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ ITO SEVENTH-ORDER FLOW (RTX 5060 Ti SM 12.0)")
    print("=" * 70)

    n = 131072
    u = torch.randn(n, device=device, dtype=torch.float32) * 0.2

    for _ in range(20):
        out_tri = poincare_ito_seventh_order_triton(u)
        out_pt = poincare_ito_seventh_order_pytorch(u)
    torch.cuda.synchronize()

    max_err = (out_tri - out_pt).abs().max().item()
    print(f"Max Absolute Error: {max_err:.2e}")
    assert max_err < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_pt = poincare_ito_seventh_order_pytorch(u)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_tri = poincare_ito_seventh_order_triton(u)
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
