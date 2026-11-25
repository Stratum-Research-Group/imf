"""
IMF High-Performance Fused Poincare Non-Linear Sigma Model Skyrmion Kernel
==========================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 12.0 / Blackwell)
Mathematical Foundation:
  O(3) / Faddeev-Skyrme non-linear sigma model on the Poincaré ball (D^d_c, g_c).
  Given field configuration n(x) in S^2 (unit 3-vector field ||n|| = 1) over manifold points x in D^d_c.
  1. Conformal metric factor:
     lambda_x = 2 / (1 - c ||x||^2),  inv_lambda_sq = ((1 - c ||x||^2) / 2)^2.
  2. Spatial derivatives and tangent projections:
     Given spatial coordinate variations dx, dy across representation channels, the field
     gradients d_1 n and d_2 n are evaluated.
  3. Dirichlet kinetic energy density:
     E_2 = (1/2) * inv_lambda_sq * ( ||d_1 n||^2 + ||d_2 n||^2 ).
  4. Skyrme quartic topological stabilization energy:
     F_{12} = (d_1 n) x (d_2 n) (vector cross product).
     E_4 = (kappa / 4) * (inv_lambda_sq^2) * ||F_{12}||^2.
  5. Topological charge density (Baryon / Skyrmion number density):
     q(x) = (1 / 4pi) * n . ( (d_1 n) x (d_2 n) ).
  6. Total energy and Bogomol'nyi bound verification:
     E_tot = E_2 + E_4 >= 12 pi^2 |q(x)|.
  This fused Triton kernel evaluates the S^2 field normalization, cross-derivatives,
  Dirichlet energy, Skyrme quartic term, and topological charge density completely in GPU registers.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_skyrmion_kernel(
    X_ptr,          # [B, D] coordinates on Poincaré ball
    N_ptr,          # [B, 3] S^2 unit vector field n = (n1, n2, n3)
    Grad1_ptr,      # [B, 3] gradient vector d_1 n
    Grad2_ptr,      # [B, 3] gradient vector d_2 n
    Energy_ptr,     # [B] total Skyrme energy density
    Charge_ptr,     # [B] topological charge density q(x)
    B: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    kappa: tl.constexpr,
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

    # 2. Load S^2 unit field n = (n0, n1, n2)
    n0 = tl.load(N_ptr + pid * 3 + 0)
    n1 = tl.load(N_ptr + pid * 3 + 1)
    n2 = tl.load(N_ptr + pid * 3 + 2)

    # Ensure exact S^2 normalization
    n_norm = tl.sqrt(tl.maximum(n0 * n0 + n1 * n1 + n2 * n2, 1e-8))
    n0 = n0 / n_norm
    n1 = n1 / n_norm
    n2 = n2 / n_norm

    # 3. Load gradients d_1 n and d_2 n
    g1_0 = tl.load(Grad1_ptr + pid * 3 + 0)
    g1_1 = tl.load(Grad1_ptr + pid * 3 + 1)
    g1_2 = tl.load(Grad1_ptr + pid * 3 + 2)

    g2_0 = tl.load(Grad2_ptr + pid * 3 + 0)
    g2_1 = tl.load(Grad2_ptr + pid * 3 + 1)
    g2_2 = tl.load(Grad2_ptr + pid * 3 + 2)

    # Project gradients to tangent space of S^2: grad_perp = grad - (n . grad) * n
    dot_ng1 = n0 * g1_0 + n1 * g1_1 + n2 * g1_2
    g1_0 = g1_0 - dot_ng1 * n0
    g1_1 = g1_1 - dot_ng1 * n1
    g1_2 = g1_2 - dot_ng1 * n2

    dot_ng2 = n0 * g2_0 + n1 * g2_1 + n2 * g2_2
    g2_0 = g2_0 - dot_ng2 * n0
    g2_1 = g2_1 - dot_ng2 * n1
    g2_2 = g2_2 - dot_ng2 * n2

    # 4. Dirichlet kinetic energy E_2
    norm_g1_sq = g1_0 * g1_0 + g1_1 * g1_1 + g1_2 * g1_2
    norm_g2_sq = g2_0 * g2_0 + g2_1 * g2_1 + g2_2 * g2_2
    e2 = 0.5 * inv_lambda_sq * (norm_g1_sq + norm_g2_sq)

    # 5. Skyrme quartic term: cross product F = (d_1 n) x (d_2 n)
    f0 = g1_1 * g2_2 - g1_2 * g2_1
    f1 = g1_2 * g2_0 - g1_0 * g2_2
    f2 = g1_0 * g2_1 - g1_1 * g2_0

    norm_f_sq = f0 * f0 + f1 * f1 + f2 * f2
    e4 = 0.25 * kappa * (inv_lambda_sq * inv_lambda_sq) * norm_f_sq

    total_energy = e2 + e4
    tl.store(Energy_ptr + pid, total_energy)

    # 6. Topological charge density: q = (1 / 4pi) * (n . F)
    # 1 / 4pi ~ 0.07957747154594767
    dot_nf = n0 * f0 + n1 * f1 + n2 * f2
    q_dens = 0.07957747154594767 * dot_nf
    tl.store(Charge_ptr + pid, q_dens)


def triton_poincare_non_linear_sigma_skyrmion(
    x: torch.Tensor,
    n: torch.Tensor,
    grad1: torch.Tensor,
    grad2: torch.Tensor,
    c: float = 1.0,
    kappa: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Non-Linear Sigma Model Skyrmion Kernel.
    Args:
        x: [B, D] manifold coordinates on Poincaré ball
        n: [B, 3] S^2 unit field vector
        grad1: [B, 3] gradient d_1 n
        grad2: [B, 3] gradient d_2 n
        c: hyperbolic curvature
        kappa: Skyrme quartic parameter
    Returns:
        (total_energy, charge_density)
    """
    assert x.is_cuda and n.is_cuda and grad1.is_cuda and grad2.is_cuda
    B, D = x.shape
    BLOCK_SIZE = triton.next_power_of_2(D)

    energy = torch.empty((B,), device=x.device, dtype=torch.float32)
    charge = torch.empty((B,), device=x.device, dtype=torch.float32)

    grid = (B,)
    _poincare_skyrmion_kernel[grid](
        x,
        n,
        grad1,
        grad2,
        energy,
        charge,
        B=B,
        D=D,
        c=c,
        kappa=kappa,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return energy, charge


def reference_poincare_skyrmion(
    x: torch.Tensor,
    n: torch.Tensor,
    grad1: torch.Tensor,
    grad2: torch.Tensor,
    c: float = 1.0,
    kappa: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of Skyrme Non-Linear Sigma Model."""
    x_sq = torch.sum(x * x, dim=-1)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = torch.clamp(x_sq, max=max_sq)
    one_minus_cx2 = torch.clamp(1.0 - c * clamped_x_sq, min=1e-6)
    inv_lambda_sq = ((one_minus_cx2 * 0.5) ** 2)

    n_norm = torch.norm(n, dim=-1, keepdim=True).clamp(min=1e-8)
    n_unit = n / n_norm

    dot_ng1 = torch.sum(n_unit * grad1, dim=-1, keepdim=True)
    g1 = grad1 - dot_ng1 * n_unit

    dot_ng2 = torch.sum(n_unit * grad2, dim=-1, keepdim=True)
    g2 = grad2 - dot_ng2 * n_unit

    norm_g1_sq = torch.sum(g1 * g1, dim=-1)
    norm_g2_sq = torch.sum(g2 * g2, dim=-1)
    e2 = 0.5 * inv_lambda_sq * (norm_g1_sq + norm_g2_sq)

    f = torch.cross(g1, g2, dim=-1)
    norm_f_sq = torch.sum(f * f, dim=-1)
    e4 = 0.25 * kappa * (inv_lambda_sq ** 2) * norm_f_sq

    total_energy = e2 + e4
    dot_nf = torch.sum(n_unit * f, dim=-1)
    q_dens = (1.0 / (4.0 * math.pi)) * dot_nf

    return total_energy, q_dens


def benchmark_skyrmion():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping.")
        return

    prop = torch.cuda.get_device_properties(0)
    print(f"[*] Physical Device: {prop.name} (Compute Capability {prop.major}.{prop.minor})")

    B = 8192
    D = 128
    c = 1.0
    kappa = 1.0

    x = torch.randn(B, D, device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * 0.65
    n = torch.randn(B, 3, device=device, dtype=torch.float32)
    grad1 = torch.randn(B, 3, device=device, dtype=torch.float32)
    grad2 = torch.randn(B, 3, device=device, dtype=torch.float32)

    # 1. Numerical verification
    e_tri, q_tri = triton_poincare_non_linear_sigma_skyrmion(x, n, grad1, grad2, c=c, kappa=kappa)
    e_ref, q_ref = reference_poincare_skyrmion(x, n, grad1, grad2, c=c, kappa=kappa)

    max_err_e = torch.max(torch.abs(e_tri - e_ref)).item()
    max_err_q = torch.max(torch.abs(q_tri - q_ref)).item()

    print(f"[✓] Numerical Verification:")
    print(f"    Max Skyrme Energy Error: {max_err_e:.2e}")
    print(f"    Max Charge Density Error: {max_err_q:.2e}")
    assert max_err_e < 1e-4, f"Energy error too high: {max_err_e}"
    assert max_err_q < 1e-4, f"Charge error too high: {max_err_q}"

    # 2. Timing benchmark
    for _ in range(20):
        _ = triton_poincare_non_linear_sigma_skyrmion(x, n, grad1, grad2, c=c, kappa=kappa)
        _ = reference_poincare_skyrmion(x, n, grad1, grad2, c=c, kappa=kappa)
    torch.cuda.synchronize()

    iters = 200
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_non_linear_sigma_skyrmion(x, n, grad1, grad2, c=c, kappa=kappa)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_skyrmion(x, n, grad1, grad2, c=c, kappa=kappa)
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
    benchmark_skyrmion()
