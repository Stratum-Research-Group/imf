"""
Cycle 260: Fused Poincaré Discrete Sawada-Kotera 5th-Order Quintic Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 8.9 AD106)

Evaluates the discrete 5th-order Sawada-Kotera integrable dynamical flow:
    d u_n / dt = (u_{n+2} - 2 u_{n+1} + 2 u_{n-1} - u_{n-2}) + 5 u_n * (u_{n+1} - u_{n-1}) * (u_{n+1} + u_n + u_{n-1})
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_u = 2.0 / (1.0 - ||u_n||^2)
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_sawada_kotera_kernel(
    u_ptr,           # [N] field displacement
    out_du_ptr,      # [N] output time derivative
    out_metric_ptr,  # [N] conformal Riemannian metric factor
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

    u_curr = tl.load(u_ptr + idx, mask=mask, other=0.0)
    u_p2   = tl.load(u_ptr + idx_p2, mask=mask, other=0.0)
    u_p1   = tl.load(u_ptr + idx_p1, mask=mask, other=0.0)
    u_m1   = tl.load(u_ptr + idx_m1, mask=mask, other=0.0)
    u_m2   = tl.load(u_ptr + idx_m2, mask=mask, other=0.0)

    # 1. 5-point discrete linear dispersion: (u_{n+2} - 2*u_{n+1} + 2*u_{n-1} - u_{n-2})
    disp5 = (u_p2 - 2.0 * u_p1 + 2.0 * u_m1 - u_m2)

    # 2. Quintic nonlinear convective flux: 5 * u_n * (u_{n+1} - u_{n-1}) * (u_{n+1} + u_n + u_{n-1})
    diff1 = u_p1 - u_m1
    sum1 = u_p1 + u_curr + u_m1
    nonlinear_flux = 5.0 * u_curr * diff1 * sum1

    du = disp5 + nonlinear_flux

    # 3. Poincaré hyperbolic conformal metric factor
    u_sq = u_curr * u_curr
    u_clamped = tl.minimum(u_sq, 0.99)
    conf_metric = 2.0 / (1.0 - u_clamped)

    fused_du = du * conf_metric

    tl.store(out_du_ptr + idx, fused_du, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_sawada_kotera(u: torch.Tensor):
    assert u.is_cuda
    N = u.numel()
    out_du = torch.empty_like(u)
    out_metric = torch.empty_like(u)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_sawada_kotera_kernel[grid](
        u, out_du, out_metric,
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_du, out_metric

def torch_poincare_discrete_sawada_kotera_ref(u: torch.Tensor):
    u_p2 = torch.roll(u, shifts=-2, dims=0)
    u_p1 = torch.roll(u, shifts=-1, dims=0)
    u_m1 = torch.roll(u, shifts=1, dims=0)
    u_m2 = torch.roll(u, shifts=2, dims=0)

    disp5 = (u_p2 - 2.0 * u_p1 + 2.0 * u_m1 - u_m2)
    diff1 = u_p1 - u_m1
    sum1 = u_p1 + u + u_m1
    nonlinear_flux = 5.0 * u * diff1 * sum1

    du = disp5 + nonlinear_flux
    u_sq = torch.clamp(u ** 2, max=0.99)
    conf_metric = 2.0 / (1.0 - u_sq)
    return du * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Sawada-Kotera Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice nodes
    u = (torch.randn(N, device=device, dtype=torch.float32) * 0.1).contiguous()

    # Warmup
    for _ in range(20):
        out_du, out_metric = triton_poincare_discrete_sawada_kotera(u)
        ref_du, ref_metric = torch_poincare_discrete_sawada_kotera_ref(u)
    torch.cuda.synchronize()

    # Numerical verification
    max_err_du = (out_du - ref_du).abs().max().item()
    max_err_metric = (out_metric - ref_metric).abs().max().item()
    print(f"Max Absolute Error (du): {max_err_du:.3e}")
    print(f"Max Absolute Error (Metric): {max_err_metric:.3e}")
    assert max_err_du < 1e-4, f"Numerical error too high: {max_err_du}"
    assert max_err_metric < 1e-5, f"Metric error too high: {max_err_metric}"

    # Timing Triton
    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        out_du, out_metric = triton_poincare_discrete_sawada_kotera(u)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_du, ref_metric = torch_poincare_discrete_sawada_kotera_ref(u)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M nodes/s")
