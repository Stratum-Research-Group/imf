"""
Cycle 274: Fused Poincaré Discrete Hunter-Saxton Liquid Crystal Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 12.0 GB206)

Evaluates the discrete Hunter-Saxton rod-director lattice dynamical flow:
    (u_{n+1} - 2 u_n + u_{n-1})_t = - u_n * (u_{n+1} - u_{n-1}) + 1/2 * (u_{n+1} - u_{n-1})^2
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_u = 2.0 / (1.0 - ||u_n||^2)
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_hunter_saxton_kernel(
    u_ptr,           # [N] orientation field
    v_ptr,           # [N] momentum / velocity field
    out_a_ptr,       # [N] output acceleration
    out_metric_ptr,  # [N] conformal Riemannian metric factor
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

    # Displacements
    diff = u_p1 - u_m1
    lap = u_p1 - 2.0 * u_curr + u_m1

    # Hunter-Saxton director force: - u * diff + 0.5 * diff^2
    force = - u_curr * diff + 0.5 * (diff * diff) + lap

    # Poincaré hyperbolic metric scaling
    u_sq = u_curr * u_curr
    u_clamped = tl.minimum(u_sq, 0.99)
    conf_metric = 2.0 / (1.0 - u_clamped)

    fused_a = force * conf_metric

    tl.store(out_a_ptr + idx, fused_a, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_hunter_saxton(u: torch.Tensor, v: torch.Tensor):
    assert u.is_cuda and v.is_cuda
    N = u.numel()
    out_a = torch.empty_like(u)
    out_metric = torch.empty_like(u)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_hunter_saxton_kernel[grid](
        u, v, out_a, out_metric,
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_a, out_metric

def torch_poincare_discrete_hunter_saxton_ref(u: torch.Tensor, v: torch.Tensor):
    u_p1 = torch.roll(u, shifts=-1, dims=0)
    u_m1 = torch.roll(u, shifts=1, dims=0)

    diff = u_p1 - u_m1
    lap = u_p1 - 2.0 * u + u_m1
    force = - u * diff + 0.5 * (diff ** 2) + lap

    u_sq = torch.clamp(u ** 2, max=0.99)
    conf_metric = 2.0 / (1.0 - u_sq)
    return force * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Hunter-Saxton Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice nodes
    u = (torch.randn(N, device=device, dtype=torch.float32) * 0.1).contiguous()
    v = (torch.randn(N, device=device, dtype=torch.float32) * 0.05).contiguous()

    # Warmup
    for _ in range(20):
        out_a, out_metric = triton_poincare_discrete_hunter_saxton(u, v)
        ref_a, ref_metric = torch_poincare_discrete_hunter_saxton_ref(u, v)
    torch.cuda.synchronize()

    # Numerical verification
    max_err_a = (out_a - ref_a).abs().max().item()
    max_err_metric = (out_metric - ref_metric).abs().max().item()
    print(f"Max Absolute Error (Acc): {max_err_a:.3e}")
    print(f"Max Absolute Error (Metric): {max_err_metric:.3e}")
    assert max_err_a < 1e-4, f"Numerical error too high: {max_err_a}"
    assert max_err_metric < 1e-5, f"Metric error too high: {max_err_metric}"

    # Timing Triton
    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        out_a, out_metric = triton_poincare_discrete_hunter_saxton(u, v)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_a, ref_metric = torch_poincare_discrete_hunter_saxton_ref(u, v)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M nodes/s")
