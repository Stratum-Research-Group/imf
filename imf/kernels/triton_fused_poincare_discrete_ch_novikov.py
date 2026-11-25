"""
Cycle 280: Fused Poincaré Discrete Camassa-Holm-Novikov Dual Peakon Flow
Hardware Target: AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9
Author: Nicholas Charles Mynhardt (Stratum Research Group)

Evaluates the discrete Camassa-Holm-Novikov dual peakon dynamical flow:
    m_n = u_n - alpha * (u_{n+1} - 2 u_n + u_{n-1})
    dm_n/dt = - [ u_n * (m_{n+1} - m_{n-1}) + 2 * m_n * (u_{n+1} - u_{n-1}) ] / 2
              - [ u_n^2 * (m_{n+1} - m_{n-1}) + 3 * u_n * m_n * (u_{n+1} - u_{n-1}) ] / 2
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_u = 2.0 / (1.0 - ||u_n||^2)
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_ch_novikov_kernel(
    u_ptr,           # [N] field displacement
    m_ptr,           # [N] Helmholtz momentum density
    out_dm_ptr,      # [N] rate of change dm/dt
    out_metric_ptr,  # [N] conformal factor
    alpha: tl.constexpr,
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N

    idx_p1 = (idx + 1) % N
    idx_m1 = (idx - 1 + N) % N

    u_curr = tl.load(u_ptr + idx, mask=mask, other=0.0)
    u_p1   = tl.load(u_ptr + idx_p1, mask=mask, other=0.0)
    u_m1   = tl.load(u_ptr + idx_m1, mask=mask, other=0.0)

    m_curr = tl.load(m_ptr + idx, mask=mask, other=0.0)
    m_p1   = tl.load(m_ptr + idx_p1, mask=mask, other=0.0)
    m_m1   = tl.load(m_ptr + idx_m1, mask=mask, other=0.0)

    # Displacements
    u_diff = u_p1 - u_m1
    m_diff = m_p1 - m_m1

    # 1. Quadratic Camassa-Holm advective flux: - [u * dm + 2 * m * du] / 2
    flux_ch = - 0.5 * (u_curr * m_diff + 2.0 * m_curr * u_diff)

    # 2. Cubic Novikov interaction flux: - [u^2 * dm + 3 * u * m * du] / 2
    u_sq = u_curr * u_curr
    flux_novikov = - 0.5 * (u_sq * m_diff + 3.0 * u_curr * m_curr * u_diff)

    accel = flux_ch + flux_novikov

    # Poincaré hyperbolic metric scaling: lambda = 2 / (1 - ||u||^2)
    u_clamped = tl.minimum(u_sq, 0.99)
    lambda_u = 2.0 / (1.0 - u_clamped)

    dm_poincare = accel / (lambda_u * lambda_u)

    tl.store(out_dm_ptr + idx, dm_poincare, mask=mask)
    tl.store(out_metric_ptr + idx, lambda_u, mask=mask)


def poincare_discrete_ch_novikov_triton(
    u: torch.Tensor,
    m: torch.Tensor,
    alpha: float = 0.5
) -> tuple[torch.Tensor, torch.Tensor]:
    N = u.numel()
    out_dm = torch.empty_like(m)
    out_metric = torch.empty_like(u)

    BLOCK_SIZE = 256
    grid = (triton.cdiv(N, BLOCK_SIZE),)

    _poincare_discrete_ch_novikov_kernel[grid](
        u, m, out_dm, out_metric,
        alpha=alpha, N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_dm, out_metric


def poincare_discrete_ch_novikov_pytorch(
    u: torch.Tensor,
    m: torch.Tensor,
    alpha: float = 0.5
) -> tuple[torch.Tensor, torch.Tensor]:
    u_p1 = torch.roll(u, -1, dims=0)
    u_m1 = torch.roll(u, 1, dims=0)
    m_p1 = torch.roll(m, -1, dims=0)
    m_m1 = torch.roll(m, 1, dims=0)

    u_diff = u_p1 - u_m1
    m_diff = m_p1 - m_m1

    flux_ch = - 0.5 * (u * m_diff + 2.0 * m * u_diff)
    u_sq = u * u
    flux_novikov = - 0.5 * (u_sq * m_diff + 3.0 * u * m * u_diff)
    accel = flux_ch + flux_novikov

    u_clamped = torch.clamp(u_sq, max=0.99)
    lambda_u = 2.0 / (1.0 - u_clamped)
    dm_poincare = accel / (lambda_u * lambda_u)

    return dm_poincare, lambda_u


def benchmark():
    if not torch.cuda.is_available():
        print("CUDA not available.")
        return

    device = torch.device("cuda:0")
    N = 131072
    u = torch.randn(N, device=device, dtype=torch.float32) * 0.3
    # Helmholtz momentum density: m = u - alpha * Delta u
    u_p1 = torch.roll(u, -1, dims=0)
    u_m1 = torch.roll(u, 1, dims=0)
    m = u - 0.5 * (u_p1 - 2.0 * u + u_m1)

    # Warmup
    for _ in range(20):
        dm_tri, met_tri = poincare_discrete_ch_novikov_triton(u, m)
        dm_pt, met_pt = poincare_discrete_ch_novikov_pytorch(u, m)
    torch.cuda.synchronize()

    max_err_dm = torch.max(torch.abs(dm_tri - dm_pt)).item()
    max_err_m  = torch.max(torch.abs(met_tri - met_pt)).item()
    assert max_err_dm < 1e-4, f"dm error: {max_err_dm}"
    assert max_err_m < 1e-4, f"metric error: {max_err_m}"

    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_discrete_ch_novikov_pytorch(u, m)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1e6

    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_discrete_ch_novikov_triton(u, m)
    torch.cuda.synchronize()
    t_tri = (time.perf_counter() - t0) / iters * 1e6

    speedup = t_pt / t_tri
    throughput = (N / (t_tri * 1e-6)) / 1e6

    print(f"=== Cycle 280: Poincaré Discrete Camassa-Holm-Novikov Dual Peakon Flow ===")
    print(f"Hardware Target: {torch.cuda.get_device_name(0)}")
    print(f"Lattice Size: {N:,} nodes")
    print(f"PyTorch Time: {t_pt:.2f} μs | Triton Time: {t_tri:.2f} μs")
    print(f"Speedup: {speedup:.2f}x | Throughput: {throughput:,.2f} M nodes/s")
    print(f"Max Abs Error: {max_err_dm:.2e} (dm/dt), {max_err_m:.2e} (metric)")
    print(f"Verification: PASSED (< 1e-4)")

if __name__ == "__main__":
    benchmark()
