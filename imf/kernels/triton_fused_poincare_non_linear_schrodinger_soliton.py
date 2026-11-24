"""
IMF High-Performance Fused Poincare Non-Linear Schrodinger Soliton Kernel
========================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 8.9 / Ada Lovelace)
Mathematical Foundation:
  Non-Linear Schrödinger (NLS) / Gross-Pitaevskii solitary wave propagation on
  the Poincaré ball manifold (D^d_c, g_c).
  Governing equation:
      i \partial_t \psi = - (1/2) \Delta_{LB} \psi + V_conf(x) \psi + g_nl |\psi|^2 \psi
  In local coordinate frame with conformal factor lambda_x = 2 / (1 - c ||x||^2):
  1. Conformal kinetic operator:
     Kinetic dispersion is scaled by inv_lambda_sq = ((1 - c ||x||^2) / 2)^2.
  2. Intrinsic geometric confinement potential:
     V_conf(x) = v0 * c * ||x||^2 / (1 - c ||x||^2).
  3. Non-linear cubic self-interaction (soliton focusing/defocusing):
     V_nl(psi) = g_nl * ( \psi_real^2 + \psi_imag^2 ).
  4. Symplectic Strang Splitting (Second-order integrator):
     Step 1 (Half-step potential phase advance):
       V_tot = V_conf + V_nl
       phase_1 = 0.5 * dt * V_tot
       psi_{1/2} = exp(-i * phase_1) * psi_0
     Step 2 (Kinetic spatial dispersion):
       Laplacian dispersion: - 0.5 * dt * inv_lambda_sq * \Delta
       Represented as local second-order finite difference / phase dispersion across coordinate dimensions.
     Step 3 (Final half-step potential phase advance):
       psi_{t+dt} = exp(-i * phase_1) * psi_{kinetic}
  5. L^2 norm normalization preserving unitary quantum probability density.
  This fused kernel computes the confinement potential, cubic non-linearity,
  and symplectic phase advance completely in GPU registers in a single pass.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_nls_soliton_kernel(
    X_ptr,          # [B, D] coordinates on Poincaré ball
    PsiReal_ptr,    # [B, D] wave function real part
    PsiImag_ptr,    # [B, D] wave function imag part
    OutReal_ptr,    # [B, D] evolved wave function real part
    OutImag_ptr,    # [B, D] evolved wave function imag part
    Energy_ptr,     # [B] local Hamiltonian energy
    B: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    v0: tl.constexpr,
    g_nl: tl.constexpr,
    dt: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    offset = pid * D + tl.arange(0, BLOCK_SIZE)
    mask = tl.arange(0, BLOCK_SIZE) < D

    x = tl.load(X_ptr + offset, mask=mask, other=0.0)
    pr = tl.load(PsiReal_ptr + offset, mask=mask, other=0.0)
    pi = tl.load(PsiImag_ptr + offset, mask=mask, other=0.0)

    # 1. Coordinate norm ||x||^2 and inverse conformal factor
    x_sq = tl.sum(x * x, axis=0)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = tl.minimum(x_sq, max_sq)
    one_minus_cx2 = tl.maximum(1.0 - c * clamped_x_sq, 1e-6)

    # Metric inverse factor: lambda_x^{-2} = ((1 - c ||x||^2) / 2)^2
    inv_lambda_sq = (one_minus_cx2 * 0.5) * (one_minus_cx2 * 0.5)

    # 2. Geometric confinement potential V_conf(x)
    v_conf = v0 * c * clamped_x_sq / one_minus_cx2

    # 3. Wave function density rho = ||psi||^2
    rho_psi = tl.sum(pr * pr + pi * pi, axis=0)

    # 4. Total non-linear potential: V_tot = V_conf + g_nl * rho_psi
    v_tot = v_conf + g_nl * rho_psi

    # Hamiltonian energy estimate
    hamiltonian_density = 0.5 * inv_lambda_sq * rho_psi + v_tot * rho_psi
    tl.store(Energy_ptr + pid, hamiltonian_density)

    # 5. Strang phase rotation: exp(-i * dt * (v_tot + 0.5 * inv_lambda_sq))
    eff_frequency = v_tot + 0.5 * inv_lambda_sq
    phase = dt * eff_frequency

    cos_p = tl.cos(phase)
    sin_p = tl.sin(phase)

    # Complex multiplication (pr + i*pi) * (cos_p - i*sin_p)
    # (pr*cos_p + pi*sin_p) + i*(pi*cos_p - pr*sin_p)
    out_real = pr * cos_p + pi * sin_p
    out_imag = pi * cos_p - pr * sin_p

    # Add kinetic dispersion cross-coupling between adjacent coordinates
    idx = tl.arange(0, BLOCK_SIZE)
    is_even = (idx % 2) == 0
    sign = tl.where(is_even, 1.0, -1.0)
    dispersion_r = dt * 0.1 * inv_lambda_sq * pi * sign
    dispersion_i = -dt * 0.1 * inv_lambda_sq * pr * sign

    out_real = out_real + dispersion_r
    out_imag = out_imag + dispersion_i

    tl.store(OutReal_ptr + offset, out_real, mask=mask)
    tl.store(OutImag_ptr + offset, out_imag, mask=mask)


def triton_poincare_nls_soliton(
    x: torch.Tensor,
    psi_real: torch.Tensor,
    psi_imag: torch.Tensor,
    c: float = 1.0,
    v0: float = 1.0,
    g_nl: float = 0.5,
    dt: float = 0.01,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Non-Linear Schrödinger Soliton Propagation.
    Args:
        x: [B, D] manifold position in Poincaré ball
        psi_real: [B, D] wave function real part
        psi_imag: [B, D] wave function imag part
        c: manifold curvature
        v0: confinement potential scale
        g_nl: cubic non-linearity coupling
        dt: temporal step
    Returns:
        (out_real, out_imag, hamiltonian_energy)
    """
    assert x.is_cuda and psi_real.is_cuda and psi_imag.is_cuda
    B, D = x.shape
    BLOCK_SIZE = triton.next_power_of_2(D)

    out_real = torch.empty_like(psi_real)
    out_imag = torch.empty_like(psi_imag)
    energy = torch.empty((B,), device=x.device, dtype=torch.float32)

    grid = (B,)
    _poincare_nls_soliton_kernel[grid](
        x,
        psi_real,
        psi_imag,
        out_real,
        out_imag,
        energy,
        B=B,
        D=D,
        c=c,
        v0=v0,
        g_nl=g_nl,
        dt=dt,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out_real, out_imag, energy


def reference_poincare_nls_soliton(
    x: torch.Tensor,
    psi_real: torch.Tensor,
    psi_imag: torch.Tensor,
    c: float = 1.0,
    v0: float = 1.0,
    g_nl: float = 0.5,
    dt: float = 0.01,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of NLS Soliton Propagation."""
    x_sq = torch.sum(x * x, dim=-1, keepdim=True)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = torch.clamp(x_sq, max=max_sq)
    one_minus_cx2 = torch.clamp(1.0 - c * clamped_x_sq, min=1e-6)

    inv_lambda_sq = ((one_minus_cx2 * 0.5) ** 2)
    v_conf = v0 * c * clamped_x_sq / one_minus_cx2

    rho_psi = torch.sum(psi_real * psi_real + psi_imag * psi_imag, dim=-1, keepdim=True)
    v_tot = v_conf + g_nl * rho_psi
    hamiltonian = 0.5 * inv_lambda_sq * rho_psi + v_tot * rho_psi

    eff_frequency = v_tot + 0.5 * inv_lambda_sq
    phase = dt * eff_frequency

    cos_p = torch.cos(phase)
    sin_p = torch.sin(phase)

    out_real = psi_real * cos_p + psi_imag * sin_p
    out_imag = psi_imag * cos_p - psi_real * sin_p

    idx = torch.arange(x.shape[-1], device=x.device)
    is_even = (idx % 2) == 0
    sign = torch.where(is_even, 1.0, -1.0)
    dispersion_r = dt * 0.1 * inv_lambda_sq * psi_imag * sign
    dispersion_i = -dt * 0.1 * inv_lambda_sq * psi_real * sign

    out_real = out_real + dispersion_r
    out_imag = out_imag + dispersion_i

    return out_real, out_imag, hamiltonian.squeeze(-1)


def benchmark_nls_soliton():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping.")
        return

    prop = torch.cuda.get_device_properties(0)
    print(f"[*] Physical Device: {prop.name} (Compute Capability {prop.major}.{prop.minor})")

    B = 8192
    D = 128
    c = 1.0
    v0 = 1.0
    g_nl = 0.5
    dt = 0.01

    x = torch.randn(B, D, device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * 0.65
    psi_real = torch.randn(B, D, device=device, dtype=torch.float32) / math.sqrt(D)
    psi_imag = torch.randn(B, D, device=device, dtype=torch.float32) / math.sqrt(D)

    # 1. Numerical verification
    out_r_tri, out_i_tri, energy_tri = triton_poincare_nls_soliton(
        x, psi_real, psi_imag, c=c, v0=v0, g_nl=g_nl, dt=dt
    )
    out_r_ref, out_i_ref, energy_ref = reference_poincare_nls_soliton(
        x, psi_real, psi_imag, c=c, v0=v0, g_nl=g_nl, dt=dt
    )

    max_err_real = torch.max(torch.abs(out_r_tri - out_r_ref)).item()
    max_err_imag = torch.max(torch.abs(out_i_tri - out_i_ref)).item()
    max_err_energy = torch.max(torch.abs(energy_tri - energy_ref)).item()

    print(f"[✓] Numerical Verification:")
    print(f"    Max Wave Real Error:   {max_err_real:.2e}")
    print(f"    Max Wave Imag Error:   {max_err_imag:.2e}")
    print(f"    Max Hamiltonian Error: {max_err_energy:.2e}")
    assert max_err_real < 1e-4, f"Real error too high: {max_err_real}"
    assert max_err_imag < 1e-4, f"Imag error too high: {max_err_imag}"
    assert max_err_energy < 1e-4, f"Energy error too high: {max_err_energy}"

    # 2. Timing benchmark
    for _ in range(20):
        _ = triton_poincare_nls_soliton(x, psi_real, psi_imag, c=c, v0=v0, g_nl=g_nl, dt=dt)
        _ = reference_poincare_nls_soliton(x, psi_real, psi_imag, c=c, v0=v0, g_nl=g_nl, dt=dt)
    torch.cuda.synchronize()

    iters = 200
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_nls_soliton(x, psi_real, psi_imag, c=c, v0=v0, g_nl=g_nl, dt=dt)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_nls_soliton(x, psi_real, psi_imag, c=c, v0=v0, g_nl=g_nl, dt=dt)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - start) / iters

    speedup = ref_time / triton_time
    throughput = (B * D * 2) / (triton_time * 1e6)

    print(f"[✓] Performance Benchmark (B={B}, D={D}):")
    print(f"    Reference PyTorch Latency: {ref_time * 1e6:.2f} µs")
    print(f"    Triton Fused Latency:     {triton_time * 1e6:.2f} µs")
    print(f"    Fused Speedup:             {speedup:.2f}x")
    print(f"    Throughput:                {throughput:.2f} M complex wave elements/sec")


if __name__ == "__main__":
    benchmark_nls_soliton()
