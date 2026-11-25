"""
Triton Fused Kernel: Poincaré Sasa-Satsuma Higher-Order Nonlinear Schrödinger Flow (SM 12.0)
Cycle 226 Capstone: Higher-Order Dispersion, Self-Steepening, and Raman Self-Frequency Shift
on Hyperbolic Poincaré Geodesic Manifold.

Physical Model:
Sasa-Satsuma equation governing ultra-short optical pulse propagation in fiber:
    i \partial_t u + \frac{1}{2} \partial_x^2 u + |u|^2 u + i \epsilon [ \partial_x^3 u + 6 |u|^2 \partial_x u + 3 u \partial_x (|u|^2) ] = 0

Projected onto Poincaré disk manifold $\mathbb{D}^2$ with hyperbolic metric
    g_{ij} = \frac{4}{(1 - \|u\|^2)^2} \delta_{ij}
"""

import torch
import triton
import triton.language as tl
import time

@triton.jit
def _poincare_sasa_satsuma_kernel(
    u_real_ptr, u_imag_ptr,
    out_real_ptr, out_imag_ptr,
    dt, epsilon, n_elements,
    BLOCK_SIZE: tl.constexpr
):
    pid = tl.program_id(axis=0)
    offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offsets < n_elements

    # Load real and imag parts
    ur = tl.load(u_real_ptr + offsets, mask=mask, other=0.0)
    ui = tl.load(u_imag_ptr + offsets, mask=mask, other=0.0)

    # Spatial finite differences with periodic wrapping
    idx_prev = (offsets - 1 + n_elements) % n_elements
    idx_next = (offsets + 1) % n_elements
    idx_prev2 = (offsets - 2 + n_elements) % n_elements
    idx_next2 = (offsets + 2) % n_elements

    ur_prev = tl.load(u_real_ptr + idx_prev, mask=mask, other=0.0)
    ui_prev = tl.load(u_imag_ptr + idx_prev, mask=mask, other=0.0)
    ur_next = tl.load(u_real_ptr + idx_next, mask=mask, other=0.0)
    ui_next = tl.load(u_imag_ptr + idx_next, mask=mask, other=0.0)

    ur_prev2 = tl.load(u_real_ptr + idx_prev2, mask=mask, other=0.0)
    ui_prev2 = tl.load(u_imag_ptr + idx_prev2, mask=mask, other=0.0)
    ur_next2 = tl.load(u_real_ptr + idx_next2, mask=mask, other=0.0)
    ui_next2 = tl.load(u_imag_ptr + idx_next2, mask=mask, other=0.0)

    # 1st, 2nd, 3rd derivatives (centered differences, dx=1.0)
    # du_dx
    dur_dx = 0.5 * (ur_next - ur_prev)
    dui_dx = 0.5 * (ui_next - ui_prev)

    # d2u_dx2
    d2ur_dx2 = ur_next - 2.0 * ur + ur_prev
    d2ui_dx2 = ui_next - 2.0 * ui + ui_prev

    # d3u_dx3 = 0.5 * (u_{x+2} - 2 u_{x+1} + 2 u_{x-1} - u_{x-2})
    d3ur_dx3 = 0.5 * (ur_next2 - 2.0 * ur_next + 2.0 * ur_prev - ur_prev2)
    d3ui_dx3 = 0.5 * (ui_next2 - 2.0 * ui_next + 2.0 * ui_prev - ui_prev2)

    # Intensity |u|^2
    intensity = ur * ur + ui * ui
    int_prev = ur_prev * ur_prev + ui_prev * ui_prev
    int_next = ur_next * ur_next + ui_next * ui_next
    d_intensity_dx = 0.5 * (int_next - int_prev)

    # Standard NLS terms:
    # i \partial_t u = -0.5 \partial_x^2 u - |u|^2 u
    # \partial_t u = i * [ 0.5 \partial_x^2 u + |u|^2 u ]
    # i (d2ur + i d2ui) = -d2ui + i d2ur
    # i |u|^2 (ur + i ui) = -|u|^2 ui + i |u|^2 ur
    nls_rhs_real = -0.5 * d2ui_dx2 - intensity * ui
    nls_rhs_imag = 0.5 * d2ur_dx2 + intensity * ur

    # Sasa-Satsuma perturbation:
    # Pert = i \epsilon [ \partial_x^3 u + 6 |u|^2 \partial_x u + 3 u \partial_x(|u|^2) ]
    # \partial_t u += -Pert
    # Term 1: \partial_x^3 u
    # Term 2: 6 |u|^2 \partial_x u = 6 |u|^2 (dur_dx + i dui_dx)
    # Term 3: 3 u \partial_x(|u|^2) = 3 (ur + i ui) d_intensity_dx
    t1_r = d3ur_dx3
    t1_i = d3ui_dx3

    t2_r = 6.0 * intensity * dur_dx
    t2_i = 6.0 * intensity * dui_dx

    t3_r = 3.0 * ur * d_intensity_dx
    t3_i = 3.0 * ui * d_intensity_dx

    bracket_r = t1_r + t2_r + t3_r
    bracket_i = t1_i + t2_i + t3_i

    # Pert = i \epsilon (bracket_r + i bracket_i) = \epsilon (-bracket_i + i bracket_r)
    # Subtracted from rhs:
    ss_rhs_real = nls_rhs_real - epsilon * (-bracket_i)
    ss_rhs_imag = nls_rhs_imag - epsilon * bracket_r

    # Hyperbolic Poincaré conformal scaling:
    # lambda_u = 4 / (1 - ||u||^2)^2 (clipped to maintain stable disk metric)
    u_norm_sq = ur * ur + ui * ui
    safe_denom = tl.maximum(1.0 - u_norm_sq, 0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)

    # Scale updates by inverse hyperbolic metric: dt / poincare_conformal
    effective_dt = dt / poincare_conformal

    out_ur = ur + effective_dt * ss_rhs_real
    out_ui = ui + effective_dt * ss_rhs_imag

    # Project strictly into Poincaré open unit disk
    norm_out_sq = out_ur * out_ur + out_ui * out_ui
    scale = tl.where(norm_out_sq >= 0.98, tl.sqrt(0.98 / norm_out_sq), 1.0)
    out_ur = out_ur * scale
    out_ui = out_ui * scale

    tl.store(out_real_ptr + offsets, out_ur, mask=mask)
    tl.store(out_imag_ptr + offsets, out_ui, mask=mask)

