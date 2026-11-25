"""
Cycle 249: Fused Poincaré Discrete Boussinesq Bidirectional Lattice Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 12.0 GB206)

Evaluates the discrete Boussinesq lattice dynamical flow on Poincaré hyperbolic ball manifold:
    d^2 u_n / dt^2 = (u_{n+1} - 2 u_n + u_{n-1}) + alpha * ((u_{n+1} - u_n)^2 - (u_n - u_{n-1})^2) - beta * (u_{n+2} - 4 u_{n+1} + 6 u_n - 4 u_{n-1} + u_{n-2})
Projected to the Poincaré disk metric conformal factor:
    lambda_u = 2.0 / (1.0 - ||u_n||^2)
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_boussinesq_kernel(
    u_ptr,           # [N] current displacement field
    v_ptr,           # [N] current momentum / velocity field
    out_acc_ptr,     # [N] output acceleration field
    out_metric_ptr,  # [N] output conformal Riemannian metric weights
    alpha,           # quadratic lattice nonlinearity
    beta,            # 5-point discrete biharmonic dispersion
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N

    # Periodic boundary indexing for 5-point stencil
    idx_p2 = (idx + 2) % N
    idx_p1 = (idx + 1) % N
    idx_m1 = (idx - 1 + N) % N
    idx_m2 = (idx - 2 + N) % N

    u_curr = tl.load(u_ptr + idx, mask=mask, other=0.0)
    u_p2   = tl.load(u_ptr + idx_p2, mask=mask, other=0.0)
    u_p1   = tl.load(u_ptr + idx_p1, mask=mask, other=0.0)
    u_m1   = tl.load(u_ptr + idx_m1, mask=mask, other=0.0)
    u_m2   = tl.load(u_ptr + idx_m2, mask=mask, other=0.0)

    # 1. Harmonic nearest-neighbor dispersion: Delta u = u_{n+1} - 2*u_n + u_{n-1}
    diff_p = u_p1 - u_curr
    diff_m = u_curr - u_m1
    linear_disp = diff_p - diff_m

    # 2. Quadratic nonlinear transport: (u_{n+1} - u_n)^2 - (u_n - u_{n-1})^2
    nonlinear_disp = (diff_p * diff_p) - (diff_m * diff_m)

    # 3. 5-point biharmonic dispersion: u_{n+2} - 4*u_{n+1} + 6*u_n - 4*u_{n-1} + u_{n-2}
    biharmonic_disp = u_p2 - 4.0 * u_p1 + 6.0 * u_curr - 4.0 * u_m1 + u_m2

    # Discrete Boussinesq acceleration
    acc = linear_disp + alpha * nonlinear_disp - beta * biharmonic_disp

    # Poincaré hyperbolic metric scaling
    u_sq = u_curr * u_curr
    u_clamped = tl.minimum(u_sq, 0.99)
    conf_metric = 2.0 / (1.0 - u_clamped)

    fused_acc = acc * conf_metric

    tl.store(out_acc_ptr + idx, fused_acc, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_boussinesq(u: torch.Tensor, v: torch.Tensor, alpha: float = 0.5, beta: float = 0.25):
    assert u.is_cuda and v.is_cuda
    assert u.shape == v.shape
    N = u.numel()
    out_acc = torch.empty_like(u)
    out_metric = torch.empty_like(u)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_boussinesq_kernel[grid](
        u, v, out_acc, out_metric,
        float(alpha), float(beta),
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_acc, out_metric

def torch_poincare_discrete_boussinesq_ref(u: torch.Tensor, v: torch.Tensor, alpha: float = 0.5, beta: float = 0.25):
    u_p2 = torch.roll(u, shifts=-2, dims=0)
    u_p1 = torch.roll(u, shifts=-1, dims=0)
    u_m1 = torch.roll(u, shifts=1, dims=0)
    u_m2 = torch.roll(u, shifts=2, dims=0)

    diff_p = u_p1 - u
    diff_m = u - u_m1
    linear_disp = diff_p - diff_m
    nonlinear_disp = (diff_p ** 2) - (diff_m ** 2)
    biharmonic_disp = u_p2 - 4.0 * u_p1 + 6.0 * u - 4.0 * u_m1 + u_m2

    acc = linear_disp + alpha * nonlinear_disp - beta * biharmonic_disp
    u_sq = torch.clamp(u ** 2, max=0.99)
    conf_metric = 2.0 / (1.0 - u_sq)
    return acc * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Boussinesq Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice nodes
    u = (torch.randn(N, device=device, dtype=torch.float32) * 0.1).contiguous()
    v = (torch.randn(N, device=device, dtype=torch.float32) * 0.05).contiguous()

    # Warmup
    for _ in range(20):
        out_acc, out_metric = triton_poincare_discrete_boussinesq(u, v)
        ref_acc, ref_metric = torch_poincare_discrete_boussinesq_ref(u, v)
    torch.cuda.synchronize()

    # Numerical verification
    max_err_acc = (out_acc - ref_acc).abs().max().item()
    max_err_metric = (out_metric - ref_metric).abs().max().item()
    print(f"Max Absolute Error (Acc): {max_err_acc:.3e}")
    print(f"Max Absolute Error (Metric): {max_err_metric:.3e}")
    assert max_err_acc < 1e-4, f"Numerical error too high: {max_err_acc}"
    assert max_err_metric < 1e-5, f"Metric error too high: {max_err_metric}"

    # Timing Triton
    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        out_acc, out_metric = triton_poincare_discrete_boussinesq(u, v)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_acc, ref_metric = torch_poincare_discrete_boussinesq_ref(u, v)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M nodes/s")
