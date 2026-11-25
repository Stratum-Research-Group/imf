"""
Cycle 266: Fused Poincaré Discrete Volterra-Lotka Prey-Predator Lattice Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 12.0 GB206)

Evaluates the discrete Volterra-Lotka ecological lattice dynamical flow:
    d N_n / dt = N_n * ( (N_{n+1} - N_{n-1}) + epsilon * N_n * (N_{n+1} + N_{n-1}) )
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_N = 2.0 / (1.0 - ||N_n||^2)
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_volterra_lotka_kernel(
    n_ptr,           # [N] population densities
    out_dn_ptr,      # [N] output growth rates
    out_metric_ptr,  # [N] conformal metric factor
    epsilon,         # quadratic correction parameter
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N

    idx_p1 = (idx + 1) % N
    idx_m1 = (idx - 1 + N) % N

    n_curr = tl.load(n_ptr + idx, mask=mask, other=0.0)
    n_p1   = tl.load(n_ptr + idx_p1, mask=mask, other=0.0)
    n_m1   = tl.load(n_ptr + idx_m1, mask=mask, other=0.0)

    # Volterra-Lotka competitive convective flux
    linear_comp = n_p1 - n_m1
    quad_comp = epsilon * n_curr * (n_p1 + n_m1)
    growth_rate = n_curr * (linear_comp + quad_comp)

    # Poincaré hyperbolic metric conformal factor
    n_sq = n_curr * n_curr
    n_clamped = tl.minimum(n_sq, 0.99)
    conf_metric = 2.0 / (1.0 - n_clamped)

    fused_dn = growth_rate * conf_metric

    tl.store(out_dn_ptr + idx, fused_dn, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_volterra_lotka(n_pop: torch.Tensor, epsilon: float = 0.2):
    assert n_pop.is_cuda
    N = n_pop.numel()
    out_dn = torch.empty_like(n_pop)
    out_metric = torch.empty_like(n_pop)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_volterra_lotka_kernel[grid](
        n_pop, out_dn, out_metric,
        float(epsilon),
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_dn, out_metric

def torch_poincare_discrete_volterra_lotka_ref(n_pop: torch.Tensor, epsilon: float = 0.2):
    n_p1 = torch.roll(n_pop, shifts=-1, dims=0)
    n_m1 = torch.roll(n_pop, shifts=1, dims=0)

    linear_comp = n_p1 - n_m1
    quad_comp = epsilon * n_pop * (n_p1 + n_m1)
    growth_rate = n_pop * (linear_comp + quad_comp)

    n_sq = torch.clamp(n_pop ** 2, max=0.99)
    conf_metric = 2.0 / (1.0 - n_sq)
    return growth_rate * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Volterra-Lotka Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice nodes
    n_pop = (torch.rand(N, device=device, dtype=torch.float32) * 0.2 + 0.05).contiguous()

    # Warmup
    for _ in range(20):
        out_dn, out_metric = triton_poincare_discrete_volterra_lotka(n_pop)
        ref_dn, ref_metric = torch_poincare_discrete_volterra_lotka_ref(n_pop)
    torch.cuda.synchronize()

    # Numerical verification
    max_err_dn = (out_dn - ref_dn).abs().max().item()
    max_err_metric = (out_metric - ref_metric).abs().max().item()
    print(f"Max Absolute Error (dn): {max_err_dn:.3e}")
    print(f"Max Absolute Error (Metric): {max_err_metric:.3e}")
    assert max_err_dn < 1e-4, f"Numerical error too high: {max_err_dn}"
    assert max_err_metric < 1e-5, f"Metric error too high: {max_err_metric}"

    # Timing Triton
    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        out_dn, out_metric = triton_poincare_discrete_volterra_lotka(n_pop)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_dn, ref_metric = torch_poincare_discrete_volterra_lotka_ref(n_pop)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M nodes/s")
