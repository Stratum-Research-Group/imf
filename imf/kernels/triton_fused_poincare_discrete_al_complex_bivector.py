"""
Cycle 273: Fused Poincaré Discrete Ablowitz-Ladik Complex Bivector Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 8.9 AD106)

Evaluates the discrete Ablowitz-Ladik complex bivector dynamical flow:
    i d u_n / dt = (u_{n+1} - 2 u_n + u_{n-1}) + (u_n u^*_n + v_n v^*_n) * (u_{n+1} + u_{n-1})
    i d v_n / dt = (v_{n+1} - 2 v_n + v_{n-1}) + (u_n u^*_n + v_n v^*_n) * (v_{n+1} + v_{n-1})
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda = 2.0 / (1.0 - (||u_n||^2 + ||v_n||^2))
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_al_bivector_kernel(
    u_r_ptr, u_i_ptr,
    v_r_ptr, v_i_ptr,
    d_u_r_ptr, d_u_i_ptr,
    d_v_r_ptr, d_v_i_ptr,
    out_metric_ptr,
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N

    idx_p1 = (idx + 1) % N
    idx_m1 = (idx - 1 + N) % N

    u_r_c = tl.load(u_r_ptr + idx, mask=mask, other=0.0)
    u_i_c = tl.load(u_i_ptr + idx, mask=mask, other=0.0)
    u_r_p = tl.load(u_r_ptr + idx_p1, mask=mask, other=0.0)
    u_i_p = tl.load(u_i_ptr + idx_p1, mask=mask, other=0.0)
    u_r_m = tl.load(u_r_ptr + idx_m1, mask=mask, other=0.0)
    u_i_m = tl.load(u_i_ptr + idx_m1, mask=mask, other=0.0)

    v_r_c = tl.load(v_r_ptr + idx, mask=mask, other=0.0)
    v_i_c = tl.load(v_i_ptr + idx, mask=mask, other=0.0)
    v_r_p = tl.load(v_r_ptr + idx_p1, mask=mask, other=0.0)
    v_i_p = tl.load(v_i_ptr + idx_p1, mask=mask, other=0.0)
    v_r_m = tl.load(v_r_ptr + idx_m1, mask=mask, other=0.0)
    v_i_m = tl.load(v_i_ptr + idx_m1, mask=mask, other=0.0)

    # Total intensity: |u|^2 + |v|^2
    tot_int = (u_r_c * u_r_c + u_i_c * u_i_c) + (v_r_c * v_r_c + v_i_c * v_i_c)

    # Dispersions
    disp_u_r = u_r_p - 2.0 * u_r_c + u_r_m
    disp_u_i = u_i_p - 2.0 * u_i_c + u_i_m
    disp_v_r = v_r_p - 2.0 * v_r_c + v_r_m
    disp_v_i = v_i_p - 2.0 * v_i_c + v_i_m

    # Cross-phase Ablowitz-Ladik couplings
    sum_u_r = u_r_p + u_r_m
    sum_u_i = u_i_p + u_i_m
    sum_v_r = v_r_p + v_r_m
    sum_v_i = v_i_p + v_i_m

    rhs_u_r = disp_u_r + tot_int * sum_u_r
    rhs_u_i = disp_u_i + tot_int * sum_u_i
    rhs_v_r = disp_v_r + tot_int * sum_v_r
    rhs_v_i = disp_v_i + tot_int * sum_v_i

    # i d/dt = RHS => dt = -i RHS
    dt_u_r = rhs_u_i
    dt_u_i = -rhs_u_r
    dt_v_r = rhs_v_i
    dt_v_i = -rhs_v_r

    clamped_int = tl.minimum(tot_int, 0.99)
    conf_metric = 2.0 / (1.0 - clamped_int)

    tl.store(d_u_r_ptr + idx, dt_u_r * conf_metric, mask=mask)
    tl.store(d_u_i_ptr + idx, dt_u_i * conf_metric, mask=mask)
    tl.store(d_v_r_ptr + idx, dt_v_r * conf_metric, mask=mask)
    tl.store(d_v_i_ptr + idx, dt_v_i * conf_metric, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_al_bivector(u: torch.Tensor, v: torch.Tensor):
    assert u.is_cuda and v.is_cuda
    N = u.numel()
    u_r, u_i = u.real.contiguous(), u.imag.contiguous()
    v_r, v_i = v.real.contiguous(), v.imag.contiguous()

    d_u_r = torch.empty_like(u_r)
    d_u_i = torch.empty_like(u_i)
    d_v_r = torch.empty_like(v_r)
    d_v_i = torch.empty_like(v_i)
    out_metric = torch.empty_like(u_r)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_al_bivector_kernel[grid](
        u_r, u_i, v_r, v_i,
        d_u_r, d_u_i, d_v_r, d_v_i,
        out_metric,
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    d_u = torch.complex(d_u_r, d_u_i)
    d_v = torch.complex(d_v_r, d_v_i)
    return d_u, d_v, out_metric

def torch_poincare_discrete_al_bivector_ref(u: torch.Tensor, v: torch.Tensor):
    u_p1 = torch.roll(u, shifts=-1, dims=0)
    u_m1 = torch.roll(u, shifts=1, dims=0)
    v_p1 = torch.roll(v, shifts=-1, dims=0)
    v_m1 = torch.roll(v, shifts=1, dims=0)

    tot_int = u.abs()**2 + v.abs()**2
    disp_u = u_p1 - 2.0 * u + u_m1
    disp_v = v_p1 - 2.0 * v + v_m1

    rhs_u = disp_u + tot_int * (u_p1 + u_m1)
    rhs_v = disp_v + tot_int * (v_p1 + v_m1)

    d_u = -1j * rhs_u
    d_v = -1j * rhs_v

    clamped_int = torch.clamp(tot_int, max=0.99)
    conf_metric = 2.0 / (1.0 - clamped_int)
    return d_u * conf_metric, d_v * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete AL Bivector Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice nodes
    u = (torch.randn(N, device=device, dtype=torch.complex64) * 0.1).contiguous()
    v = (torch.randn(N, device=device, dtype=torch.complex64) * 0.1).contiguous()

    # Warmup
    for _ in range(20):
        d_u, d_v, out_metric = triton_poincare_discrete_al_bivector(u, v)
        ref_u, ref_v, ref_metric = torch_poincare_discrete_al_bivector_ref(u, v)
    torch.cuda.synchronize()

    # Numerical verification
    max_err_u = (d_u - ref_u).abs().max().item()
    max_err_v = (d_v - ref_v).abs().max().item()
    max_err_metric = (out_metric - ref_metric).abs().max().item()
    print(f"Max Absolute Error (du): {max_err_u:.3e}")
    print(f"Max Absolute Error (dv): {max_err_v:.3e}")
    print(f"Max Absolute Error (Metric): {max_err_metric:.3e}")
    assert max_err_u < 1e-4, f"Numerical error too high: {max_err_u}"
    assert max_err_v < 1e-4, f"Numerical error too high: {max_err_v}"
    assert max_err_metric < 1e-5, f"Metric error too high: {max_err_metric}"

    # Timing Triton
    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        d_u, d_v, out_metric = triton_poincare_discrete_al_bivector(u, v)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_u, ref_v, ref_metric = torch_poincare_discrete_al_bivector_ref(u, v)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M nodes/s")
