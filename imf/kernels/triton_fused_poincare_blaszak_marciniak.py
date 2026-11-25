"""
Triton Fused Kernel: Poincaré Blaszak-Marciniak Multi-Field Integrable Lattice (SM 8.9)
Cycle 244 Capstone: Three-Field Coupled Lattice Flow, Higher-Rank Poisson Tensors,
and Poincaré Hyperbolic Confinement.

Physical Model:
Blaszak-Marciniak (BM) 3-field lattice equations:
    \dot{a}_n = a_n (b_{n+1} - b_n)
    \dot{b}_n = c_{n+1} - c_n + a_n - a_{n-1}
    \dot{c}_n = b_n a_n - b_{n-1} a_{n-1}

Projected onto Poincaré disk manifold g(u) = 4 / (1 - (a^2 + b^2 + c^2))^2.
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_blaszak_marciniak_kernel(
    a_ptr, b_ptr, c_ptr,
    out_a_ptr, out_b_ptr, out_c_ptr,
    dt, n_elements,
    BLOCK_N: tl.constexpr
):
    pid = tl.program_id(axis=0)
    offsets = pid * BLOCK_N + tl.arange(0, BLOCK_N)
    mask = offsets < n_elements

    idx_prev = (offsets - 1 + n_elements) % n_elements
    idx_next = (offsets + 1) % n_elements

    a = tl.load(a_ptr + offsets, mask=mask, other=0.0)
    b = tl.load(b_ptr + offsets, mask=mask, other=0.0)
    c = tl.load(c_ptr + offsets, mask=mask, other=0.0)

    a_prev = tl.load(a_ptr + idx_prev, mask=mask, other=0.0)
    b_prev = tl.load(b_ptr + idx_prev, mask=mask, other=0.0)
    b_next = tl.load(b_ptr + idx_next, mask=mask, other=0.0)
    c_next = tl.load(c_ptr + idx_next, mask=mask, other=0.0)

    # BM 3-field equations
    # \dot{a}_n = a_n (b_{n+1} - b_n)
    a_dot = a * (b_next - b)

    # \dot{b}_n = c_{n+1} - c_n + a_n - a_{n-1}
    b_dot = (c_next - c) + (a - a_prev)

    # \dot{c}_n = b_n a_n - b_{n-1} a_{n-1}
    c_dot = (b * a) - (b_prev * a_prev)

    # Conformal factor g(u) = 4 / (1 - ||u||^2)^2
    norm_sq = a * a + b * b + c * c
    safe_denom = tl.maximum(1.0 - norm_sq, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_a = a + effective_dt * a_dot
    out_b = b + effective_dt * b_dot
    out_c = c + effective_dt * c_dot

    # Project to Poincare 3-ball
    out_norm_sq = out_a * out_a + out_b * out_b + out_c * out_c
    scale = tl.where(out_norm_sq >= 0.98, tl.sqrt(0.98 / out_norm_sq), 1.0)
    out_a = out_a * scale
    out_b = out_b * scale
    out_c = out_c * scale

    tl.store(out_a_ptr + offsets, out_a, mask=mask)
    tl.store(out_b_ptr + offsets, out_b, mask=mask)
    tl.store(out_c_ptr + offsets, out_c, mask=mask)

def poincare_blaszak_marciniak_triton(a: torch.Tensor, b: torch.Tensor, c: torch.Tensor, dt: float = 0.001):
    assert a.is_cuda and b.is_cuda and c.is_cuda
    n = a.numel()
    out_a = torch.empty_like(a)
    out_b = torch.empty_like(b)
    out_c = torch.empty_like(c)
    BLOCK_N = 1024
    grid = (triton.cdiv(n, BLOCK_N),)
    _poincare_blaszak_marciniak_kernel[grid](
        a, b, c, out_a, out_b, out_c,
        dt, n,
        BLOCK_N=BLOCK_N
    )
    return out_a, out_b, out_c

def poincare_blaszak_marciniak_pytorch(a: torch.Tensor, b: torch.Tensor, c: torch.Tensor, dt: float = 0.001):
    a_prev = torch.roll(a, shifts=1, dims=0)
    b_prev = torch.roll(b, shifts=1, dims=0)
    b_next = torch.roll(b, shifts=-1, dims=0)
    c_next = torch.roll(c, shifts=-1, dims=0)

    a_dot = a * (b_next - b)
    b_dot = (c_next - c) + (a - a_prev)
    c_dot = (b * a) - (b_prev * a_prev)

    norm_sq = a * a + b * b + c * c
    safe_denom = torch.clamp(1.0 - norm_sq, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_a = a + effective_dt * a_dot
    out_b = b + effective_dt * b_dot
    out_c = c + effective_dt * c_dot

    out_norm_sq = out_a * out_a + out_b * out_b + out_c * out_c
    scale = torch.ones_like(out_norm_sq)
    mask = out_norm_sq >= 0.98
    scale[mask] = torch.sqrt(0.98 / out_norm_sq[mask])

    return out_a * scale, out_b * scale, out_c * scale

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ BLASZAK-MARCINIAK FLOW (RTX 5060 Ti SM 8.9)")
    print("=" * 70)

    n = 131072
    a = torch.randn(n, device=device, dtype=torch.float32) * 0.25
    b = torch.randn(n, device=device, dtype=torch.float32) * 0.25
    c = torch.randn(n, device=device, dtype=torch.float32) * 0.25

    for _ in range(20):
        out_a_tri, out_b_tri, out_c_tri = poincare_blaszak_marciniak_triton(a, b, c)
        out_a_pt, out_b_pt, out_c_pt = poincare_blaszak_marciniak_pytorch(a, b, c)
    torch.cuda.synchronize()

    max_err_a = (out_a_tri - out_a_pt).abs().max().item()
    max_err_b = (out_b_tri - out_b_pt).abs().max().item()
    max_err_c = (out_c_tri - out_c_pt).abs().max().item()
    print(f"Max Absolute Error A: {max_err_a:.2e}")
    print(f"Max Absolute Error B: {max_err_b:.2e}")
    print(f"Max Absolute Error C: {max_err_c:.2e}")
    assert max_err_a < 1e-4 and max_err_b < 1e-4 and max_err_c < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_a_pt, out_b_pt, out_c_pt = poincare_blaszak_marciniak_pytorch(a, b, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_a_tri, out_b_tri, out_c_tri = poincare_blaszak_marciniak_triton(a, b, c)
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
