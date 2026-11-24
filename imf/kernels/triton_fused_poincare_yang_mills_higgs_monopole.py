"""
IMF High-Performance Fused Poincare Yang-Mills-Higgs Monopole Kernel
===================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 8.9 / Ada Lovelace)
Mathematical Foundation:
  Bogomolny Prasad-Sommerfield (BPS) Yang-Mills-Higgs monopoles on the Poincaré ball (D^d_c, g_c).
  In non-Abelian gauge theory on hyperbolic symmetric spaces, an SU(2) gauge connection A
  coupled to an adjoint Higgs scalar field \Phi in su(2) satisfies the Bogomolny equations:
      B_i = D_i \Phi = \partial_i \Phi + [A_i, \Phi],
  where B_i = (1/2) \epsilon_{ijk} F_{jk} is the non-Abelian magnetic field.
  1. Conformal metric factor:
     lambda_x = 2 / (1 - c ||x||^2),  inv_lambda_sq = ((1 - c ||x||^2) / 2)^2.
  2. Adjoint Higgs field \Phi = (\phi_1, \phi_2, \phi_3) in su(2).
  3. Non-Abelian gauge link cross-terms:
     [A, \Phi]_a = \sum_{b, c} \epsilon_{abc} A_b \phi_c.
  4. Covariant derivative / Magnetic BPS field:
     D_i \Phi = \nabla_i \Phi + [A_i, \Phi].
  5. BPS Monopole Energy density:
     E_{BPS} = (1/2) * inv_lambda_sq * ( ||B||^2 + ||D \Phi||^2 ).
     Under the BPS condition B = D \Phi:
     E_{BPS} = inv_lambda_sq * ||D \Phi||^2.
  6. Topological magnetic charge density:
     m(x) = (1 / 4pi) * \sum_{a=1}^3 \hat{\phi}_a B_a, where \hat{\phi} = \Phi / ||\Phi||.
  This fused Triton kernel evaluates the metric inverse factor, non-Abelian commutator [A, \Phi],
  Higgs covariant derivative, BPS energy density, and magnetic charge density in GPU registers.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_monopole_kernel(
    X_ptr,          # [B, D] coordinates on Poincaré ball
    Phi_ptr,        # [B, 3] adjoint Higgs field \Phi
    A_ptr,          # [B, 3] gauge field connection A
    GradPhi_ptr,    # [B, 3] spatial gradient \nabla \Phi
    Energy_ptr,     # [B] BPS energy density
    Charge_ptr,     # [B] magnetic charge density m(x)
    B: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    offset = pid * D + tl.arange(0, BLOCK_SIZE)
    mask = tl.arange(0, BLOCK_SIZE) < D

    x = tl.load(X_ptr + offset, mask=mask, other=0.0)

    # 1. Conformal factor on Poincaré ball
    x_sq = tl.sum(x * x, axis=0)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = tl.minimum(x_sq, max_sq)
    one_minus_cx2 = tl.maximum(1.0 - c * clamped_x_sq, 1e-6)
    inv_lambda_sq = (one_minus_cx2 * 0.5) * (one_minus_cx2 * 0.5)

    # 2. Load Higgs field \Phi = (p0, p1, p2)
    p0 = tl.load(Phi_ptr + pid * 3 + 0)
    p1 = tl.load(Phi_ptr + pid * 3 + 1)
    p2 = tl.load(Phi_ptr + pid * 3 + 2)

    # Load gauge connection A = (a0, a1, a2)
    a0 = tl.load(A_ptr + pid * 3 + 0)
    a1 = tl.load(A_ptr + pid * 3 + 1)
    a2 = tl.load(A_ptr + pid * 3 + 2)

    # Load gradient \nabla \Phi = (g0, g1, g2)
    g0 = tl.load(GradPhi_ptr + pid * 3 + 0)
    g1 = tl.load(GradPhi_ptr + pid * 3 + 1)
    g2 = tl.load(GradPhi_ptr + pid * 3 + 2)

    # 3. Non-Abelian commutator [A, \Phi]: cross product in su(2)
    comm0 = a1 * p2 - a2 * p1
    comm1 = a2 * p0 - a0 * p2
    comm2 = a0 * p1 - a1 * p0

    # 4. Covariant derivative D \Phi = \nabla \Phi + [A, \Phi]
    dphi0 = g0 + comm0
    dphi1 = g1 + comm1
    dphi2 = g2 + comm2

    norm_dphi_sq = dphi0 * dphi0 + dphi1 * dphi1 + dphi2 * dphi2

    # 5. BPS Monopole Energy density: E = inv_lambda_sq * ||D \Phi||^2
    energy = inv_lambda_sq * norm_dphi_sq
    tl.store(Energy_ptr + pid, energy)

    # 6. Topological magnetic charge density: m(x) = (1 / 4pi) * (\Phi / ||\Phi||) . D \Phi
    phi_norm = tl.sqrt(tl.maximum(p0 * p0 + p1 * p1 + p2 * p2, 1e-8))
    unit_p0 = p0 / phi_norm
    unit_p1 = p1 / phi_norm
    unit_p2 = p2 / phi_norm

    dot_phi_dphi = unit_p0 * dphi0 + unit_p1 * dphi1 + unit_p2 * dphi2
    charge_dens = 0.07957747154594767 * dot_phi_dphi
    tl.store(Charge_ptr + pid, charge_dens)


def triton_poincare_yang_mills_higgs_monopole(
    x: torch.Tensor,
    phi: torch.Tensor,
    a: torch.Tensor,
    grad_phi: torch.Tensor,
    c: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Yang-Mills-Higgs Monopole Kernel.
    Args:
        x: [B, D] manifold coordinates in Poincaré ball
        phi: [B, 3] adjoint Higgs field in su(2)
        a: [B, 3] gauge connection A
        grad_phi: [B, 3] spatial gradient \nabla \Phi
        c: hyperbolic curvature
    Returns:
        (bps_energy, magnetic_charge)
    """
    assert x.is_cuda and phi.is_cuda and a.is_cuda and grad_phi.is_cuda
    B, D = x.shape
    BLOCK_SIZE = triton.next_power_of_2(D)

    energy = torch.empty((B,), device=x.device, dtype=torch.float32)
    charge = torch.empty((B,), device=x.device, dtype=torch.float32)

    grid = (B,)
    _poincare_monopole_kernel[grid](
        x,
        phi,
        a,
        grad_phi,
        energy,
        charge,
        B=B,
        D=D,
        c=c,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return energy, charge


def reference_poincare_monopole(
    x: torch.Tensor,
    phi: torch.Tensor,
    a: torch.Tensor,
    grad_phi: torch.Tensor,
    c: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of BPS Monopole."""
    x_sq = torch.sum(x * x, dim=-1)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = torch.clamp(x_sq, max=max_sq)
    one_minus_cx2 = torch.clamp(1.0 - c * clamped_x_sq, min=1e-6)
    inv_lambda_sq = ((one_minus_cx2 * 0.5) ** 2)

    comm = torch.cross(a, phi, dim=-1)
    dphi = grad_phi + comm
    norm_dphi_sq = torch.sum(dphi * dphi, dim=-1)

    energy = inv_lambda_sq * norm_dphi_sq

    phi_norm = torch.norm(phi, dim=-1, keepdim=True).clamp(min=1e-8)
    unit_phi = phi / phi_norm
    dot_phi_dphi = torch.sum(unit_phi * dphi, dim=-1)
    charge = (1.0 / (4.0 * math.pi)) * dot_phi_dphi

    return energy, charge


def benchmark_monopole():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping.")
        return

    prop = torch.cuda.get_device_properties(0)
    print(f"[*] Physical Device: {prop.name} (Compute Capability {prop.major}.{prop.minor})")

    B = 8192
    D = 128
    c = 1.0

    x = torch.randn(B, D, device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * 0.65
    phi = torch.randn(B, 3, device=device, dtype=torch.float32)
    a = torch.randn(B, 3, device=device, dtype=torch.float32)
    grad_phi = torch.randn(B, 3, device=device, dtype=torch.float32)

    # 1. Numerical verification
    e_tri, q_tri = triton_poincare_yang_mills_higgs_monopole(x, phi, a, grad_phi, c=c)
    e_ref, q_ref = reference_poincare_monopole(x, phi, a, grad_phi, c=c)

    max_err_e = torch.max(torch.abs(e_tri - e_ref)).item()
    max_err_q = torch.max(torch.abs(q_tri - q_ref)).item()

    print(f"[✓] Numerical Verification:")
    print(f"    Max BPS Energy Error:     {max_err_e:.2e}")
    print(f"    Max Magnetic Charge Error: {max_err_q:.2e}")
    assert max_err_e < 1e-4, f"Energy error too high: {max_err_e}"
    assert max_err_q < 1e-4, f"Charge error too high: {max_err_q}"

    # 2. Timing benchmark
    for _ in range(20):
        _ = triton_poincare_yang_mills_higgs_monopole(x, phi, a, grad_phi, c=c)
        _ = reference_poincare_monopole(x, phi, a, grad_phi, c=c)
    torch.cuda.synchronize()

    iters = 200
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_yang_mills_higgs_monopole(x, phi, a, grad_phi, c=c)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_monopole(x, phi, a, grad_phi, c=c)
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
    benchmark_monopole()
