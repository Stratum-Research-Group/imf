"""
Cycle 252: Fused Poincaré Discrete Sine-Gordon Fluxon Breather Lattice Flow Kernel
Hardware Target: Workstation NVIDIA GeForce RTX 5060 Ti (SM 12.0 GB206)

Evaluates the discrete sine-Gordon (Frenkel-Kontorova fluxon) lattice dynamical flow:
    d^2 phi_n / dt^2 = C * (phi_{n+1} - 2 phi_n + phi_{n-1}) - omega_0^2 * sin(phi_n)
Projected to the Poincaré hyperbolic ball conformal metric:
    lambda_phi = 2.0 / (1.0 - ||phi_n||^2)
"""

import math
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_discrete_sine_gordon_kernel(
    phi_ptr,         # [N] field displacement / phase
    pi_ptr,          # [N] field momentum / velocity
    out_acc_ptr,     # [N] field acceleration
    out_metric_ptr,  # [N] conformal Riemannian metric factor
    coupling_c,      # inter-site coupling C
    omega_sq,        # Josephson plasma frequency squared omega_0^2
    N: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N

    idx_p1 = (idx + 1) % N
    idx_m1 = (idx - 1 + N) % N

    phi_curr = tl.load(phi_ptr + idx, mask=mask, other=0.0)
    phi_p1   = tl.load(phi_ptr + idx_p1, mask=mask, other=0.0)
    phi_m1   = tl.load(phi_ptr + idx_m1, mask=mask, other=0.0)

    # 1. Discrete spatial Laplacian: C * (phi_{n+1} - 2 phi_n + phi_{n-1})
    laplacian = phi_p1 - 2.0 * phi_curr + phi_m1

    # 2. Josephson junction non-linear periodic restoring force: - omega_0^2 * sin(phi_n)
    restoring_force = - omega_sq * tl.sin(phi_curr)

    acc = coupling_c * laplacian + restoring_force

    # 3. Poincaré hyperbolic metric conformal factor
    # Constrain phi for hyperbolic disk coordinate projection
    phi_sq = phi_curr * phi_curr
    phi_clamped = tl.minimum(phi_sq, 0.99)
    conf_metric = 2.0 / (1.0 - phi_clamped)

    fused_acc = acc * conf_metric

    tl.store(out_acc_ptr + idx, fused_acc, mask=mask)
    tl.store(out_metric_ptr + idx, conf_metric, mask=mask)

def triton_poincare_discrete_sine_gordon(phi: torch.Tensor, pi: torch.Tensor, coupling_c: float = 1.0, omega_sq: float = 1.0):
    assert phi.is_cuda and pi.is_cuda
    N = phi.numel()
    out_acc = torch.empty_like(phi)
    out_metric = torch.empty_like(phi)

    BLOCK_SIZE = 256
    grid = ((N + BLOCK_SIZE - 1) // BLOCK_SIZE,)

    _poincare_discrete_sine_gordon_kernel[grid](
        phi, pi, out_acc, out_metric,
        float(coupling_c), float(omega_sq),
        N=N, BLOCK_SIZE=BLOCK_SIZE
    )
    return out_acc, out_metric

def torch_poincare_discrete_sine_gordon_ref(phi: torch.Tensor, pi: torch.Tensor, coupling_c: float = 1.0, omega_sq: float = 1.0):
    phi_p1 = torch.roll(phi, shifts=-1, dims=0)
    phi_m1 = torch.roll(phi, shifts=1, dims=0)
    laplacian = phi_p1 - 2.0 * phi + phi_m1
    restoring_force = - omega_sq * torch.sin(phi)
    acc = coupling_c * laplacian + restoring_force
    phi_sq = torch.clamp(phi ** 2, max=0.99)
    conf_metric = 2.0 / (1.0 - phi_sq)
    return acc * conf_metric, conf_metric

if __name__ == "__main__":
    import time
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Executing Poincaré Discrete Sine-Gordon Kernel Benchmark on: {torch.cuda.get_device_name(0)}")

    N = 131072 # 128K lattice nodes
    phi = (torch.randn(N, device=device, dtype=torch.float32) * 0.2).contiguous()
    pi = (torch.randn(N, device=device, dtype=torch.float32) * 0.1).contiguous()

    # Warmup
    for _ in range(20):
        out_acc, out_metric = triton_poincare_discrete_sine_gordon(phi, pi)
        ref_acc, ref_metric = torch_poincare_discrete_sine_gordon_ref(phi, pi)
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
        out_acc, out_metric = triton_poincare_discrete_sine_gordon(phi, pi)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    # Timing PyTorch
    torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        ref_acc, ref_metric = torch_poincare_discrete_sine_gordon_ref(phi, pi)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    speedup = t_torch / t_triton
    throughput_m_nodes = (N / t_triton) / 1e6
    print(f"Triton Kernel Latency: {t_triton * 1e6:.2f} us")
    print(f"PyTorch Ref Latency:    {t_torch * 1e6:.2f} us")
    print(f"Hardware Speedup:       {speedup:.2f}x")
    print(f"Throughput:             {throughput_m_nodes:.2f} M nodes/s")
