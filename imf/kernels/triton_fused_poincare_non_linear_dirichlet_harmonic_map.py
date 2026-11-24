"""
IMF High-Performance Fused Poincare Non-Linear Dirichlet Harmonic Map Kernel
===========================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 8.9 / Ada Lovelace)
Mathematical Foundation:
  Non-linear Dirichlet energy and harmonic map heat flow between Poincaré manifolds:
      u: (D^d_{c_1}, g) -> (D^d_{c_2}, h).
  Given source coordinate x in D^d_{c_1} and target mapping coordinate u in D^d_{c_2}.
  1. Source inverse metric factor:
     lambda_x^{-2} = ((1 - c_1 ||x||^2) / 2)^2.
  2. Target metric conformal factor:
     lambda_u = 2 / (1 - c_2 ||u||^2).
  3. Given Jacobian / gradient matrix representation J = \nabla u in R^{d x d},
     the non-linear Dirichlet energy density is:
     e(u) = (1/2) * lambda_x^{-2} * lambda_u^2 * ||J||_F^2.
  4. Tension field tau(u) in the target tangent space T_u D^d_{c_2}:
     tau(u) = \Delta_g u + \Gamma^h(u)(\nabla u, \nabla u).
     For the Poincaré metric, the Christoffel contraction simplifies to:
     \Gamma^h(u)(J, J)^\alpha = (2 c_2 / (1 - c_2 ||u||^2)) * ( 2 <u, J_i> J_i^\alpha - ||J_i||^2 u^\alpha ).
     In simplified channel-wise form for gradient descent step:
     tau(u) = \Delta_g u + (2 c_2 / (1 - c_2 ||u||^2)) * ( ||J||_F^2 * u ).
  5. Eells-Sampson harmonic heat flow update:
     u_{t+dt} = u + dt * ( lambda_x^{-2} * \Delta u - (2 c_2 lambda_x^{-2} / (1 - c_2 ||u||^2)) * (||J||_F^2) * u ),
     followed by strict boundary projection ||u_{t+dt}||^2 <= (1 - eps) / c_2.
  This fused Triton kernel computes the Dirichlet energy density, Christoffel tension drift,
  and harmonic heat flow update completely in GPU registers in a single pass.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_harmonic_map_kernel(
    X_ptr,          # [B, D] source points in D^d_{c_1}
    U_ptr,          # [B, D] target points in D^d_{c_2}
    LapU_ptr,       # [B, D] Laplacian / gradient drift \Delta u
    OutU_ptr,       # [B, D] updated target points u_{t+dt}
    Energy_ptr,     # [B] Dirichlet energy density e(u)
    B: tl.constexpr,
    D: tl.constexpr,
    c1: tl.constexpr,
    c2: tl.constexpr,
    dt: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    offset = pid * D + tl.arange(0, BLOCK_SIZE)
    mask = tl.arange(0, BLOCK_SIZE) < D

    x = tl.load(X_ptr + offset, mask=mask, other=0.0)
    u = tl.load(U_ptr + offset, mask=mask, other=0.0)
    lap_u = tl.load(LapU_ptr + offset, mask=mask, other=0.0)

    # 1. Source metric factor lambda_x^{-2}
    x_sq = tl.sum(x * x, axis=0)
    max_sq_1 = (1.0 - 1e-4) / c1
    clamped_x_sq = tl.minimum(x_sq, max_sq_1)
    one_minus_c1_x2 = tl.maximum(1.0 - c1 * clamped_x_sq, 1e-6)
    inv_lambda_x_sq = (one_minus_c1_x2 * 0.5) * (one_minus_c1_x2 * 0.5)

    # 2. Target metric factor lambda_u
    u_sq = tl.sum(u * u, axis=0)
    max_sq_2 = (1.0 - 1e-4) / c2
    clamped_u_sq = tl.minimum(u_sq, max_sq_2)
    one_minus_c2_u2 = tl.maximum(1.0 - c2 * clamped_u_sq, 1e-6)
    lambda_u = 2.0 / one_minus_c2_u2
    lambda_u_sq = lambda_u * lambda_u

    # 3. Dirichlet energy density: e(u) = 0.5 * inv_lambda_x_sq * lambda_u_sq * ||lap_u||^2
    lap_norm_sq = tl.sum(lap_u * lap_u, axis=0)
    dirichlet_energy = 0.5 * inv_lambda_x_sq * lambda_u_sq * lap_norm_sq
    tl.store(Energy_ptr + pid, dirichlet_energy)

    # 4. Christoffel tension term: Gamma(u)(grad, grad) ~ (2 * c2 / (1 - c2 * ||u||^2)) * lap_norm_sq * u
    christoffel_factor = (2.0 * c2 / one_minus_c2_u2) * lap_norm_sq

    # 5. Harmonic map heat flow tension field: tau(u) = lap_u - christoffel_factor * u
    tau_u = lap_u - christoffel_factor * u

    # Update u_{t+dt} = u + dt * inv_lambda_x_sq * tau_u
    u_next = u + dt * inv_lambda_x_sq * tau_u

    # 6. Strict boundary projection in target manifold D^d_{c_2}
    u_next_sq = tl.sum(u_next * u_next, axis=0)
    scale = 1.0
    if u_next_sq > max_sq_2:
        scale = tl.sqrt(max_sq_2 / u_next_sq)
    u_next = u_next * scale

    tl.store(OutU_ptr + offset, u_next, mask=mask)


def triton_poincare_non_linear_dirichlet_harmonic_map(
    x: torch.Tensor,
    u: torch.Tensor,
    lap_u: torch.Tensor,
    c1: float = 1.0,
    c2: float = 1.0,
    dt: float = 0.01,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Non-Linear Dirichlet Harmonic Map Kernel.
    Args:
        x: [B, D] source points in D^d_{c_1}
        u: [B, D] target points in D^d_{c_2}
        lap_u: [B, D] Laplacian drift \Delta u
        c1: source curvature
        c2: target curvature
        dt: step size
    Returns:
        (u_next, dirichlet_energy)
    """
    assert x.is_cuda and u.is_cuda and lap_u.is_cuda
    B, D = x.shape
    BLOCK_SIZE = triton.next_power_of_2(D)

    out_u = torch.empty_like(u)
    energy = torch.empty((B,), device=x.device, dtype=torch.float32)

    grid = (B,)
    _poincare_harmonic_map_kernel[grid](
        x,
        u,
        lap_u,
        out_u,
        energy,
        B=B,
        D=D,
        c1=c1,
        c2=c2,
        dt=dt,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out_u, energy


def reference_poincare_harmonic_map(
    x: torch.Tensor,
    u: torch.Tensor,
    lap_u: torch.Tensor,
    c1: float = 1.0,
    c2: float = 1.0,
    dt: float = 0.01,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of Harmonic Map Heat Flow."""
    x_sq = torch.sum(x * x, dim=-1, keepdim=True)
    max_sq_1 = (1.0 - 1e-4) / c1
    clamped_x_sq = torch.clamp(x_sq, max=max_sq_1)
    one_minus_c1_x2 = torch.clamp(1.0 - c1 * clamped_x_sq, min=1e-6)
    inv_lambda_x_sq = ((one_minus_c1_x2 * 0.5) ** 2)

    u_sq = torch.sum(u * u, dim=-1, keepdim=True)
    max_sq_2 = (1.0 - 1e-4) / c2
    clamped_u_sq = torch.clamp(u_sq, max=max_sq_2)
    one_minus_c2_u2 = torch.clamp(1.0 - c2 * clamped_u_sq, min=1e-6)
    lambda_u = 2.0 / one_minus_c2_u2
    lambda_u_sq = lambda_u ** 2

    lap_norm_sq = torch.sum(lap_u * lap_u, dim=-1, keepdim=True)
    dirichlet_energy = 0.5 * inv_lambda_x_sq * lambda_u_sq * lap_norm_sq

    christoffel_factor = (2.0 * c2 / one_minus_c2_u2) * lap_norm_sq
    tau_u = lap_u - christoffel_factor * u

    u_next = u + dt * inv_lambda_x_sq * tau_u

    u_next_sq = torch.sum(u_next * u_next, dim=-1, keepdim=True)
    scale = torch.where(u_next_sq > max_sq_2, torch.sqrt(max_sq_2 / u_next_sq), torch.ones_like(u_next_sq))
    u_next = u_next * scale

    return u_next, dirichlet_energy.squeeze(-1)


def benchmark_harmonic_map():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping.")
        return

    prop = torch.cuda.get_device_properties(0)
    print(f"[*] Physical Device: {prop.name} (Compute Capability {prop.major}.{prop.minor})")

    B = 8192
    D = 128
    c1 = 1.0
    c2 = 1.0
    dt = 0.01

    x = torch.randn(B, D, device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * 0.65
    u = torch.randn(B, D, device=device, dtype=torch.float32)
    u = u / (torch.norm(u, dim=-1, keepdim=True) + 1e-5) * 0.65
    lap_u = torch.randn(B, D, device=device, dtype=torch.float32) / math.sqrt(D)

    # 1. Numerical verification
    out_tri, energy_tri = triton_poincare_non_linear_dirichlet_harmonic_map(x, u, lap_u, c1=c1, c2=c2, dt=dt)
    out_ref, energy_ref = reference_poincare_harmonic_map(x, u, lap_u, c1=c1, c2=c2, dt=dt)

    max_err_out = torch.max(torch.abs(out_tri - out_ref)).item()
    max_err_energy = torch.max(torch.abs(energy_tri - energy_ref)).item()

    print(f"[✓] Numerical Verification:")
    print(f"    Max Coordinate Output Error: {max_err_out:.2e}")
    print(f"    Max Dirichlet Energy Error:  {max_err_energy:.2e}")
    assert max_err_out < 1e-4, f"Output error too high: {max_err_out}"
    assert max_err_energy < 1e-4, f"Energy error too high: {max_err_energy}"

    # 2. Timing benchmark
    for _ in range(20):
        _ = triton_poincare_non_linear_dirichlet_harmonic_map(x, u, lap_u, c1=c1, c2=c2, dt=dt)
        _ = reference_poincare_harmonic_map(x, u, lap_u, c1=c1, c2=c2, dt=dt)
    torch.cuda.synchronize()

    iters = 200
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_non_linear_dirichlet_harmonic_map(x, u, lap_u, c1=c1, c2=c2, dt=dt)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_harmonic_map(x, u, lap_u, c1=c1, c2=c2, dt=dt)
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
    benchmark_harmonic_map()
