"""
Cycle 251: Fused Poincaré Discrete Coupled NLS Manakov Vector Soliton Lattice Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 8.9 AD106)

Evaluates the 2-component vector discrete nonlinear Schrödinger (Manakov lattice) flow:
    i d psi_{1,n} / dt = (psi_{1,n+1} - 2 psi_{1,n} + psi_{1,n-1}) + gamma * (|psi_{1,n}|^2 + |psi_{2,n}|^2) * (psi_{1,n+1} + psi_{1,n-1})
    i d psi_{2,n} / dt = (psi_{2,n+1} - 2 psi_{2,n} + psi_{2,n-1}) + gamma * (|psi_{1,n}|^2 + |psi_{2,n}|^2) * (psi_{2,n+1} + psi_{2,n-1})
Decomposed into 4 real components [psi1_r, psi1_i, psi2_r, psi2_i] and projected to the Poincaré hyperbolic ball:
    lambda_psi = 2.0 / (1.0 - (||psi_1||^2 + ||psi_2||^2))
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_manakov_kernel(
    p1_r_ptr, p1_i_ptr,
    p2_r_ptr, p2_i_ptr,
    d_p1_r_ptr, d_p1_i_ptr,
    d_p2_r_ptr, d_p2_i_ptr,
    out_metric_ptr,
    gamma,
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N

    idx_p1 = (idx + 1) % N
    idx_m1 = (idx - 1 + N) % N

    # Load psi1
    p1_r_c = tl.load(p1_r_ptr + idx, mask=mask, other=0.0)
    p1_i_c = tl.load(p1_i_ptr + idx, mask=mask, other=0.0)
    p1_r_p = tl.load(p1_r_ptr + idx_p1, mask=mask, other=0.0)
    p1_i_p = tl.load(p1_i_ptr + idx_p1, mask=mask, other=0.0)
    p1_r_m = tl.load(p1_r_ptr + idx_m1, mask=mask, other=0.0)
    p1_i_m = tl.load(p1_i_ptr + idx_m1, mask=mask, other=0.0)

    # Load psi2
    p2_r_c = tl.load(p2_r_ptr + idx, mask=mask, other=0.0)
    p2_i_c = tl.load(p2_i_ptr + idx, mask=mask, other=0.0)
    p2_r_p = tl.load(p2_r_ptr + idx_p1, mask=mask, other=0.0)
    p2_i_p = tl.load(p2_i_ptr + idx_p1, mask=mask, other=0.0)
    p2_r_m = tl.load(p2_r_ptr + idx_m1, mask=mask, other=0.0)
    p2_i_m = tl.load(p2_i_ptr + idx_m1, mask=mask, other=0.0)

    # Total intensity: |psi_1|^2 + |psi_2|^2
    int1 = p1_r_c * p1_r_c + p1_i_c * p1_i_c
    int2 = p2_r_c * p2_r_c + p2_i_c * p2_i_c
    tot_int = int1 + int2

    # Discrete linear dispersion: (psi_{n+1} - 2 psi_n + psi_{n-1})
    disp1_r = p1_r_p - 2.0 * p1_r_c + p1_r_m
    disp1_i = p1_i_p - 2.0 * p1_i_c + p1_i_m
    disp2_r = p2_r_p - 2.0 * p2_r_c + p2_r_m
    disp2_i = p2_i_p - 2.0 * p2_i_c + p2_i_m

    # Ablowitz-Ladik cross-coupling term: gamma * tot_int * (psi_{n+1} + psi_{n-1})
    sum1_r = p1_r_p + p1_r_m
    sum1_i = p1_i_p + p1_i_m
    sum2_r = p2_r_p + p2_r_m
    sum2_i = p2_i_p + p2_i_m

    rhs1_r = disp1_r + gamma * tot_int * sum1_r
    rhs1_i = disp1_i + gamma * tot_int * sum1_i
    rhs2_r = disp2_r + gamma * tot_int * sum2_r
    rhs2_i = disp2_i + gamma * tot_int * sum2_i

    # i dpsi/dt = RHS  =>  dpsi/dt = -i RHS  =>  d(psi_r)/dt = rhs_i,  d(psi_i)/dt = -rhs_r
    dt_p1_r = rhs1_i
    dt_p1_i = -rhs1_r
    dt_p2_r = rhs2_i
    dt_p2_i = -rhs2_r

    # Conformal metric: lambda = 2 / (1 - tot_int)
    clamped_int = tl.minimum(tot_int, 0.99)
    conf_metric = 2.0 / (1.0 - clamped_int)

    tl.store(d_p1_r_ptr + idx, dt_p1_r * conf_metric, mask=mask)
    tl.store(d_p1_i_ptr + idx, dt_p1_i * conf_metric, mask=mask)
    tl.store(d_p2_r_ptr + idx, dt_p2_r * conf_metric, mask=mask)
    tl.store(d_p2_i_ptr + idx, dt_p2_i * conf_metric, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_manakov(p1: torch.Tensor, p2: torch.Tensor, gamma: float = 0.5):
    assert p1.is_cuda and p2.is_cuda
    N = p1.numel()
    p1_r, p1_i = p1.real.contiguous(), p1.imag.contiguous()
    p2_r, p2_i = p2.real.contiguous(), p2.imag.contiguous()

    d_p1_r = torch.empty_like(p1_r)
    d_p1_i = torch.empty_like(p1_i)
    d_p2_r = torch.empty_like(p2_r)
    d_p2_i = torch.empty_like(p2_i)
    out_metric = torch.empty_like(p1_r)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_manakov_kernel[grid](
        p1_r, p1_i, p2_r, p2_i,
        d_p1_r, d_p1_i, d_p2_r, d_p2_i,
        out_metric, float(gamma),
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    d_p1 = torch.complex(d_p1_r, d_p1_i)
    d_p2 = torch.complex(d_p2_r, d_p2_i)
    return d_p1, d_p2, out_metric

def torch_poincare_discrete_manakov_ref(p1: torch.Tensor, p2: torch.Tensor, gamma: float = 0.5):
    p1_p1 = torch.roll(p1, shifts=-1, dims=0)
    p1_m1 = torch.roll(p1, shifts=1, dims=0)
    p2_p1 = torch.roll(p2, shifts=-1, dims=0)
    p2_m1 = torch.roll(p2, shifts=1, dims=0)

    tot_int = p1.abs()**2 + p2.abs()**2

    disp1 = p1_p1 - 2.0 * p1 + p1_m1
    disp2 = p2_p1 - 2.0 * p2 + p2_m1

    sum1 = p1_p1 + p1_m1
    sum2 = p2_p1 + p2_m1

    rhs1 = disp1 + gamma * tot_int * sum1
    rhs2 = disp2 + gamma * tot_int * sum2

    # i dpsi/dt = rhs => dpsi/dt = -1j * rhs
    d_p1 = -1j * rhs1
    d_p2 = -1j * rhs2

    clamped_int = torch.clamp(tot_int, max=0.99)
    conf_metric = 2.0 / (1.0 - clamped_int)
    return d_p1 * conf_metric, d_p2 * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Manakov Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice nodes
    p1 = (torch.randn(N, device=device, dtype=torch.complex64) * 0.1).contiguous()
    p2 = (torch.randn(N, device=device, dtype=torch.complex64) * 0.1).contiguous()

    # Warmup
    for _ in range(20):
        d_p1, d_p2, out_metric = triton_poincare_discrete_manakov(p1, p2)
        ref_p1, ref_p2, ref_metric = torch_poincare_discrete_manakov_ref(p1, p2)
    torch.cuda.synchronize()

    # Numerical verification
    max_err_p1 = (d_p1 - ref_p1).abs().max().item()
    max_err_p2 = (d_p2 - ref_p2).abs().max().item()
    max_err_metric = (out_metric - ref_metric).abs().max().item()
    print(f"Max Absolute Error (Psi1): {max_err_p1:.3e}")
    print(f"Max Absolute Error (Psi2): {max_err_p2:.3e}")
    print(f"Max Absolute Error (Metric): {max_err_metric:.3e}")
    assert max_err_p1 < 1e-4, f"Numerical error too high: {max_err_p1}"
    assert max_err_p2 < 1e-4, f"Numerical error too high: {max_err_p2}"
    assert max_err_metric < 1e-5, f"Metric error too high: {max_err_metric}"

    # Timing Triton
    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        d_p1, d_p2, out_metric = triton_poincare_discrete_manakov(p1, p2)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_p1, ref_p2, ref_metric = torch_poincare_discrete_manakov_ref(p1, p2)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M nodes/s")
