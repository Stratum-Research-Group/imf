"""
Cycle 279: Fused Poincaré Discrete Sine-Gordon-Toda Hybrid Lattice Flow
Hardware Target: AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9
Author: Nicholas Charles Mynhardt (Stratum Research Group)

Evaluates the discrete Sine-Gordon-Toda hybrid lattice dynamical flow:
    d^2 u_n / dt^2 = e^{u_{n+1} - u_n} - e^{u_n - u_{n-1}} - sin(u_n)
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_u = 2.0 / (1.0 - ||u_n||^2)
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_sine_gordon_toda_kernel(
    u_ptr,           # [N] field displacement
    v_ptr,           # [N] velocity / momentum
    out_a_ptr,       # [N] acceleration output
    out_metric_ptr,  # [N] metric conformal factor
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

    # Toda exponential spring force: e^{u_{n+1} - u_n} - e^{u_n - u_{n-1}}
    # Clamp exponent to prevent register overflow
    diff_p1 = tl.maximum(tl.minimum(u_p1 - u_curr, 8.0), -8.0)
    diff_m1 = tl.maximum(tl.minimum(u_curr - u_m1, 8.0), -8.0)
    force_toda = tl.exp(diff_p1) - tl.exp(diff_m1)

    # Sine-Gordon pinning potential force: - sin(u_n)
    force_sg = - tl.sin(u_curr)

    accel = force_toda + force_sg

    # Poincaré hyperbolic metric scaling: lambda = 2 / (1 - ||u||^2)
    u_sq = u_curr * u_curr
    u_clamped = tl.minimum(u_sq, 0.99)
    lambda_u = 2.0 / (1.0 - u_clamped)

    a_poincare = accel / (lambda_u * lambda_u)

    tl.store(out_a_ptr + idx, a_poincare, mask=mask)
    tl.store(out_metric_ptr + idx, lambda_u, mask=mask)


def poincare_discrete_sine_gordon_toda_triton(
    u: torch.Tensor,
    v: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    N = u.numel()
    out_a = torch.empty_like(u)
    out_metric = torch.empty_like(u)

    BLOCK_SIZE = 256
    grid = (triton.cdiv(N, BLOCK_SIZE),)

    _poincare_discrete_sine_gordon_toda_kernel[grid](
        u, v, out_a, out_metric,
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_a, out_metric


def poincare_discrete_sine_gordon_toda_pytorch(
    u: torch.Tensor,
    v: torch.Tensor
) -> tuple[torch.Tensor, torch.Tensor]:
    u_p1 = torch.roll(u, -1, dims=0)
    u_m1 = torch.roll(u, 1, dims=0)

    diff_p1 = torch.clamp(u_p1 - u, min=-8.0, max=8.0)
    diff_m1 = torch.clamp(u - u_m1, min=-8.0, max=8.0)
    force_toda = torch.exp(diff_p1) - torch.exp(diff_m1)
    force_sg = - torch.sin(u)

    accel = force_toda + force_sg

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
    v = torch.randn(N, device=device, dtype=torch.float32) * 0.1

    # Warmup
    for _ in range(20):
        a_tri, m_tri = poincare_discrete_sine_gordon_toda_triton(u, v)
        a_pt, m_pt = poincare_discrete_sine_gordon_toda_pytorch(u, v)
    torch.cuda.synchronize()

    max_err_a = torch.max(torch.abs(a_tri - a_pt)).item()
    max_err_m = torch.max(torch.abs(m_tri - m_pt)).item()
    assert max_err_a < 1e-4, f"Accel error: {max_err_a}"
    assert max_err_m < 1e-4, f"Metric error: {max_err_m}"

    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_discrete_sine_gordon_toda_pytorch(u, v)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1e6

    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_discrete_sine_gordon_toda_triton(u, v)
    torch.cuda.synchronize()
    t_tri = (time.perf_counter() - t0) / iters * 1e6

    speedup = t_pt / t_tri
    throughput = (N / (t_tri * 1e-6)) / 1e6

    print(f"=== Cycle 279: Poincaré Discrete Sine-Gordon-Toda Flow ===")
    print(f"Hardware Target: {torch.cuda.get_device_name(0)}")
    print(f"Lattice Size: {N:,} nodes")
    print(f"PyTorch Time: {t_pt:.2f} μs | Triton Time: {t_tri:.2f} μs")
    print(f"Speedup: {speedup:.2f}x | Throughput: {throughput:,.2f} M nodes/s")
    print(f"Max Abs Error: {max_err_a:.2e} (accel), {max_err_m:.2e} (metric)")
    print(f"Verification: PASSED (< 1e-4)")

if __name__ == "__main__":
    benchmark()
