"""
Cycle 265: Fused Poincaré Discrete Ruijsenaars-Schneider Relativistic Hyperbolic Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 12.0 GB206)

Evaluates the discrete Ruijsenaars-Schneider relativistic many-body interaction:
    d q_n / dt = v_n * sqrt( (1 + lambda^2 / (q_n - q_{n+1} + d0)^2) * (1 + lambda^2 / (q_n - q_{n-1} - d0)^2) )
Projected to the Poincaré hyperbolic ball conformal factor:
    lambda_q = 2.0 / (1.0 - ||q_n||^2)
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_relativistic_rs_kernel(
    q_ptr,           # [N] particle positions
    v_ptr,           # [N] particle velocities
    out_dq_ptr,      # [N] output relativistic velocity
    out_metric_ptr,  # [N] conformal metric factor
    coupling_lam_sq, # relativistic parameter lambda^2
    d0,              # equilibrium spacing d0
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
    v_curr = tl.load(v_ptr + idx, mask=mask, other=0.0)

    # Displacements
    dist_p = (q_curr - q_p1) + d0
    dist_m = (q_curr - q_m1) - d0

    dist_p_safe = tl.where(dist_p >= 0.0, tl.maximum(dist_p, 0.02), tl.minimum(dist_p, -0.02))
    dist_m_safe = tl.where(dist_m >= 0.0, tl.maximum(dist_m, 0.02), tl.minimum(dist_m, -0.02))

    factor_p = 1.0 + coupling_lam_sq / (dist_p_safe * dist_p_safe)
    factor_m = 1.0 + coupling_lam_sq / (dist_m_safe * dist_m_safe)

    rel_factor = tl.sqrt(factor_p * factor_m)
    dq = v_curr * rel_factor

    # Poincaré hyperbolic metric conformal factor
    q_sq = q_curr * q_curr
    q_clamped = tl.minimum(q_sq, 0.99)
    conf_metric = 2.0 / (1.0 - q_clamped)

    fused_dq = dq * conf_metric

    tl.store(out_dq_ptr + idx, fused_dq, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_relativistic_rs(q: torch.Tensor, v: torch.Tensor, coupling_lam_sq: float = 0.5, d0: float = 1.0):
    assert q.is_cuda and v.is_cuda
    N = q.numel()
    out_dq = torch.empty_like(q)
    out_metric = torch.empty_like(q)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_relativistic_rs_kernel[grid](
        q, v, out_dq, out_metric,
        float(coupling_lam_sq), float(d0),
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_dq, out_metric

def torch_poincare_discrete_relativistic_rs_ref(q: torch.Tensor, v: torch.Tensor, coupling_lam_sq: float = 0.5, d0: float = 1.0):
    q_p1 = torch.roll(q, shifts=-1, dims=0)
    q_m1 = torch.roll(q, shifts=1, dims=0)

    dist_p = (q - q_p1) + d0
    dist_m = (q - q_m1) - d0

    dist_p_safe = torch.where(dist_p >= 0.0, torch.clamp(dist_p, min=0.02), torch.clamp(dist_p, max=-0.02))
    dist_m_safe = torch.where(dist_m >= 0.0, torch.clamp(dist_m, min=0.02), torch.clamp(dist_m, max=-0.02))

    factor_p = 1.0 + coupling_lam_sq / (dist_p_safe ** 2)
    factor_m = 1.0 + coupling_lam_sq / (dist_m_safe ** 2)

    rel_factor = torch.sqrt(factor_p * factor_m)
    dq = v * rel_factor

    q_sq = torch.clamp(q ** 2, max=0.99)
    conf_metric = 2.0 / (1.0 - q_sq)
    return dq * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Relativistic RS Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K particles
    q = (torch.randn(N, device=device, dtype=torch.float32) * 0.1).contiguous()
    v = (torch.randn(N, device=device, dtype=torch.float32) * 0.05).contiguous()

    # Warmup
    for _ in range(20):
        out_dq, out_metric = triton_poincare_discrete_relativistic_rs(q, v)
        ref_dq, ref_metric = torch_poincare_discrete_relativistic_rs_ref(q, v)
    torch.cuda.synchronize()

    # Numerical verification
    max_err_dq = (out_dq - ref_dq).abs().max().item()
    max_err_metric = (out_metric - ref_metric).abs().max().item()
    print(f"Max Absolute Error (dq): {max_err_dq:.3e}")
    print(f"Max Absolute Error (Metric): {max_err_metric:.3e}")
    assert max_err_dq < 1e-4, f"Numerical error too high: {max_err_dq}"
    assert max_err_metric < 1e-5, f"Metric error too high: {max_err_metric}"

    # Timing Triton
    iters = 200
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        out_dq, out_metric = triton_poincare_discrete_relativistic_rs(q, v)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_dq, ref_metric = torch_poincare_discrete_relativistic_rs_ref(q, v)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M particles/s")
