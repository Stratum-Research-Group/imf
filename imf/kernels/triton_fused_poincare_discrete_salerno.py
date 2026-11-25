"""
Cycle 253: Fused Poincaré Discrete Salerno Polariton Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 8.9 AD106)

Evaluates the discrete Salerno equation interpolating between standard discrete NLS (DNLS) and integrable Ablowitz-Ladik (AL):
    i d psi_n / dt = (psi_{n+1} - 2 psi_n + psi_{n-1}) + (mu * |psi_n|^2 * (psi_{n+1} + psi_{n-1})) + (gamma * |psi_n|^2 * psi_n)
Decomposed into real and imaginary parts [psi_r, psi_i] and projected to the Poincaré hyperbolic disk conformal factor:
    lambda_psi = 2.0 / (1.0 - ||psi_n||^2)
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_salerno_kernel(
    psi_r_ptr, psi_i_ptr,
    d_psi_r_ptr, d_psi_i_ptr,
    out_metric_ptr,
    mu,        # Ablowitz-Ladik inter-site nonlinear parameter
    gamma,     # Standard DNLS on-site nonlinear parameter
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N

    idx_p1 = (idx + 1) % N
    idx_m1 = (idx - 1 + N) % N

    psi_r_c = tl.load(psi_r_ptr + idx, mask=mask, other=0.0)
    psi_i_c = tl.load(psi_i_ptr + idx, mask=mask, other=0.0)

    psi_r_p = tl.load(psi_r_ptr + idx_p1, mask=mask, other=0.0)
    psi_i_p = tl.load(psi_i_ptr + idx_p1, mask=mask, other=0.0)

    psi_r_m = tl.load(psi_r_ptr + idx_m1, mask=mask, other=0.0)
    psi_i_m = tl.load(psi_i_ptr + idx_m1, mask=mask, other=0.0)

    # 1. Intensity: |psi_n|^2
    intensity = psi_r_c * psi_r_c + psi_i_c * psi_i_c

    # 2. Linear dispersion: (psi_{n+1} - 2 psi_n + psi_{n-1})
    disp_r = psi_r_p - 2.0 * psi_r_c + psi_r_m
    disp_i = psi_i_p - 2.0 * psi_i_c + psi_i_m

    # 3. Ablowitz-Ladik inter-site term: mu * |psi_n|^2 * (psi_{n+1} + psi_{n-1})
    sum_r = psi_r_p + psi_r_m
    sum_i = psi_i_p + psi_i_m
    al_r = mu * intensity * sum_r
    al_i = mu * intensity * sum_i

    # 4. Standard on-site DNLS cubic term: gamma * |psi_n|^2 * psi_n
    dnls_r = gamma * intensity * psi_r_c
    dnls_i = gamma * intensity * psi_i_c

    # Total RHS
    rhs_r = disp_r + al_r + dnls_r
    rhs_i = disp_i + al_i + dnls_i

    # i dpsi/dt = RHS => dpsi/dt = -i RHS => d(psi_r)/dt = rhs_i, d(psi_i)/dt = -rhs_r
    dt_r = rhs_i
    dt_i = -rhs_r

    # Poincaré hyperbolic metric conformal factor
    intensity_clamped = tl.minimum(intensity, 0.99)
    conf_metric = 2.0 / (1.0 - intensity_clamped)

    tl.store(d_psi_r_ptr + idx, dt_r * conf_metric, mask=mask)
    tl.store(d_psi_i_ptr + idx, dt_i * conf_metric, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_salerno(psi: torch.Tensor, mu: float = 0.5, gamma: float = 0.5):
    assert psi.is_cuda
    N = psi.numel()
    psi_r = psi.real.contiguous()
    psi_i = psi.imag.contiguous()

    d_psi_r = torch.empty_like(psi_r)
    d_psi_i = torch.empty_like(psi_i)
    out_metric = torch.empty_like(psi_r)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_salerno_kernel[grid](
        psi_r, psi_i,
        d_psi_r, d_psi_i,
        out_metric,
        float(mu), float(gamma),
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    d_psi = torch.complex(d_psi_r, d_psi_i)
    return d_psi, out_metric

def torch_poincare_discrete_salerno_ref(psi: torch.Tensor, mu: float = 0.5, gamma: float = 0.5):
    psi_p1 = torch.roll(psi, shifts=-1, dims=0)
    psi_m1 = torch.roll(psi, shifts=1, dims=0)
    intensity = psi.abs() ** 2

    disp = psi_p1 - 2.0 * psi + psi_m1
    al_term = mu * intensity * (psi_p1 + psi_m1)
    dnls_term = gamma * intensity * psi

    rhs = disp + al_term + dnls_term
    d_psi = -1j * rhs

    clamped_int = torch.clamp(intensity, max=0.99)
    conf_metric = 2.0 / (1.0 - clamped_int)
    return d_psi * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Salerno Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice nodes
    psi = (torch.randn(N, device=device, dtype=torch.complex64) * 0.1).contiguous()

    # Warmup
    for _ in range(20):
        d_psi, out_metric = triton_poincare_discrete_salerno(psi)
        ref_d_psi, ref_metric = torch_poincare_discrete_salerno_ref(psi)
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
        d_psi, out_metric = triton_poincare_discrete_salerno(psi)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_d_psi, ref_metric = torch_poincare_discrete_salerno_ref(psi)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M nodes/s")