def poincare_sasa_satsuma_triton(u_real: torch.Tensor, u_imag: torch.Tensor, dt: float = 0.001, epsilon: float = 0.05):
    assert u_real.is_cuda and u_imag.is_cuda
    n = u_real.numel()
    out_real = torch.empty_like(u_real)
    out_imag = torch.empty_like(u_imag)
    BLOCK_SIZE = 1024
    grid = (triton.cdiv(n, BLOCK_SIZE),)
    _poincare_sasa_satsuma_kernel[grid](
        u_real, u_imag, out_real, out_imag,
        dt, epsilon, n,
        BLOCK_SIZE=BLOCK_SIZE
    )
    return out_real, out_imag

def poincare_sasa_satsuma_pytorch(ur: torch.Tensor, ui: torch.Tensor, dt: float = 0.001, epsilon: float = 0.05):
    # Centered periodic finite difference
    ur_prev = torch.roll(ur, shifts=1, dims=0)
    ur_next = torch.roll(ur, shifts=-1, dims=0)
    ui_prev = torch.roll(ui, shifts=1, dims=0)
    ui_next = torch.roll(ui, shifts=-1, dims=0)

    ur_prev2 = torch.roll(ur, shifts=2, dims=0)
    ur_next2 = torch.roll(ur, shifts=-2, dims=0)
    ui_prev2 = torch.roll(ui, shifts=2, dims=0)
    ui_next2 = torch.roll(ui, shifts=-2, dims=0)

    dur_dx = 0.5 * (ur_next - ur_prev)
    dui_dx = 0.5 * (ui_next - ui_prev)

    d2ur_dx2 = ur_next - 2.0 * ur + ur_prev
    d2ui_dx2 = ui_next - 2.0 * ui + ui_prev

    d3ur_dx3 = 0.5 * (ur_next2 - 2.0 * ur_next + 2.0 * ur_prev - ur_prev2)
    d3ui_dx3 = 0.5 * (ui_next2 - 2.0 * ui_next + 2.0 * ui_prev - ui_prev2)

    intensity = ur * ur + ui * ui
    int_prev = ur_prev * ur_prev + ui_prev * ui_prev
    int_next = ur_next * ur_next + ui_next * ui_next
    d_intensity_dx = 0.5 * (int_next - int_prev)

    nls_rhs_real = -0.5 * d2ui_dx2 - intensity * ui
    nls_rhs_imag = 0.5 * d2ur_dx2 + intensity * ur

    t1_r = d3ur_dx3
    t1_i = d3ui_dx3
    t2_r = 6.0 * intensity * dur_dx
    t2_i = 6.0 * intensity * dui_dx
    t3_r = 3.0 * ur * d_intensity_dx
    t3_i = 3.0 * ui * d_intensity_dx

    bracket_r = t1_r + t2_r + t3_r
    bracket_i = t1_i + t2_i + t3_i

    ss_rhs_real = nls_rhs_real + epsilon * bracket_i
    ss_rhs_imag = nls_rhs_imag - epsilon * bracket_r

    safe_denom = torch.clamp(1.0 - intensity, min=0.05)
    poincare_conformal = 4.0 / (safe_denom * safe_denom)
    effective_dt = dt / poincare_conformal

    out_ur = ur + effective_dt * ss_rhs_real
    out_ui = ui + effective_dt * ss_rhs_imag

    norm_sq = out_ur * out_ur + out_ui * out_ui
    mask = norm_sq >= 0.98
    scale = torch.ones_like(norm_sq)
    scale[mask] = torch.sqrt(0.98 / norm_sq[mask])

    return out_ur * scale, out_ui * scale

