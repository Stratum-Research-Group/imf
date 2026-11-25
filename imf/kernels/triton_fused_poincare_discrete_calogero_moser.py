"""
Cycle 263: Fused Poincaré Discrete Calogero-Moser Many-Body Nearest-Neighbor Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 12.0 GB206)

Evaluates the discrete Calogero-Moser lattice interaction:
    d^2 x_n / dt^2 = 2.0 * g^2 * ( 1 / (x_n - x_{n+1} + d0)^3 + 1 / (x_n - x_{n-1} - d0)^3 )
Where d0 is the lattice spacing offset ensuring strict positive denominator.
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_x = 2.0 / (1.0 - ||x_n||^2)
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_calogero_moser_kernel(
    x_ptr,           # [N] particle positions
    p_ptr,           # [N] particle momenta
    out_a_ptr,       # [N] output acceleration
    out_metric_ptr,  # [N] conformal metric factor
    g_sq,            # coupling constant g^2
    d0,              # equilibrium lattice spacing offset
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N

    idx_p1 = (idx + 1) % N
    idx_m1 = (idx - 1 + N) % N

    x_curr = tl.load(x_ptr + idx, mask=mask, other=0.0)
    x_p1   = tl.load(x_ptr + idx_p1, mask=mask, other=0.0)
    x_m1   = tl.load(x_ptr + idx_m1, mask=mask, other=0.0)

    # Displacements with non-zero equilibrium spacing d0
    dist_p = (x_curr - x_p1) + d0
    dist_m = (x_curr - x_m1) - d0

    # Ensure numerical safety
    dist_p_safe = tl.where(dist_p >= 0.0, tl.maximum(dist_p, 0.01), tl.minimum(dist_p, -0.01))
    dist_m_safe = tl.where(dist_m >= 0.0, tl.maximum(dist_m, 0.01), tl.minimum(dist_m, -0.01))

    force_p = (2.0 * g_sq) / (dist_p_safe * dist_p_safe * dist_p_safe)
    force_m = (2.0 * g_sq) / (dist_m_safe * dist_m_safe * dist_m_safe)

    acc = force_p + force_m

    # Poincaré hyperbolic metric conformal factor
    x_sq = x_curr * x_curr
    x_clamped = tl.minimum(x_sq, 0.99)
    conf_metric = 2.0 / (1.0 - x_clamped)

    fused_acc = acc * conf_metric

    tl.store(out_a_ptr + idx, fused_acc, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_calogero_moser(x: torch.Tensor, p: torch.Tensor, g_sq: float = 1.0, d0: float = 1.0):
    assert x.is_cuda and p.is_cuda
    N = x.numel()
    out_a = torch.empty_like(x)
    out_metric = torch.empty_like(x)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_calogero_moser_kernel[grid](
        x, p, out_a, out_metric,
        float(g_sq), float(d0),
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_a, out_metric

def torch_poincare_discrete_calogero_moser_ref(x: torch.Tensor, p: torch.Tensor, g_sq: float = 1.0, d0: float = 1.0):
    x_p1 = torch.roll(x, shifts=-1, dims=0)
    x_m1 = torch.roll(x, shifts=1, dims=0)

    dist_p = (x - x_p1) + d0
    dist_m = (x - x_m1) - d0

    dist_p_safe = torch.where(dist_p >= 0.0, torch.clamp(dist_p, min=0.01), torch.clamp(dist_p, max=-0.01))
    dist_m_safe = torch.where(dist_m >= 0.0, torch.clamp(dist_m, min=0.01), torch.clamp(dist_m, max=-0.01))

    force_p = (2.0 * g_sq) / (dist_p_safe ** 3)
    force_m = (2.0 * g_sq) / (dist_m_safe ** 3)
    acc = force_p + force_m

    x_sq = torch.clamp(x ** 2, max=0.99)
    conf_metric = 2.0 / (1.0 - x_sq)
    return acc * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Calogero-Moser Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice particles
    x = (torch.randn(N, device=device, dtype=torch.float32) * 0.1).contiguous()
    p = (torch.randn(N, device=device, dtype=torch.float32) * 0.05).contiguous()

    # Warmup
    for _ in range(20):
        out_a, out_metric = triton_poincare_discrete_calogero_moser(x, p)
        ref_a, ref_metric = torch_poincare_discrete_calogero_moser_ref(x, p)
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
        out_a, out_metric = triton_poincare_discrete_calogero_moser(x, p)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_a, ref_metric = torch_poincare_discrete_calogero_moser_ref(x, p)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M particles/s")
