"""
Cycle 267: Fused Poincaré Discrete Belov-Chaltikian Lattice Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 8.9 AD106)

Evaluates the discrete Belov-Chaltikian 2-component lattice dynamical flow:
    d u_n / dt = u_n * (u_{n+1} - u_{n-1}) + v_{n+1} - v_n
    d v_n / dt = v_n * (u_n - u_{n-1})
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda = 2.0 / (1.0 - (||u_n||^2 + ||v_n||^2))
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_belov_chaltikian_kernel(
    u_ptr, v_ptr,
    out_du_ptr, out_dv_ptr,
    out_metric_ptr,
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

    v_curr = tl.load(v_ptr + idx, mask=mask, other=0.0)
    v_p1   = tl.load(v_ptr + idx_p1, mask=mask, other=0.0)

    # Hydrodynamic discrete convective updates
    du = u_curr * (u_p1 - u_m1) + (v_p1 - v_curr)
    dv = v_curr * (u_curr - u_m1)

    # Conformal metric factor
    tot_sq = u_curr * u_curr + v_curr * v_curr
    clamped_sq = tl.minimum(tot_sq, 0.99)
    conf_metric = 2.0 / (1.0 - clamped_sq)

    tl.store(out_du_ptr + idx, du * conf_metric, mask=mask)
    tl.store(out_dv_ptr + idx, dv * conf_metric, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_belov_chaltikian(u: torch.Tensor, v: torch.Tensor):
    assert u.is_cuda and v.is_cuda
    N = u.numel()
    out_du = torch.empty_like(u)
    out_dv = torch.empty_like(v)
    out_metric = torch.empty_like(u)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_belov_chaltikian_kernel[grid](
        u, v, out_du, out_dv, out_metric,
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_du, out_dv, out_metric

def torch_poincare_discrete_belov_chaltikian_ref(u: torch.Tensor, v: torch.Tensor):
    u_p1 = torch.roll(u, shifts=-1, dims=0)
    u_m1 = torch.roll(u, shifts=1, dims=0)
    v_p1 = torch.roll(v, shifts=-1, dims=0)

    du = u * (u_p1 - u_m1) + (v_p1 - v)
    dv = v * (u - u_m1)

    tot_sq = torch.clamp(u ** 2 + v ** 2, max=0.99)
    conf_metric = 2.0 / (1.0 - tot_sq)
    return du * conf_metric, dv * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Belov-Chaltikian Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice nodes
    u = (torch.randn(N, device=device, dtype=torch.float32) * 0.1).contiguous()
    v = (torch.randn(N, device=device, dtype=torch.float32) * 0.1).contiguous()

    # Warmup
    for _ in range(20):
        out_du, out_dv, out_metric = triton_poincare_discrete_belov_chaltikian(u, v)
        ref_du, ref_dv, ref_metric = torch_poincare_discrete_belov_chaltikian_ref(u, v)
    torch.cuda.synchronize()

    # Numerical verification
    max_err_du = (out_du - ref_du).abs().max().item()
    max_err_dv = (out_dv - ref_dv).abs().max().item()
    max_err_metric = (out_metric - ref_metric).abs().max().item()
    print(f"Max Absolute Error (du): {max_err_du:.3e}")
    print(f"Max Absolute Error (dv): {max_err_dv:.3e}")
    print(f"Max Absolute Error (Metric): {max_err_metric:.3e}")
    assert max_err_du < 1e-4, f"Numerical error too high: {max_err_du}"
    assert max_err_dv < 1e-4, f"Numerical error too high: {max_err_dv}"
    assert max_err_metric < 1e-5, f"Metric error too high: {max_err_metric}"

    # Timing Triton
    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        out_du, out_dv, out_metric = triton_poincare_discrete_belov_chaltikian(u, v)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_du, ref_dv, ref_metric = torch_poincare_discrete_belov_chaltikian_ref(u, v)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M nodes/s")
