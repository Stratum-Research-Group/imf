"""
Cycle 254: Fused Poincaré Discrete Coupled Hirota Bivector Lattice Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 8.9 AD106)

Evaluates the discrete Hirota integrable lattice flow combining second-order dispersion,
third-order chiral dispersion, and Ablowitz-Ladik cross-phase modulation:
    i d psi_n / dt = alpha * (psi_{n+1} - 2 psi_n + psi_{n-1} + |psi_n|^2 (psi_{n+1} + psi_{n-1})) 
                   + i beta * ( (psi_{n+2} - 2 psi_{n+1} + 2 psi_{n-1} - psi_{n-2}) 
                                + |psi_n|^2 (psi_{n+2} - psi_{n-2}) )
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_psi = 2.0 / (1.0 - ||psi_n||^2)
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_coupled_hirota_kernel(
    psi_r_ptr, psi_i_ptr,
    d_psi_r_ptr, d_psi_i_ptr,
    out_metric_ptr,
    alpha,
    beta,
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N

    idx_p2 = (idx + 2) % N
    idx_p1 = (idx + 1) % N
    idx_m1 = (idx - 1 + N) % N
    idx_m2 = (idx - 2 + N) % N

    psi_r_c = tl.load(psi_r_ptr + idx, mask=mask, other=0.0)
    psi_i_c = tl.load(psi_i_ptr + idx, mask=mask, other=0.0)

    psi_r_p1 = tl.load(psi_r_ptr + idx_p1, mask=mask, other=0.0)
    psi_i_p1 = tl.load(psi_i_ptr + idx_p1, mask=mask, other=0.0)

    psi_r_p2 = tl.load(psi_r_ptr + idx_p2, mask=mask, other=0.0)
    psi_i_p2 = tl.load(psi_i_ptr + idx_p2, mask=mask, other=0.0)

    psi_r_m1 = tl.load(psi_r_ptr + idx_m1, mask=mask, other=0.0)
    psi_i_m1 = tl.load(psi_i_ptr + idx_m1, mask=mask, other=0.0)

    psi_r_m2 = tl.load(psi_r_ptr + idx_m2, mask=mask, other=0.0)
    psi_i_m2 = tl.load(psi_i_ptr + idx_m2, mask=mask, other=0.0)

    intensity = psi_r_c * psi_r_c + psi_i_c * psi_i_c

    # 1. Discrete NLS part: disp2 = (psi_{p1} - 2*psi_c + psi_{m1}) + intensity * (psi_{p1} + psi_{m1})
    disp2_r = (psi_r_p1 - 2.0 * psi_r_c + psi_r_m1) + intensity * (psi_r_p1 + psi_r_m1)
    disp2_i = (psi_i_p1 - 2.0 * psi_i_c + psi_i_m1) + intensity * (psi_i_p1 + psi_i_m1)

    # 2. Discrete mKdV chiral part: disp3 = (psi_{p2} - 2*psi_{p1} + 2*psi_{m1} - psi_{m2}) + intensity * (psi_{p2} - psi_{m2})
    disp3_r = (psi_r_p2 - 2.0 * psi_r_p1 + 2.0 * psi_r_m1 - psi_r_m2) + intensity * (psi_r_p2 - psi_r_m2)
    disp3_i = (psi_i_p2 - 2.0 * psi_i_p1 + 2.0 * psi_i_m1 - psi_i_m2) + intensity * (psi_i_p2 - psi_i_m2)

    # Total RHS = alpha * disp2 + i * beta * disp3
    # RHS_r = alpha * disp2_r - beta * disp3_i
    # RHS_i = alpha * disp2_i + beta * disp3_r
    rhs_r = alpha * disp2_r - beta * disp3_i
    rhs_i = alpha * disp2_i + beta * disp3_r

    # i dpsi/dt = RHS => dpsi/dt = -i RHS => dt_r = rhs_i, dt_i = -rhs_r
    dt_r = rhs_i
    dt_i = -rhs_r

    intensity_clamped = tl.minimum(intensity, 0.99)
    conf_metric = 2.0 / (1.0 - intensity_clamped)

    tl.store(d_psi_r_ptr + idx, dt_r * conf_metric, mask=mask)
    tl.store(d_psi_i_ptr + idx, dt_i * conf_metric, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_coupled_hirota(psi: torch.Tensor, alpha: float = 0.5, beta: float = 0.25):
    assert psi.is_cuda
    N = psi.numel()
    psi_r = psi.real.contiguous()
    psi_i = psi.imag.contiguous()

    d_psi_r = torch.empty_like(psi_r)
    d_psi_i = torch.empty_like(psi_i)
    out_metric = torch.empty_like(psi_r)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_coupled_hirota_kernel[grid](
        psi_r, psi_i,
        d_psi_r, d_psi_i,
        out_metric,
        float(alpha), float(beta),
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    d_psi = torch.complex(d_psi_r, d_psi_i)
    return d_psi, out_metric

def torch_poincare_discrete_coupled_hirota_ref(psi: torch.Tensor, alpha: float = 0.5, beta: float = 0.25):
    psi_p2 = torch.roll(psi, shifts=-2, dims=0)
    psi_p1 = torch.roll(psi, shifts=-1, dims=0)
    psi_m1 = torch.roll(psi, shifts=1, dims=0)
    psi_m2 = torch.roll(psi, shifts=2, dims=0)
    intensity = psi.abs() ** 2

    disp2 = (psi_p1 - 2.0 * psi + psi_m1) + intensity * (psi_p1 + psi_m1)
    disp3 = (psi_p2 - 2.0 * psi_p1 + 2.0 * psi_m1 - psi_m2) + intensity * (psi_p2 - psi_m2)

    rhs = alpha * disp2 + 1j * beta * disp3
    d_psi = -1j * rhs

    clamped_int = torch.clamp(intensity, max=0.99)
    conf_metric = 2.0 / (1.0 - clamped_int)
    return d_psi * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Coupled Hirota Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice nodes
    psi = (torch.randn(N, device=device, dtype=torch.complex64) * 0.1).contiguous()

    # Warmup
    for _ in range(20):
        d_psi, out_metric = triton_poincare_discrete_coupled_hirota(psi)
        ref_d_psi, ref_metric = torch_poincare_discrete_coupled_hirota_ref(psi)
    torch.cuda.synchronize()

    # Numerical verification
    max_err_d_psi = (d_psi - ref_d_psi).abs().max().item()
    max_err_metric = (out_metric - ref_metric).abs().max().item()
    print(f"Max Absolute Error (d_psi): {max_err_d_psi:.3e}")
    print(f"Max Absolute Error (Metric): {max_err_metric:.3e}")
    assert max_err_d_psi < 1e-4, f"Numerical error too high: {max_err_d_psi}"
    assert max_err_metric < 1e-5, f"Metric error too high: {max_err_metric}"

    # Timing Triton
    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        d_psi, out_metric = triton_poincare_discrete_coupled_hirota(psi)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_d_psi, ref_metric = torch_poincare_discrete_coupled_hirota_ref(psi)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M nodes/s")
