"""
Cycle 271: Fused Poincaré Discrete Novikov Cubic Peakon Lattice Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 8.9 AD106)

Evaluates the discrete Novikov cubic peakon lattice dynamical flow:
    m_n = u_n - alpha * (u_{n+1} - 2 u_n + u_{n-1})
    d m_n / dt = - u_n^2 * (m_{n+1} - m_{n-1}) - 3 * u_n * m_n * (u_{n+1} - u_{n-1})
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_u = 2.0 / (1.0 - ||u_n||^2)
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_novikov_kernel(
    u_ptr,           # [N] velocity field
    m_ptr,           # [N] momentum density
    out_dm_ptr,      # [N] output time derivative of momentum
    out_metric_ptr,  # [N] conformal metric factor
    alpha,           # Helmholtz dispersion scale parameter
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

    # Novikov cubic peakon advective dynamics: - u^2 * (m_{p1} - m_{m1}) - 3 * u * m * (u_{p1} - u_{m1})
    diff_m = m_p1 - m_m1
    diff_u = u_p1 - u_m1
    u_sq = u_curr * u_curr

    dm = - u_sq * diff_m - 3.0 * u_curr * m_curr * diff_u

    # Conformal hyperbolic metric factor
    u_clamped = tl.minimum(u_sq, 0.99)
    conf_metric = 2.0 / (1.0 - u_clamped)

    fused_dm = dm * conf_metric

    tl.store(out_dm_ptr + idx, fused_dm, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_novikov(u: torch.Tensor, m: torch.Tensor, alpha: float = 1.0):
    assert u.is_cuda and m.is_cuda
    N = u.numel()
    out_dm = torch.empty_like(m)
    out_metric = torch.empty_like(u)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_novikov_kernel[grid](
        u, m, out_dm, out_metric,
        float(alpha),
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_dm, out_metric

def torch_poincare_discrete_novikov_ref(u: torch.Tensor, m: torch.Tensor, alpha: float = 1.0):
    u_p1 = torch.roll(u, shifts=-1, dims=0)
    u_m1 = torch.roll(u, shifts=1, dims=0)
    m_p1 = torch.roll(m, shifts=-1, dims=0)
    m_m1 = torch.roll(m, shifts=1, dims=0)

    u_sq = u ** 2
    dm = - u_sq * (m_p1 - m_m1) - 3.0 * u * m * (u_p1 - u_m1)
    u_clamped = torch.clamp(u_sq, max=0.99)
    conf_metric = 2.0 / (1.0 - u_clamped)
    return dm * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Novikov Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice nodes
    u = (torch.randn(N, device=device, dtype=torch.float32) * 0.1).contiguous()
    u_p1 = torch.roll(u, shifts=-1, dims=0)
    u_m1 = torch.roll(u, shifts=1, dims=0)
    m = (u - 1.0 * (u_p1 - 2.0 * u + u_m1)).contiguous()

    # Warmup
    for _ in range(20):
        out_dm, out_metric = triton_poincare_discrete_novikov(u, m)
        ref_dm, ref_metric = torch_poincare_discrete_novikov_ref(u, m)
    torch.cuda.synchronize()

    # Numerical verification
    max_err_dm = (out_dm - ref_dm).abs().max().item()
    max_err_metric = (out_metric - ref_metric).abs().max().item()
    print(f"Max Absolute Error (dm): {max_err_dm:.3e}")
    print(f"Max Absolute Error (Metric): {max_err_metric:.3e}")
    assert max_err_dm < 1e-4, f"Numerical error too high: {max_err_dm}"
    assert max_err_metric < 1e-5, f"Metric error too high: {max_err_metric}"

    # Timing Triton
    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        out_dm, out_metric = triton_poincare_discrete_novikov(u, m)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_dm, ref_metric = torch_poincare_discrete_novikov_ref(u, m)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M nodes/s")
