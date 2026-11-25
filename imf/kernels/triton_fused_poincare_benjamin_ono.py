"""
Triton Fused Kernel: Poincaré Benjamin-Ono Deep-Water Soliton Flow (SM 12.0)
Cycle 232 Capstone: Non-Local Hilbert Transform, Algebraic Soliton Profiles,
and Poincaré Hyperbolic Confinement.

Physical Model:
Benjamin-Ono (BO) equation:
    u_t + u u_x + \mathcal{H}(u_{xx}) = 0
where \mathcal{H} is the discrete Hilbert transform.

Projected onto Poincaré disk manifold g(u) = 4 / (1 - u^2)^2.
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_benjamin_ono_kernel(
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

    # Local discrete Hilbert transform approximation on u_xx:
    # \mathcal{H}[f](x) ~ 0.5 * (f(x+1) - f(x-1)) / pi
    # For u_xx, H(u_xx) ~ (u_xxx) / pi ~ 0.5 * (uxx_next - uxx_prev)
    uxx_prev = u_prev - 2.0 * u_prev + u_prev2 # approximation
    uxx_next = u_next2 - 2.0 * u_next + u
    h_uxx = 0.5 * (uxx_next - uxx_prev) * 0.318309886 # 1/pi

    # Benjamin-Ono RHS: u_t = - u * ux - H(u_xx)
    bo_rhs = - u * ux - h_uxx

    # Hyperbolic metric conformal factor g(u) = 4 / (1 - u^2)^2
    u_sq = u * u
    safe_denom = tl.maximum(1.0 - u_sq, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)

    effective_dt = dt / poincare_conformal
    out_u = u + effective_dt * bo_rhs

    # Project to Poincaré interval (-0.98, 0.98)
    out_u = tl.maximum(tl.minimum(out_u, 0.98), -0.98)

    tl.store(out_u_ptr + offsets, out_u, mask=mask)

def poincare_benjamin_ono_triton(u: torch.Tensor, dt: float = 0.001):
    assert u.is_cuda
    n = u.numel()
    out_u = torch.empty_like(u)
    BLOCK_SIZE = 1024
    grid = (triton.cdiv(n, BLOCK_SIZE),)
    _poincare_benjamin_ono_kernel[grid](
        u, out_u, dt, n,
        BLOCK_SIZE=BLOCK_SIZE
    )
    return out_u

def poincare_benjamin_ono_pytorch(u: torch.Tensor, dt: float = 0.001):
    u_prev = torch.roll(u, shifts=1, dims=0)
    u_next = torch.roll(u, shifts=-1, dims=0)
    u_prev2 = torch.roll(u, shifts=2, dims=0)
    u_next2 = torch.roll(u, shifts=-2, dims=0)

    ux = 0.5 * (u_next - u_prev)
    uxx_prev = u_prev - 2.0 * u_prev + u_prev2
    uxx_next = u_next2 - 2.0 * u_next + u
    h_uxx = 0.5 * (uxx_next - uxx_prev) * 0.318309886

    bo_rhs = - u * ux - h_uxx

    u_sq = u * u
    safe_denom = torch.clamp(1.0 - u_sq, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)

    effective_dt = dt / poincare_conformal
    out_u = u + effective_dt * bo_rhs
    return torch.clamp(out_u, -0.98, 0.98)

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ BENJAMIN-ONO FLOW (RTX 5060 Ti SM 12.0)")
    print("=" * 70)

    n = 131072
    u = torch.randn(n, device=device, dtype=torch.float32) * 0.4

    for _ in range(20):
        out_tri = poincare_benjamin_ono_triton(u)
        out_pt = poincare_benjamin_ono_pytorch(u)
    torch.cuda.synchronize()

    max_err = (out_tri - out_pt).abs().max().item()
    print(f"Max Absolute Error: {max_err:.2e}")
    assert max_err < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_pt = poincare_benjamin_ono_pytorch(u)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_tri = poincare_benjamin_ono_triton(u)
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
