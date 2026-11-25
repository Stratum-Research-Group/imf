"""
Cycle 268: Fused Poincaré Discrete Blaszak-Marciniak 3-Field Lattice Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 12.0 GB206)

Evaluates the discrete Blaszak-Marciniak 3-field coupled lattice dynamical flow:
    d u_n / dt = v_{n+1} - v_n
    d v_n / dt = w_{n+1} - w_n + u_n * (v_{n+1} - v_n)
    d w_n / dt = w_n * (u_n - u_{n-1})
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda = 2.0 / (1.0 - (||u_n||^2 + ||v_n||^2 + ||w_n||^2))
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_blaszak_marciniak_kernel(
    u_ptr, v_ptr, w_ptr,
    out_du_ptr, out_dv_ptr, out_dw_ptr,
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
    u_m1   = tl.load(u_ptr + idx_m1, mask=mask, other=0.0)

    v_curr = tl.load(v_ptr + idx, mask=mask, other=0.0)
    v_p1   = tl.load(v_ptr + idx_p1, mask=mask, other=0.0)

    w_curr = tl.load(w_ptr + idx, mask=mask, other=0.0)
    w_p1   = tl.load(w_ptr + idx_p1, mask=mask, other=0.0)

    # 3-field discrete bi-Hamiltonian hierarchy
    du = v_p1 - v_curr
    dv = (w_p1 - w_curr) + u_curr * (v_p1 - v_curr)
    dw = w_curr * (u_curr - u_m1)

    tot_sq = u_curr * u_curr + v_curr * v_curr + w_curr * w_curr
    clamped_sq = tl.minimum(tot_sq, 0.99)
    conf_metric = 2.0 / (1.0 - clamped_sq)

    tl.store(out_du_ptr + idx, du * conf_metric, mask=mask)
    tl.store(out_dv_ptr + idx, dv * conf_metric, mask=mask)
    tl.store(out_dw_ptr + idx, dw * conf_metric, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_blaszak_marciniak(u: torch.Tensor, v: torch.Tensor, w: torch.Tensor):
    assert u.is_cuda and v.is_cuda and w.is_cuda
    N = u.numel()
    out_du = torch.empty_like(u)
    out_dv = torch.empty_like(v)
    out_dw = torch.empty_like(w)
    out_metric = torch.empty_like(u)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_blaszak_marciniak_kernel[grid](
        u, v, w,
        out_du, out_dv, out_dw,
        out_metric,
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_du, out_dv, out_dw, out_metric

def torch_poincare_discrete_blaszak_marciniak_ref(u: torch.Tensor, v: torch.Tensor, w: torch.Tensor):
    u_m1 = torch.roll(u, shifts=1, dims=0)
    v_p1 = torch.roll(v, shifts=-1, dims=0)
    w_p1 = torch.roll(w, shifts=-1, dims=0)

    du = v_p1 - v
    dv = (w_p1 - w) + u * (v_p1 - v)
    dw = w * (u - u_m1)

    tot_sq = torch.clamp(u ** 2 + v ** 2 + w ** 2, max=0.99)
    conf_metric = 2.0 / (1.0 - tot_sq)
    return du * conf_metric, dv * conf_metric, dw * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Blaszak-Marciniak Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice nodes
    u = (torch.randn(N, device=device, dtype=torch.float32) * 0.1).contiguous()
    v = (torch.randn(N, device=device, dtype=torch.float32) * 0.1).contiguous()
    w = (torch.randn(N, device=device, dtype=torch.float32) * 0.1).contiguous()

    # Warmup
    for _ in range(20):
        out_du, out_dv, out_dw, out_metric = triton_poincare_discrete_blaszak_marciniak(u, v, w)
        ref_du, ref_dv, ref_dw, ref_metric = torch_poincare_discrete_blaszak_marciniak_ref(u, v, w)
    torch.cuda.synchronize()

    # Numerical verification
    max_err_du = (out_du - ref_du).abs().max().item()
    max_err_dv = (out_dv - ref_dv).abs().max().item()
    max_err_dw = (out_dw - ref_dw).abs().max().item()
    max_err_metric = (out_metric - ref_metric).abs().max().item()
    print(f"Max Absolute Error (du): {max_err_du:.3e}")
    print(f"Max Absolute Error (dv): {max_err_dv:.3e}")
    print(f"Max Absolute Error (dw): {max_err_dw:.3e}")
    print(f"Max Absolute Error (Metric): {max_err_metric:.3e}")
    assert max_err_du < 1e-4, f"Numerical error too high: {max_err_du}"
    assert max_err_dv < 1e-4, f"Numerical error too high: {max_err_dv}"
    assert max_err_dw < 1e-4, f"Numerical error too high: {max_err_dw}"
    assert max_err_metric < 1e-5, f"Metric error too high: {max_err_metric}"

    # Timing Triton
    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        out_du, out_dv, out_dw, out_metric = triton_poincare_discrete_blaszak_marciniak(u, v, w)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_du, ref_dv, ref_dw, ref_metric = torch_poincare_discrete_blaszak_marciniak_ref(u, v, w)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M nodes/s")
