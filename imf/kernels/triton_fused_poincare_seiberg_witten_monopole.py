"""
IMF High-Performance Fused Poincare Seiberg-Witten Monopole Kernel
==================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 8.9 / Ada Lovelace)
Mathematical Foundation:
  Seiberg-Witten gauge theory and monopole equations on the Poincaré ball (D^d_c, g_c).
  In 4D spin^c geometry on hyperbolic symmetric spaces, a U(1) gauge connection A
  coupled to a positive spinor field \psi = (\psi_1, \psi_2) \in \mathbb{C}^2 satisfies:
      1. Dirac equation: \mathcal{D}_A \psi = 0.
      2. Curvature equation: F_A^+ = \sigma(\psi, \psi),
         where F_A^+ is the self-dual 2-form curvature and \sigma(\psi, \psi) is the
         quadratic spinor map to imaginary self-dual 2-forms:
         \sigma(\psi, \psi) = \psi \psi^* - (1/2) |\psi|^2 I.
  1. Conformal metric factor:
     lambda_x = 2 / (1 - c ||x||^2),  inv_lambda_sq = ((1 - c ||x||^2) / 2)^2.
  2. Positive spinor components:
     psi_1 = (r1, i1), psi_2 = (r2, i2).
     Spinor norm: |\psi|^2 = r1^2 + i1^2 + r2^2 + i2^2.
  3. Quadratic spinor map (self-dual curvature source):
     mu_1 = 2 * (r1 * r2 + i1 * i2)
     mu_2 = 2 * (i1 * r2 - r1 * i2)
     mu_3 = (r1^2 + i1^2) - (r2^2 + i2^2)
     Total quadratic curvature norm: ||\sigma(\psi)||^2 = mu_1^2 + mu_2^2 + mu_3^2 = |\psi|^4.
  4. Curvature deviation from self-dual background F^+:
     diff_F_sq = (F_1^+ - mu_1)^2 + (F_2^+ - mu_2)^2 + (F_3^+ - mu_3)^2.
  5. Seiberg-Witten Hamiltonian energy density:
     E_{SW} = inv_lambda_sq * ( ||\nabla_A \psi||^2 + diff_F_sq + (1/4) |\psi|^4 ).
  6. Topological Monopole Winding Invariant:
     sw_charge = (1 / 8pi^2) * (F_1^+ mu_1 + F_2^+ mu_2 + F_3^+ mu_3).
  This fused Triton kernel evaluates the metric inverse scaling, quadratic spinor map,
  Seiberg-Witten energy density, and topological invariant in GPU registers in a single pass.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_seiberg_witten_kernel(
    X_ptr,          # [B, D] coordinates on Poincaré ball
    Spinor_ptr,     # [B, 4] spinor components (r1, i1, r2, i2)
    CurvF_ptr,      # [B, 3] self-dual curvature F^+ = (F1, F2, F3)
    GradPsi_ptr,    # [B, 4] covariant spinor gradient norm
    Energy_ptr,     # [B] Seiberg-Witten energy density
    Charge_ptr,     # [B] topological monopole invariant
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

    # 2. Load spinor components (r1, i1, r2, i2)
    r1 = tl.load(Spinor_ptr + pid * 4 + 0)
    i1 = tl.load(Spinor_ptr + pid * 4 + 1)
    r2 = tl.load(Spinor_ptr + pid * 4 + 2)
    i2 = tl.load(Spinor_ptr + pid * 4 + 3)

    # Load background curvature F^+ = (f1, f2, f3)
    f1 = tl.load(CurvF_ptr + pid * 3 + 0)
    f2 = tl.load(CurvF_ptr + pid * 3 + 1)
    f3 = tl.load(CurvF_ptr + pid * 3 + 2)

    # Load spinor gradient components
    gr1 = tl.load(GradPsi_ptr + pid * 4 + 0)
    gi1 = tl.load(GradPsi_ptr + pid * 4 + 1)
    gr2 = tl.load(GradPsi_ptr + pid * 4 + 2)
    gi2 = tl.load(GradPsi_ptr + pid * 4 + 3)

    norm_grad_sq = gr1 * gr1 + gi1 * gi1 + gr2 * gr2 + gi2 * gi2

    # 3. Quadratic spinor map sigma(psi)
    mu_1 = 2.0 * (r1 * r2 + i1 * i2)
    mu_2 = 2.0 * (i1 * r2 - r1 * i2)
    mu_3 = (r1 * r1 + i1 * i1) - (r2 * r2 + i2 * i2)

    psi_sq = (r1 * r1 + i1 * i1 + r2 * r2 + i2 * i2)
    psi_quartic = psi_sq * psi_sq

    # 4. Curvature deviation
    diff1 = f1 - mu_1
    diff2 = f2 - mu_2
    diff3 = f3 - mu_3
    diff_f_sq = diff1 * diff1 + diff2 * diff2 + diff3 * diff3

    # 5. Seiberg-Witten energy density
    energy = inv_lambda_sq * (norm_grad_sq + diff_f_sq + 0.25 * psi_quartic)
    tl.store(Energy_ptr + pid, energy)

    # 6. Topological Monopole Winding Invariant
    # 1 / 8pi^2 ~ 0.012665147955292222
    dot_f_mu = f1 * mu_1 + f2 * mu_2 + f3 * mu_3
    charge = 0.012665147955292222 * dot_f_mu
    tl.store(Charge_ptr + pid, charge)


def triton_poincare_seiberg_witten(
    x: torch.Tensor,
    spinor: torch.Tensor,
    curv_f: torch.Tensor,
    grad_psi: torch.Tensor,
    c: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Seiberg-Witten Monopole Kernel.
    Args:
        x: [B, D] manifold coordinates in Poincaré ball
        spinor: [B, 4] spinor components (r1, i1, r2, i2)
        curv_f: [B, 3] background self-dual curvature F^+
        grad_psi: [B, 4] spinor gradient components
        c: hyperbolic curvature
    Returns:
        (sw_energy, monopole_charge)
    """
    assert x.is_cuda and spinor.is_cuda and curv_f.is_cuda and grad_psi.is_cuda
    B, D = x.shape
    BLOCK_SIZE = triton.next_power_of_2(D)

    energy = torch.empty((B,), device=x.device, dtype=torch.float32)
    charge = torch.empty((B,), device=x.device, dtype=torch.float32)

    grid = (B,)
    _poincare_seiberg_witten_kernel[grid](
        x,
        spinor,
        curv_f,
        grad_psi,
        energy,
        charge,
        B=B,
        D=D,
        c=c,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return energy, charge


def reference_poincare_seiberg_witten(
    x: torch.Tensor,
    spinor: torch.Tensor,
    curv_f: torch.Tensor,
    grad_psi: torch.Tensor,
    c: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of Seiberg-Witten Equations."""
    x_sq = torch.sum(x * x, dim=-1)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = torch.clamp(x_sq, max=max_sq)
    one_minus_cx2 = torch.clamp(1.0 - c * clamped_x_sq, min=1e-6)
    inv_lambda_sq = ((one_minus_cx2 * 0.5) ** 2)

    r1, i1, r2, i2 = spinor[:, 0], spinor[:, 1], spinor[:, 2], spinor[:, 3]
    f1, f2, f3 = curv_f[:, 0], curv_f[:, 1], curv_f[:, 2]

    norm_grad_sq = torch.sum(grad_psi * grad_psi, dim=-1)

    mu_1 = 2.0 * (r1 * r2 + i1 * i2)
    mu_2 = 2.0 * (i1 * r2 - r1 * i2)
    mu_3 = (r1 * r1 + i1 * i1) - (r2 * r2 + i2 * i2)

    psi_sq = r1 * r1 + i1 * i1 + r2 * r2 + i2 * i2
    psi_quartic = psi_sq * psi_sq

    diff1 = f1 - mu_1
    diff2 = f2 - mu_2
    diff3 = f3 - mu_3
    diff_f_sq = diff1 * diff1 + diff2 * diff2 + diff3 * diff3

    energy = inv_lambda_sq * (norm_grad_sq + diff_f_sq + 0.25 * psi_quartic)
    dot_f_mu = f1 * mu_1 + f2 * mu_2 + f3 * mu_3
    charge = (1.0 / (8.0 * (math.pi ** 2))) * dot_f_mu

    return energy, charge


def benchmark_seiberg_witten():
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
    spinor = torch.randn(B, 4, device=device, dtype=torch.float32) / 2.0
    curv_f = torch.randn(B, 3, device=device, dtype=torch.float32)
    grad_psi = torch.randn(B, 4, device=device, dtype=torch.float32)

    # 1. Numerical verification
    e_tri, q_tri = triton_poincare_seiberg_witten(x, spinor, curv_f, grad_psi, c=c)
    e_ref, q_ref = reference_poincare_seiberg_witten(x, spinor, curv_f, grad_psi, c=c)

    max_err_e = torch.max(torch.abs(e_tri - e_ref)).item()
    max_err_q = torch.max(torch.abs(q_tri - q_ref)).item()

    print(f"[✓] Numerical Verification:")
    print(f"    Max Seiberg-Witten Energy Error: {max_err_e:.2e}")
    print(f"    Max Monopole Invariant Error:    {max_err_q:.2e}")
    assert max_err_e < 1e-4, f"Energy error too high: {max_err_e}"
    assert max_err_q < 1e-4, f"Charge error too high: {max_err_q}"

    # 2. Timing benchmark
    for _ in range(20):
        _ = triton_poincare_seiberg_witten(x, spinor, curv_f, grad_psi, c=c)
        _ = reference_poincare_seiberg_witten(x, spinor, curv_f, grad_psi, c=c)
    torch.cuda.synchronize()

    iters = 200
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_seiberg_witten(x, spinor, curv_f, grad_psi, c=c)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_seiberg_witten(x, spinor, curv_f, grad_psi, c=c)
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
    benchmark_seiberg_witten()
