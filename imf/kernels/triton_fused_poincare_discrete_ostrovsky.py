"""
Cycle 275: Fused Poincaré Discrete Ostrovsky Oceanic Internal Soliton Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 12.0 GB206)

Evaluates the discrete Ostrovsky ocean lattice dynamical flow:
    (u_t + c_0 u_x + alpha u u_x + beta u_{xxx})_x = gamma u
Discrete lattice Hamiltonian equations for oceanic internal waves with Coriolis rotation:
    du_n/dt = v_n
    dv_n/dt = - alpha * u_n * (u_{n+1} - u_{n-1}) / 2 
              - beta * (u_{n+2} - 2 u_{n+1} + 2 u_{n-1} - u_{n-2}) / 2
              + gamma * (u_{n+1} - 2 u_n + u_{n-1})
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_u = 2.0 / (1.0 - ||u_n||^2)
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_ostrovsky_kernel(
    u_ptr,           # [N] surface/interface displacement field
    v_ptr,           # [N] velocity / momentum field
    out_a_ptr,       # [N] output acceleration
    out_metric_ptr,  # [N] conformal Riemannian metric factor
    alpha: tl.constexpr,
    beta: tl.constexpr,
    gamma: tl.constexpr,
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

    # 1. Nonlinear advective flux: alpha * u * (u_{n+1} - u_{n-1}) / 2
    advect = 0.5 * alpha * u_curr * (u_p1 - u_m1)

    # 2. Third-order KdV-type dispersion: beta * (u_{n+2} - 2 u_{n+1} + 2 u_{n-1} - u_{n-2}) / 2
    disp = 0.5 * beta * (u_p2 - 2.0 * u_p1 + 2.0 * u_m1 - u_m2)

    # 3. Ostrovsky rotation (Coriolis) restoring force: gamma * (u_{n+1} - 2 u_n + u_{n-1})
    coriolis = gamma * (u_p1 - 2.0 * u_curr + u_m1)

    accel = - advect - disp + coriolis

    # Poincaré hyperbolic metric scaling: lambda_u = 2 / (1 - ||u||^2)
    u_sq = u_curr * u_curr
    u_clamped = tl.minimum(u_sq, 0.99)
    lambda_u = 2.0 / (1.0 - u_clamped)

    # Symplectic conformal hyperbolic acceleration
    a_poincare = accel / (lambda_u * lambda_u)

    tl.store(out_a_ptr + idx, a_poincare, mask=mask)
    tl.store(out_metric_ptr + idx, lambda_u, mask=mask)


def poincare_discrete_ostrovsky_triton(
    u: torch.Tensor,
    v: torch.Tensor,
    alpha: float = 1.0,
    beta: float = 0.1,
    gamma: float = 0.05
) -> tuple[torch.Tensor, torch.Tensor]:
    """Fused Triton kernel evaluating Poincaré Discrete Ostrovsky Ocean Soliton Flow."""
    N = u.numel()
    out_a = torch.empty_like(u)
    out_metric = torch.empty_like(u)

    BLOCK_SIZE = 256
    grid = (triton.cdiv(N, BLOCK_SIZE),)

    _poincare_discrete_ostrovsky_kernel[grid](
        u, v, out_a, out_metric,
        alpha=alpha, beta=beta, gamma=gamma,
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_a, out_metric


def poincare_discrete_ostrovsky_pytorch(
    u: torch.Tensor,
    v: torch.Tensor,
    alpha: float = 1.0,
    beta: float = 0.1,
    gamma: float = 0.05
) -> tuple[torch.Tensor, torch.Tensor]:
    """Pure PyTorch baseline for verification."""
    u_p1 = torch.roll(u, -1, dims=0)
    u_p2 = torch.roll(u, -2, dims=0)
    u_m1 = torch.roll(u, 1, dims=0)
    u_m2 = torch.roll(u, 2, dims=0)

    advect = 0.5 * alpha * u * (u_p1 - u_m1)
    disp = 0.5 * beta * (u_p2 - 2.0 * u_p1 + 2.0 * u_m1 - u_m2)
    coriolis = gamma * (u_p1 - 2.0 * u + u_m1)

    accel = - advect - disp + coriolis

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
    N = 131072  # 128K lattice nodes
    u = torch.randn(N, device=device, dtype=torch.float32) * 0.4
    v = torch.randn(N, device=device, dtype=torch.float32) * 0.1

    # Warmup
    for _ in range(20):
        a_tri, m_tri = poincare_discrete_ostrovsky_triton(u, v)
        a_pt, m_pt = poincare_discrete_ostrovsky_pytorch(u, v)
    torch.cuda.synchronize()

    # Numerical accuracy check
    max_err_a = torch.max(torch.abs(a_tri - a_pt)).item()
    max_err_m = torch.max(torch.abs(m_tri - m_pt)).item()
    assert max_err_a < 1e-4, f"Acceleration error too high: {max_err_a}"
    assert max_err_m < 1e-4, f"Metric error too high: {max_err_m}"

    # Benchmark PyTorch
    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_discrete_ostrovsky_pytorch(u, v)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1e6

    # Benchmark Triton
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_discrete_ostrovsky_triton(u, v)
    torch.cuda.synchronize()
    t_tri = (time.perf_counter() - t0) / iters * 1e6

    speedup = t_pt / t_tri
    throughput = (N / (t_tri * 1e-6)) / 1e6

    print(f"=== Cycle 275: Poincaré Discrete Ostrovsky Oceanic Soliton Flow ===")
    print(f"Hardware Target: {torch.cuda.get_device_name(0)}")
    print(f"Lattice Size: {N:,} nodes")
    print(f"PyTorch Time: {t_pt:.2f} μs | Triton Time: {t_tri:.2f} μs")
    print(f"Speedup: {speedup:.2f}x | Throughput: {throughput:,.2f} M nodes/s")
    print(f"Max Abs Error: {max_err_a:.2e} (accel), {max_err_m:.2e} (metric)")
    print(f"Verification: PASSED (< 1e-4)")

if __name__ == "__main__":
    benchmark()
