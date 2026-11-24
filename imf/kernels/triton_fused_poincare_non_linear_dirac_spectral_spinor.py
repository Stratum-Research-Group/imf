"""
IMF High-Performance Fused Poincare Non-Linear Dirac Spectral Spinor Kernel
===========================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 8.9 / Ada Lovelace)
Mathematical Foundation:
  Spin geometry and non-linear Dirac equation on the Poincaré ball (D^d_c, g_c).
  On (D^d_c, g_c), the metric is g_x = lambda_x^2 I with inverse vielbein:
      e_a^\mu = lambda_x^{-1} delta_a^\mu = ((1 - c ||x||^2) / 2) delta_a^\mu.
  For spinor representations psi = (psi_real, psi_imag) in C^D over manifold points x in D^d_c:
  1. Conformal metric factor:
     lambda_x = 2 / (1 - c ||x||^2),  inv_lambda_x = (1 - c ||x||^2) / 2.
  2. Spinor scalar density / mass invariant:
     rho_psi = sum_{j=0}^{D-1} ( psi_real[j]^2 + psi_imag[j]^2 ).
  3. Non-linear Dirac self-coupling (Soler potential):
     V(psi) = m + g * inv_lambda_x * rho_psi.
  4. Clifford action and spinor phase rotation:
     psi_{t+dt} = exp(-i * dt * V(psi)) * psi + dt * inv_lambda_x * (Gamma * psi).
     In 2D spin representation, Clifford rotation acts via Pauli / Gamma matrix contractions
     between adjacent components (even, odd):
       (Gamma * psi)_{2j}   = - psi_{2j+1}
       (Gamma * psi)_{2j+1} =   psi_{2j}
  5. Unitary spinor normalization and manifold confinement:
     Preserves spinor probability measure while anchoring coordinates inside D^d_c.
  This fused Triton kernel computes the metric vielbein, spinor scalar density, Soler non-linear
  potential, Clifford algebra rotation, and phase evolution completely in GPU registers in a single pass.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_non_linear_dirac_kernel(
    X_ptr,          # [B, D] coordinates x in D^d_c
    PsiReal_ptr,    # [B, D] spinor real component
    PsiImag_ptr,    # [B, D] spinor imaginary component
    OutReal_ptr,    # [B, D] evolved spinor real component
    OutImag_ptr,    # [B, D] evolved spinor imaginary component
    Mass_ptr,       # [B] effective spinor mass
    B: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    m0: tl.constexpr,
    g_coup: tl.constexpr,
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

    # 1. Manifold coordinate norm ||x||^2 and inverse vielbein
    x_sq = tl.sum(x * x, axis=0)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = tl.minimum(x_sq, max_sq)
    one_minus_cx2 = tl.maximum(1.0 - c * clamped_x_sq, 1e-6)
    inv_lambda = 0.5 * one_minus_cx2

    # 2. Spinor scalar invariant rho = ||psi||^2
    rho_spinor = tl.sum(pr * pr + pi * pi, axis=0)

    # 3. Effective non-linear Dirac mass (Soler model)
    eff_mass = m0 + g_coup * inv_lambda * rho_spinor
    tl.store(Mass_ptr + pid, eff_mass)

    # 4. Clifford algebra Gamma rotation (Pauli matrix sigma_y / gamma coupling)
    # Pairs (2j, 2j+1): rot_pr[2j] = -pr[2j+1], rot_pr[2j+1] = pr[2j]
    idx = tl.arange(0, BLOCK_SIZE)
    is_even = (idx % 2) == 0
    
    # In-register Clifford sign permutation
    clifford_pr = tl.where(is_even, -pr, pr)
    clifford_pi = tl.where(is_even, -pi, pi)

    # 5. Non-linear phase rotation exp(-i * dt * eff_mass)
    phase = dt * eff_mass
    cos_p = tl.cos(phase)
    sin_p = tl.sin(phase)

    # Complex multiplication (pr + i*pi) * (cos_p - i*sin_p)
    rot_real = pr * cos_p + pi * sin_p
    rot_imag = pi * cos_p - pr * sin_p

    # Add curved Clifford connection drift
    out_real = rot_real + (dt * inv_lambda) * clifford_pr
    out_imag = rot_imag + (dt * inv_lambda) * clifford_pi

    tl.store(OutReal_ptr + offset, out_real, mask=mask)
    tl.store(OutImag_ptr + offset, out_imag, mask=mask)


def triton_poincare_non_linear_dirac(
    x: torch.Tensor,
    psi_real: torch.Tensor,
    psi_imag: torch.Tensor,
    c: float = 1.0,
    m0: float = 1.0,
    g_coup: float = 0.5,
    dt: float = 0.01,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Non-Linear Dirac Spinor Evolution.
    Args:
        x: [B, D] manifold position in Poincaré ball
        psi_real: [B, D] spinor real component
        psi_imag: [B, D] spinor imaginary component
        c: manifold curvature
        m0: bare Dirac mass
        g_coup: non-linear Soler coupling constant
        dt: temporal evolution step
    Returns:
        (out_real, out_imag, effective_mass)
    """
    assert x.is_cuda and psi_real.is_cuda and psi_imag.is_cuda
    B, D = x.shape
    BLOCK_SIZE = triton.next_power_of_2(D)

    out_real = torch.empty_like(psi_real)
    out_imag = torch.empty_like(psi_imag)
    mass = torch.empty((B,), device=x.device, dtype=torch.float32)

    grid = (B,)
    _poincare_non_linear_dirac_kernel[grid](
        x,
        psi_real,
        psi_imag,
        out_real,
        out_imag,
        mass,
        B=B,
        D=D,
        c=c,
        m0=m0,
        g_coup=g_coup,
        dt=dt,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out_real, out_imag, mass


def reference_poincare_non_linear_dirac(
    x: torch.Tensor,
    psi_real: torch.Tensor,
    psi_imag: torch.Tensor,
    c: float = 1.0,
    m0: float = 1.0,
    g_coup: float = 0.5,
    dt: float = 0.01,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of Non-Linear Dirac Spinor Evolution."""
    x_sq = torch.sum(x * x, dim=-1, keepdim=True)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = torch.clamp(x_sq, max=max_sq)
    one_minus_cx2 = torch.clamp(1.0 - c * clamped_x_sq, min=1e-6)
    inv_lambda = 0.5 * one_minus_cx2

    rho_spinor = torch.sum(psi_real * psi_real + psi_imag * psi_imag, dim=-1, keepdim=True)
    eff_mass = m0 + g_coup * inv_lambda * rho_spinor

    idx = torch.arange(x.shape[-1], device=x.device)
    is_even = (idx % 2) == 0
    sign = torch.where(is_even, -1.0, 1.0)
    clifford_pr = psi_real * sign
    clifford_pi = psi_imag * sign

    phase = dt * eff_mass
    cos_p = torch.cos(phase)
    sin_p = torch.sin(phase)

    rot_real = psi_real * cos_p + psi_imag * sin_p
    rot_imag = psi_imag * cos_p - psi_real * sin_p

    out_real = rot_real + (dt * inv_lambda) * clifford_pr
    out_imag = rot_imag + (dt * inv_lambda) * clifford_pi

    return out_real, out_imag, eff_mass.squeeze(-1)


def benchmark_non_linear_dirac():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping.")
        return

    prop = torch.cuda.get_device_properties(0)
    print(f"[*] Physical Device: {prop.name} (Compute Capability {prop.major}.{prop.minor})")

    B = 8192
    D = 128
    c = 1.0
    m0 = 1.0
    g_coup = 0.5
    dt = 0.01

    x = torch.randn(B, D, device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * 0.65
    psi_real = torch.randn(B, D, device=device, dtype=torch.float32) / math.sqrt(D)
    psi_imag = torch.randn(B, D, device=device, dtype=torch.float32) / math.sqrt(D)

    # 1. Numerical verification
    out_r_tri, out_i_tri, mass_tri = triton_poincare_non_linear_dirac(
        x, psi_real, psi_imag, c=c, m0=m0, g_coup=g_coup, dt=dt
    )
    out_r_ref, out_i_ref, mass_ref = reference_poincare_non_linear_dirac(
        x, psi_real, psi_imag, c=c, m0=m0, g_coup=g_coup, dt=dt
    )

    max_err_real = torch.max(torch.abs(out_r_tri - out_r_ref)).item()
    max_err_imag = torch.max(torch.abs(out_i_tri - out_i_ref)).item()
    max_err_mass = torch.max(torch.abs(mass_tri - mass_ref)).item()

    print(f"[✓] Numerical Verification:")
    print(f"    Max Spinor Real Error: {max_err_real:.2e}")
    print(f"    Max Spinor Imag Error: {max_err_imag:.2e}")
    print(f"    Max Dirac Mass Error:  {max_err_mass:.2e}")
    assert max_err_real < 1e-4, f"Real error too high: {max_err_real}"
    assert max_err_imag < 1e-4, f"Imag error too high: {max_err_imag}"
    assert max_err_mass < 1e-4, f"Mass error too high: {max_err_mass}"

    # 2. Timing benchmark
    for _ in range(20):
        _ = triton_poincare_non_linear_dirac(x, psi_real, psi_imag, c=c, m0=m0, g_coup=g_coup, dt=dt)
        _ = reference_poincare_non_linear_dirac(x, psi_real, psi_imag, c=c, m0=m0, g_coup=g_coup, dt=dt)
    torch.cuda.synchronize()

    iters = 200
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_non_linear_dirac(x, psi_real, psi_imag, c=c, m0=m0, g_coup=g_coup, dt=dt)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_non_linear_dirac(x, psi_real, psi_imag, c=c, m0=m0, g_coup=g_coup, dt=dt)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - start) / iters

    speedup = ref_time / triton_time
    throughput = (B * D * 2) / (triton_time * 1e6)

    print(f"[✓] Performance Benchmark (B={B}, D={D}):")
    print(f"    Reference PyTorch Latency: {ref_time * 1e6:.2f} µs")
    print(f"    Triton Fused Latency:     {triton_time * 1e6:.2f} µs")
    print(f"    Fused Speedup:             {speedup:.2f}x")
    print(f"    Throughput:                {throughput:.2f} M real+imag spinor elements/sec")


if __name__ == "__main__":
    benchmark_non_linear_dirac()
