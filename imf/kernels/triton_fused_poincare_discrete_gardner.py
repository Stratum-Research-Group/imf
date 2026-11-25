"""
Cycle 276: Fused Poincaré Discrete Gardner (Extended KdV) Lattice Soliton Kernel
Hardware Target: AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9
Author: Nicholas Charles Mynhardt (Stratum Research Group)

Evaluates the discrete Gardner (extended KdV) lattice flow:
    du_n/dt = - [ alpha * u_n + beta * u_n^2 ] * (u_{n+1} - u_{n-1}) / 2 
              - delta * (u_{n+2} - 2 u_{n+1} + 2 u_{n-1} - u_{n-2}) / 2
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_u = 2.0 / (1.0 - ||u_n||^2)
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_gardner_kernel(
    u_ptr,           # [N] field displacement
    out_a_ptr,       # [N] output acceleration / rate of change
    out_metric_ptr,  # [N] conformal metric factor
    alpha: tl.constexpr,
    beta: tl.constexpr,
    delta: tl.constexpr,
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N

    idx_p1 = (idx + 1) % N
    idx_p2 = (idx + 2) % N
    idx_m1 = (idx - 1 + N) % N
    idx_m2 = (idx - 2 + N) % N

    u_curr = tl.load(u_ptr + idx, mask=mask, other=0.0)
    u_p1   = tl.load(u_ptr + idx_p1, mask=mask, other=0.0)
    u_p2   = tl.load(u_ptr + idx_p2, mask=mask, other=0.0)
    u_m1   = tl.load(u_ptr + idx_m1, mask=mask, other=0.0)
    u_m2   = tl.load(u_ptr + idx_m2, mask=mask, other=0.0)

    # Nonlinear advection with mixed quadratic & cubic terms: (alpha * u + beta * u^2) * (u_{n+1} - u_{n-1}) / 2
    flux_coeff = alpha * u_curr + beta * (u_curr * u_curr)
    advect = 0.5 * flux_coeff * (u_p1 - u_m1)

    # 3rd-order spatial dispersion: delta * (u_{n+2} - 2 u_{n+1} + 2 u_{n-1} - u_{n-2}) / 2
    disp = 0.5 * delta * (u_p2 - 2.0 * u_p1 + 2.0 * u_m1 - u_m2)

    accel = - advect - disp

    # Poincaré hyperbolic metric scaling
    u_sq = u_curr * u_curr
    u_clamped = tl.minimum(u_sq, 0.99)
    lambda_u = 2.0 / (1.0 - u_clamped)

    a_poincare = accel / (lambda_u * lambda_u)

    tl.store(out_a_ptr + idx, a_poincare, mask=mask)
    tl.store(out_metric_ptr + idx, lambda_u, mask=mask)


def poincare_discrete_gardner_triton(
    u: torch.Tensor,
    alpha: float = 6.0,
    beta: float = -6.0,
    delta: float = 1.0
) -> tuple[torch.Tensor, torch.Tensor]:
    N = u.numel()
    out_a = torch.empty_like(u)
    out_metric = torch.empty_like(u)

    BLOCK_SIZE = 256
    grid = (triton.cdiv(N, BLOCK_SIZE),)

    _poincare_discrete_gardner_kernel[grid](
        u, out_a, out_metric,
        alpha=alpha, beta=beta, delta=delta,
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_a, out_metric


def poincare_discrete_gardner_pytorch(
    u: torch.Tensor,
    alpha: float = 6.0,
    beta: float = -6.0,
    delta: float = 1.0
) -> tuple[torch.Tensor, torch.Tensor]:
    u_p1 = torch.roll(u, -1, dims=0)
    u_p2 = torch.roll(u, -2, dims=0)
    u_m1 = torch.roll(u, 1, dims=0)
    u_m2 = torch.roll(u, 2, dims=0)

    flux_coeff = alpha * u + beta * (u * u)
    advect = 0.5 * flux_coeff * (u_p1 - u_m1)
    disp = 0.5 * delta * (u_p2 - 2.0 * u_p1 + 2.0 * u_m1 - u_m2)
    accel = - advect - disp

    u_sq = u * u
    u_clamped = torch.clamp(u_sq, max=0.99)
    lambda_u = 2.0 / (1.0 - u_clamped)
    a_poincare = accel / (lambda_u * lambda_u)

    return a_poincare, lambda_u


def benchmark():
    if not torch.cuda.is_available():
        print("CUDA not available.")
        return

    device = torch.device("cuda:0")
    N = 131072
    u = torch.randn(N, device=device, dtype=torch.float32) * 0.3

    for _ in range(20):
        a_tri, m_tri = poincare_discrete_gardner_triton(u)
        a_pt, m_pt = poincare_discrete_gardner_pytorch(u)
    torch.cuda.synchronize()

    max_err_a = torch.max(torch.abs(a_tri - a_pt)).item()
    max_err_m = torch.max(torch.abs(m_tri - m_pt)).item()
    assert max_err_a < 1e-4, f"Accel error: {max_err_a}"
    assert max_err_m < 1e-4, f"Metric error: {max_err_m}"

    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_discrete_gardner_pytorch(u)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1e6

    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_discrete_gardner_triton(u)
    torch.cuda.synchronize()
    t_tri = (time.perf_counter() - t0) / iters * 1e6

    speedup = t_pt / t_tri
    throughput = (N / (t_tri * 1e-6)) / 1e6

    print(f"=== Cycle 276: Poincaré Discrete Gardner (Extended KdV) Flow ===")
    print(f"Hardware Target: {torch.cuda.get_device_name(0)}")
    print(f"Lattice Size: {N:,} nodes")
    print(f"PyTorch Time: {t_pt:.2f} μs | Triton Time: {t_tri:.2f} μs")
    print(f"Speedup: {speedup:.2f}x | Throughput: {throughput:,.2f} M nodes/s")
    print(f"Max Abs Error: {max_err_a:.2e} (accel), {max_err_m:.2e} (metric)")
    print(f"Verification: PASSED (< 1e-4)")

if __name__ == "__main__":
    benchmark()