def benchmark():
    device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    print("=" * 70)
    print("  IMF TRITON POINCARÉ SASA-SATSUMA FLOW (RTX 5060 Ti SM 12.0)")
    print("=" * 70)

    n = 131072  # 128k spatial grid points
    ur = torch.randn(n, device=device, dtype=torch.float32) * 0.4
    ui = torch.randn(n, device=device, dtype=torch.float32) * 0.4

    # Warmup
    for _ in range(20):
        out_r_tri, out_i_tri = poincare_sasa_satsuma_triton(ur, ui)
        out_r_pt, out_i_pt = poincare_sasa_satsuma_pytorch(ur, ui)
    torch.cuda.synchronize()

    # Numerical verification
    max_err_r = (out_r_tri - out_r_pt).abs().max().item()
    max_err_i = (out_i_tri - out_i_pt).abs().max().item()
    print(f"Max Absolute Error Real: {max_err_r:.2e}")
    print(f"Max Absolute Error Imag: {max_err_i:.2e}")
    assert max_err_r < 1e-4 and max_err_i < 1e-4, "Numerical tolerance check failed!"

    iters = 100
    t0 = time.perf_counter()
    for _ in range(iters):
        out_r_pt, out_i_pt = poincare_sasa_satsuma_pytorch(ur, ui)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / iters * 1000.0

    t0 = time.perf_counter()
    for _ in range(iters):
        out_r_tri, out_i_tri = poincare_sasa_satsuma_triton(ur, ui)
    torch.cuda.synchronize()
    t_tri = (time.perf_counter() - t0) / iters * 1000.0

    speedup = t_pt / t_tri
    throughput = (n / (t_tri / 1000.0)) / 1e6

    print(f"PyTorch Time:  {t_pt * 1000.0:.2f} µs")
    print(f"Triton Time:   {t_tri * 1000.0:.2f} µs")
    print(f"Speedup:       {speedup:.2f}x")
    print(f"Throughput:    {throughput:.2f} M nodes/s")
    print("=" * 70)

if __name__ == "__main__":
    benchmark()
