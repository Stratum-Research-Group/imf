"""
Triton Fused Kernel: Poincaré Discrete Modified KdV (mKdV) Lattice Flow (SM 8.9)
Cycle 247 Capstone: Cubic Lattice Non-Linearity, Discrete Miura Homomorphism,
and Poincaré Hyperbolic Confinement.

Physical Model:
Discrete mKdV lattice equation:
    \dot{w}_n = (1 - w_n^2) (w_{n+1} - w_{n-1})

Projected onto Poincaré disk manifold g(w) = 4 / (1 - w^2)^2.
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_discrete_mkdv_kernel(
    w_ptr, out_w_ptr,
    dt, n_elements,
    BLOCK_N: tl.constexpr
):
    pid = tl.program_id(axis=0)
    offsets = pid * BLOCK_N + tl.arange(0, BLOCK_N)
    mask = offsets < n_elements

    idx_prev = (offsets - 1 + n_elements) % n_elements
    idx_next = (offsets + 1) % n_elements

    w = tl.load(w_ptr + offsets, mask=mask, other=0.0)
    w_prev = tl.load(w_ptr + idx_prev, mask=mask, other=0.0)
    w_next = tl.load(w_ptr + idx_next, mask=mask, other=0.0)

    # Discrete mKdV equation: \dot{w}_n = (1 - w_n^2) (w_{n+1} - w_{n-1})
    w_sq = w * w
    w_dot = (1.0 - w_sq) * (w_next - w_prev)

    # Conformal factor g(w) = 4 / (1 - w^2)^2
    safe_denom = tl.maximum(1.0 - w_sq, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_w = w + effective_dt * w_dot

    # Project to Poincare interval (-0.98, 0.98)
    out_w = tl.maximum(tl.minimum(out_w, 0.98), -0.98)

    tl.store(out_w_ptr + offsets, out_w, mask=mask)

def poincare_discrete_mkdv_triton(w: torch.Tensor, dt: float = 0.001):
    assert w.is_cuda
    n = w.numel()
    out_w = torch.empty_like(w)
    BLOCK_N = 1024
    grid = (triton.cdiv(n, BLOCK_N),)
    _poincare_discrete_mkdv_kernel[grid](
        w, out_w, dt, n,
        BLOCK_N=BLOCK_N
    )
    return out_w

def poincare_discrete_mkdv_pytorch(w: torch.Tensor, dt: float = 0.001):
    w_prev = torch.roll(w, shifts=1, dims=0)
    w_next = torch.roll(w, shifts=-1, dims=0)

    w_sq = w * w
    w_dot = (1.0 - w_sq) * (w_next - w_prev)

    safe_denom = torch.clamp(1.0 - w_sq, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_w = w + effective_dt * w_dot
    return torch.clamp(out_w, -0.98, 0.98)

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ DISCRETE MKDV FLOW (RTX 5060 Ti SM 8.9)")
    print("=" * 70)

    n = 131072
    w = torch.randn(n, device=device, dtype=torch.float32) * 0.3

    for _ in range(20):
        out_tri = poincare_discrete_mkdv_triton(w)
        out_pt = poincare_discrete_mkdv_pytorch(w)
    torch.cuda.synchronize()

    max_err = (out_tri - out_pt).abs().max().item()
    print(f"Max Absolute Error: {max_err:.2e}")
    assert max_err < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_pt = poincare_discrete_mkdv_pytorch(w)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_tri = poincare_discrete_mkdv_triton(w)
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
