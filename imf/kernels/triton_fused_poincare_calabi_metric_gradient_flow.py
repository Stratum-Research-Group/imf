"""
IMF High-Performance Fused Poincare Calabi Metric Gradient Flow Kernel
======================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 12.0 / Blackwell)
Mathematical Foundation:
  Calabi flow of the scalar curvature functional on Kähler hyperbolic manifolds (D^d_c, g_c).
  The Calabi energy of a metric g in Kähler class [\omega] is:
      C(g) = \int_M (R(g) - \bar{R})^2 \, d\mu_g.
  The Calabi flow is the L^2-gradient flow of C(g):
      \partial_t g_{i\bar{j}} = \nabla_i \nabla_{\bar{j}} R(g),
  which is a fourth-order parabolic geometric partial differential equation.
  In coordinate representation on the Poincaré ball with conformal metric g_z = \lambda_z^2 I_d:
  1. Conformal factor: lambda_z = 2 / (1 - c ||z||^2),  inv_lambda_z_sq = ((1 - c ||z||^2) / 2)^2.
  2. Local scalar curvature R(z):
     R(z) = - 2 * c * d - \Delta_{LB} log(\lambda_z).
  3. Given scalar curvature Laplacian / gradient signal \Delta R in R^d:
     The biharmonic drift driving metric toward extremal Kähler metric is:
     drift_z = \lambda_z^{-2} \Delta R(z) - \gamma * (R(z) - \bar{R}) * z.
  4. Flow integration with implicit boundary metric confinement:
     z_{t+dt} = z + dt * drift_z,
     followed by strict boundary projection ||z_{t+dt}||^2 <= (1 - eps)/c.
  This fused Triton kernel evaluates the scalar curvature deviation, biharmonic drift,
  Calabi energy density, and metric update in GPU registers in a single pass.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_calabi_flow_kernel(
    Z_ptr,          # [B, D] input coordinates in D^d_c
    LapR_ptr,       # [B, D] scalar curvature gradient/Laplacian \Delta R
    OutZ_ptr,       # [B, D] updated coordinates z_{t+dt}
    Energy_ptr,     # [B] local Calabi energy density (R - R_bar)^2
    B: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    r_bar: tl.constexpr,
    gamma: tl.constexpr,
    dt: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    offset = pid * D + tl.arange(0, BLOCK_SIZE)
    mask = tl.arange(0, BLOCK_SIZE) < D

    z = tl.load(Z_ptr + offset, mask=mask, other=0.0)
    lap_r = tl.load(LapR_ptr + offset, mask=mask, other=0.0)

    # 1. Conformal factor on Poincaré ball
    z_sq = tl.sum(z * z, axis=0)
    max_sq = (1.0 - 1e-4) / c
    clamped_z_sq = tl.minimum(z_sq, max_sq)
    one_minus_cz2 = tl.maximum(1.0 - c * clamped_z_sq, 1e-6)
    inv_lambda_sq = (one_minus_cz2 * 0.5) * (one_minus_cz2 * 0.5)

    # 2. Local scalar curvature R(z) approximation
    # For hyperbolic metric, curvature is -2*c*D + boundary defect
    r_loc = -2.0 * c * D - c * clamped_z_sq / one_minus_cz2
    r_diff = r_loc - r_bar

    # Calabi energy density: (R - \bar{R})^2
    calabi_energy = r_diff * r_diff
    tl.store(Energy_ptr + pid, calabi_energy)

    # 3. Fourth-order Calabi drift: inv_lambda_sq * lap_r - gamma * r_diff * z
    drift = inv_lambda_sq * lap_r - gamma * r_diff * z

    # 4. Update coordinates z_{t+dt} = z + dt * drift
    z_next = z + dt * drift

    # 5. Strict boundary projection in D^d_c
    z_next_sq = tl.sum(z_next * z_next, axis=0)
    scale = 1.0
    if z_next_sq > max_sq:
        scale = tl.sqrt(max_sq / z_next_sq)
    z_next = z_next * scale

    tl.store(OutZ_ptr + offset, z_next, mask=mask)


def triton_poincare_calabi_metric_gradient_flow(
    z: torch.Tensor,
    lap_r: torch.Tensor,
    c: float = 1.0,
    r_bar: float = -256.0,
    gamma: float = 0.05,
    dt: float = 0.01,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Calabi Metric Gradient Flow Kernel.
    Args:
        z: [B, D] manifold coordinates in Poincaré ball
        lap_r: [B, D] scalar curvature biharmonic gradient
        c: manifold curvature
        r_bar: average scalar curvature
        gamma: metric restoring damping
        dt: temporal step size
    Returns:
        (z_next, calabi_energy)
    """
    assert z.is_cuda and lap_r.is_cuda
    B, D = z.shape
    BLOCK_SIZE = triton.next_power_of_2(D)

    out_z = torch.empty_like(z)
    energy = torch.empty((B,), device=z.device, dtype=torch.float32)

    grid = (B,)
    _poincare_calabi_flow_kernel[grid](
        z,
        lap_r,
        out_z,
        energy,
        B=B,
        D=D,
        c=c,
        r_bar=r_bar,
        gamma=gamma,
        dt=dt,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out_z, energy


def reference_poincare_calabi_flow(
    z: torch.Tensor,
    lap_r: torch.Tensor,
    c: float = 1.0,
    r_bar: float = -256.0,
    gamma: float = 0.05,
    dt: float = 0.01,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of Calabi Flow."""
    B, D = z.shape
    z_sq = torch.sum(z * z, dim=-1, keepdim=True)
    max_sq = (1.0 - 1e-4) / c
    clamped_z_sq = torch.clamp(z_sq, max=max_sq)
    one_minus_cz2 = torch.clamp(1.0 - c * clamped_z_sq, min=1e-6)
    inv_lambda_sq = ((one_minus_cz2 * 0.5) ** 2)

    r_loc = -2.0 * c * float(D) - c * clamped_z_sq / one_minus_cz2
    r_diff = r_loc - r_bar
    calabi_energy = r_diff * r_diff

    drift = inv_lambda_sq * lap_r - gamma * r_diff * z
    z_next = z + dt * drift

    z_next_sq = torch.sum(z_next * z_next, dim=-1, keepdim=True)
    scale = torch.where(z_next_sq > max_sq, torch.sqrt(max_sq / z_next_sq), torch.ones_like(z_next_sq))
    z_next = z_next * scale

    return z_next, calabi_energy.squeeze(-1)


def benchmark_calabi_flow():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping.")
        return

    prop = torch.cuda.get_device_properties(0)
    print(f"[*] Physical Device: {prop.name} (Compute Capability {prop.major}.{prop.minor})")

    B = 8192
    D = 128
    c = 1.0
    r_bar = -2.0 * c * D
    gamma = 0.05
    dt = 0.01

    z = torch.randn(B, D, device=device, dtype=torch.float32)
    z = z / (torch.norm(z, dim=-1, keepdim=True) + 1e-5) * 0.65
    lap_r = torch.randn(B, D, device=device, dtype=torch.float32)

    # 1. Numerical verification
    out_tri, e_tri = triton_poincare_calabi_metric_gradient_flow(z, lap_r, c=c, r_bar=r_bar, gamma=gamma, dt=dt)
    out_ref, e_ref = reference_poincare_calabi_flow(z, lap_r, c=c, r_bar=r_bar, gamma=gamma, dt=dt)

    max_err_out = torch.max(torch.abs(out_tri - out_ref)).item()
    max_err_e = torch.max(torch.abs(e_tri - e_ref)).item()

    print(f"[✓] Numerical Verification:")
    print(f"    Max Coordinate Output Error: {max_err_out:.2e}")
    print(f"    Max Calabi Energy Error:     {max_err_e:.2e}")
    assert max_err_out < 1e-4, f"Output error too high: {max_err_out}"
    assert max_err_e < 1e-3, f"Energy error too high: {max_err_e}"

    # 2. Timing benchmark
    for _ in range(20):
        _ = triton_poincare_calabi_metric_gradient_flow(z, lap_r, c=c, r_bar=r_bar, gamma=gamma, dt=dt)
        _ = reference_poincare_calabi_flow(z, lap_r, c=c, r_bar=r_bar, gamma=gamma, dt=dt)
    torch.cuda.synchronize()

    iters = 200
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_calabi_metric_gradient_flow(z, lap_r, c=c, r_bar=r_bar, gamma=gamma, dt=dt)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_calabi_flow(z, lap_r, c=c, r_bar=r_bar, gamma=gamma, dt=dt)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - start) / iters

    speedup = ref_time / triton_time
    throughput = (B * D) / (triton_time * 1e6)

    print(f"[✓] Performance Benchmark (B={B}, D={D}):")
    print(f"    Reference PyTorch Latency: {ref_time * 1e6:.2f} µs")
    print(f"    Triton Fused Latency:     {triton_time * 1e6:.2f} µs")
    print(f"    Fused Speedup:             {speedup:.2f}x")
    print(f"    Throughput:                {throughput:.2f} M elements/sec")


if __name__ == "__main__":
    benchmark_calabi_flow()
