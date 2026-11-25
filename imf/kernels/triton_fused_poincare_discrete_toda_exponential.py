"""
Cycle 264: Fused Poincaré Discrete Toda Lattice Exponential Soliton Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 8.9 AD106)

Evaluates the discrete Toda exponential lattice dynamical flow:
    d^2 q_n / dt^2 = exp( - (q_n - q_{n-1}) ) - exp( - (q_{n+1} - q_n) )
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_q = 2.0 / (1.0 - ||q_n||^2)
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_toda_kernel(
    q_ptr,           # [N] particle positions
    p_ptr,           # [N] particle momenta
    out_a_ptr,       # [N] output acceleration
    out_metric_ptr,  # [N] conformal metric factor
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N

    idx_p1 = (idx + 1) % N
    idx_m1 = (idx - 1 + N) % N

    q_curr = tl.load(q_ptr + idx, mask=mask, other=0.0)
    q_p1   = tl.load(q_ptr + idx_p1, mask=mask, other=0.0)
    q_m1   = tl.load(q_ptr + idx_m1, mask=mask, other=0.0)

    # Toda exponential restoring forces: exp(-(q_n - q_{n-1})) - exp(-(q_{n+1} - q_n))
    diff_m = q_curr - q_m1
    diff_p = q_p1 - q_curr

    # Clamp diffs for numerical safety in exp
    diff_m_clamped = tl.maximum(tl.minimum(diff_m, 10.0), -10.0)
    diff_p_clamped = tl.maximum(tl.minimum(diff_p, 10.0), -10.0)

    force_m = tl.exp(-diff_m_clamped)
    force_p = tl.exp(-diff_p_clamped)

    acc = force_m - force_p

    # Poincaré hyperbolic metric conformal factor
    q_sq = q_curr * q_curr
    q_clamped = tl.minimum(q_sq, 0.99)
    conf_metric = 2.0 / (1.0 - q_clamped)

    fused_acc = acc * conf_metric

    tl.store(out_a_ptr + idx, fused_acc, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_toda(q: torch.Tensor, p: torch.Tensor):
    assert q.is_cuda and p.is_cuda
    N = q.numel()
    out_a = torch.empty_like(q)
    out_metric = torch.empty_like(q)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_toda_kernel[grid](
        q, p, out_a, out_metric,
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_a, out_metric

def torch_poincare_discrete_toda_ref(q: torch.Tensor, p: torch.Tensor):
    q_p1 = torch.roll(q, shifts=-1, dims=0)
    q_m1 = torch.roll(q, shifts=1, dims=0)

    diff_m = torch.clamp(q - q_m1, min=-10.0, max=10.0)
    diff_p = torch.clamp(q_p1 - q, min=-10.0, max=10.0)

    acc = torch.exp(-diff_m) - torch.exp(-diff_p)
    q_sq = torch.clamp(q ** 2, max=0.99)
    conf_metric = 2.0 / (1.0 - q_sq)
    return acc * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Toda Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice particles
    q = (torch.randn(N, device=device, dtype=torch.float32) * 0.1).contiguous()
    p = (torch.randn(N, device=device, dtype=torch.float32) * 0.05).contiguous()

    # Warmup
    for _ in range(20):
        out_a, out_metric = triton_poincare_discrete_toda(q, p)
        ref_a, ref_metric = torch_poincare_discrete_toda_ref(q, p)
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
        out_a, out_metric = triton_poincare_discrete_toda(q, p)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_a, ref_metric = torch_poincare_discrete_toda_ref(q, p)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M particles/s")
