"""
Triton Fused Discrete Calogero-Bogoyavlensky-Schiff (CBS) Soliton Flow Kernel on Poincaré Ball.
Cycle 285: (2+1)D breaking soliton dynamics on the Poincaré hyperbolic unit ball B^d.

The Calogero-Bogoyavlensky-Schiff (CBS) equation:
  u_{xt} + 4 u_x u_{xy} + 2 u_{xx} u_y + u_{xxxy} = 0
or equivalently in potential form:
  v_t + 4 v_x v_y + v_{xxy} = 0  (where u = v_x)
models breaking solitons and nonlinear Riemann wave steepening with transverse dispersion.
On the Poincaré ball B^d with conformal metric ds^2 = 4 dx^2 / (1 - ||u||^2)^2,
we discretize the (2+1)D breaking soliton envelope and conformal Riemannian gradient flow.
"""

import math
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_discrete_cbs_kernel(
    u_ptr,           # Input coordinates [N, D]
    u_out_ptr,       # Output updated coordinates [N, D]
    metric_ptr,      # Output conformal metric factors [N]
    cbs_pot_ptr,     # Output CBS breaking soliton potential [N]
    N: tl.constexpr,
    D: tl.constexpr,
    dt: tl.constexpr,
    k: tl.constexpr,
    l: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N

    # 1. Compute Euclidean norm squared ||u||^2 = sum_d u_{i, d}^2
    norm_sq = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    for d in range(D):
        u_val = tl.load(u_ptr + offs * D + d, mask=mask, other=0.0)
        norm_sq += u_val * u_val

    # Clamp norm_sq to avoid boundary singularities (< 0.99)
    norm_sq_clamped = tl.minimum(norm_sq, 0.985)
    one_minus_r2 = 1.0 - norm_sq_clamped
    one_minus_r2_safe = tl.maximum(one_minus_r2, 1e-5)

    # Conformal metric factor: lambda(u) = 2 / (1 - ||u||^2)
    metric_factor = 2.0 / one_minus_r2_safe
    tl.store(metric_ptr + offs, metric_factor, mask=mask)

    # 2. Calogero-Bogoyavlensky-Schiff Breaking Soliton Profile
    # Along transverse spatial directions x = u[0], y = u[1]:
    # phase theta = k * x + l * y
    # u_CBS(x, y) = k^2 * sech^2(k * x + l * y)
    u0 = tl.load(u_ptr + offs * D + 0, mask=mask, other=0.0)
    u1 = tl.load(u_ptr + offs * D + 1, mask=mask, other=0.0)

    theta = k * u0 + l * u1
    c_theta = tl.maximum(tl.minimum(theta, 12.0), -12.0)

    exp_p = tl.exp(c_theta)
    exp_m = tl.exp(-c_theta)
    cosh_val = 0.5 * (exp_p + exp_m)
    sech_val = 1.0 / cosh_val
    tanh_val = (exp_p - exp_m) / (exp_p + exp_m)

    cbs_pot = (k * k) * (sech_val * sech_val)
    tl.store(cbs_pot_ptr + offs, cbs_pot, mask=mask)

    # 3. Conformal Hyperbolic Gradient Flow
    decay_factor = (one_minus_r2_safe * one_minus_r2_safe) * 0.25

    # Update along primary transverse modes d=0 and d=1 and radial orthogonal modes
    for d in range(D):
        u_val = tl.load(u_ptr + offs * D + d, mask=mask, other=0.0)
        if d == 0:
            # - d(cbs_pot)/dx = 2 * k^3 * sech^2(theta) * tanh(theta)
            force = 2.0 * (k * k * k) * (sech_val * sech_val) * tanh_val
        elif d == 1:
            # - d(cbs_pot)/dy = 2 * k^2 * l * sech^2(theta) * tanh(theta)
            force = 2.0 * (k * k * l) * (sech_val * sech_val) * tanh_val
        else:
            force = -0.5 * u_val * cbs_pot

        u_new = u_val + dt * decay_factor * force
        tl.store(u_out_ptr + offs * D + d, u_new, mask=mask)


def triton_poincare_discrete_cbs(
    u: torch.Tensor, dt: float = 0.01, k: float = 1.3, l: float = 0.9
):
    """
    Executes the Fused Poincaré Discrete CBS Breaking Soliton flow kernel.
    u: [N, D] tensor on CUDA (D >= 2).
    """
    assert u.is_cuda and u.is_contiguous()
    N, D = u.shape
    assert D >= 2, "CBS requires at least D=2 dimensions."

    u_out = torch.empty_like(u)
    metric = torch.empty(N, dtype=torch.float32, device=u.device)
    pot = torch.empty(N, dtype=torch.float32, device=u.device)

    BLOCK_SIZE = 1024
    grid = (triton.cdiv(N, BLOCK_SIZE),)

    _poincare_discrete_cbs_kernel[grid](
        u, u_out, metric, pot,
        N=N, D=D, dt=dt, k=k, l=l,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return u_out, metric, pot


def pytorch_poincare_discrete_cbs_ref(
    u: torch.Tensor, dt: float = 0.01, k: float = 1.3, l: float = 0.9
):
    """
    PyTorch pure reference for verification.
    """
    norm_sq = torch.sum(u ** 2, dim=-1)
    norm_sq_clamped = torch.clamp(norm_sq, max=0.985)
    one_minus_r2 = 1.0 - norm_sq_clamped
    one_minus_r2_safe = torch.clamp(one_minus_r2, min=1e-5)
    metric = 2.0 / one_minus_r2_safe

    u0 = u[:, 0]
    u1 = u[:, 1]
    theta = torch.clamp(k * u0 + l * u1, -12.0, 12.0)

    cosh_val = torch.cosh(theta)
    sech_val = 1.0 / cosh_val
    tanh_val = torch.tanh(theta)

    cbs_pot = (k ** 2) * (sech_val ** 2)
    decay_factor = (one_minus_r2_safe ** 2) * 0.25

    u_out = u.clone()
    f0 = 2.0 * (k ** 3) * (sech_val ** 2) * tanh_val
    f1 = 2.0 * (k ** 2) * l * (sech_val ** 2) * tanh_val

    u_out[:, 0] = u[:, 0] + dt * decay_factor * f0
    u_out[:, 1] = u[:, 1] + dt * decay_factor * f1
    if u.shape[1] > 2:
        for d in range(2, u.shape[1]):
            fd = -0.5 * u[:, d] * cbs_pot
            u_out[:, d] = u[:, d] + dt * decay_factor * fd

    return u_out, metric, cbs_pot


if __name__ == "__main__":
    if not torch.cuda.is_available():
        print("CUDA not available, skipping.")
        exit(0)

    torch.manual_seed(42)
    N = 131072 # 128k nodes
    D = 16
    u = (torch.rand(N, D, device="cuda") - 0.5) * 0.8

    # Correctness check
    u_tri, m_tri, p_tri = triton_poincare_discrete_cbs(u)
    u_ref, m_ref, p_ref = pytorch_poincare_discrete_cbs_ref(u)

    max_u_err = (u_tri - u_ref).abs().max().item()
    max_p_err = (p_tri - p_ref).abs().max().item()

    print(f"Correctness: Max u error: {max_u_err:.2e}, Max pot error: {max_p_err:.2e}")
    assert max_u_err < 1e-4, f"u error too high: {max_u_err}"
    assert max_p_err < 1e-4, f"pot error too high: {max_p_err}"

    # Benchmark
    warmup = 20
    iters = 100
    for _ in range(warmup):
        _ = triton_poincare_discrete_cbs(u)
    torch.cuda.synchronize()

    start_event = torch.cuda.Event(enable_timing=True)
    end_event = torch.cuda.Event(enable_timing=True)

    start_event.record()
    for _ in range(iters):
        _ = triton_poincare_discrete_cbs(u)
    end_event.record()
    torch.cuda.synchronize()

    elapsed_ms = start_event.elapsed_time(end_event) / iters
    throughput = (N / (elapsed_ms / 1000.0)) / 1e6
    print(f"Triton Discrete CBS Kernel Latency: {elapsed_ms * 1000:.2f} us | Throughput: {throughput:.2f} M nodes/s")
