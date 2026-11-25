"""
Triton Fused Discrete Boiti-Leon-Pempinelli (BLP) Soliton Flow Kernel on Poincaré Ball.
Cycle 286: (2+1)D sinh-Gordon-type continuous wave-interaction lattice dynamics
on the Poincaré hyperbolic unit ball B^d.

The Boiti-Leon-Pempinelli (BLP) system:
  u_t = ( u_{xx} - 2 u v )_x
  v_y = ( u^2 )_x
describes (2+1)-dimensional nonlinear wave interactions related to the sinh-Gordon hierarchy.
On the Poincaré ball B^d with conformal metric ds^2 = 4 dx^2 / (1 - ||u||^2)^2,
we discretize the (2+1)D interaction potential and conformal Riemannian gradient flow.
"""

import math
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_discrete_blp_kernel(
    u_ptr,           # Input coordinates [N, D]
    u_out_ptr,       # Output updated coordinates [N, D]
    metric_ptr,      # Output conformal metric factors [N]
    blp_pot_ptr,     # Output BLP wave interaction potential [N]
    N: tl.constexpr,
    D: tl.constexpr,
    dt: tl.constexpr,
    m1: tl.constexpr,
    n1: tl.constexpr,
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

    # 2. Boiti-Leon-Pempinelli Interaction Soliton Potential
    # Along transverse spatial directions x = u[0], y = u[1]:
    # u_{BLP}(x, y) = 2 * m1 * sech(m1 * x) * sech(n1 * y) / (1 + 0.3 * tanh(m1 * x) * tanh(n1 * y))
    u0 = tl.load(u_ptr + offs * D + 0, mask=mask, other=0.0)
    u1 = tl.load(u_ptr + offs * D + 1, mask=mask, other=0.0)

    arg0 = tl.maximum(tl.minimum(m1 * u0, 10.0), -10.0)
    arg1 = tl.maximum(tl.minimum(n1 * u1, 10.0), -10.0)

    exp_p0 = tl.exp(arg0)
    exp_m0 = tl.exp(-arg0)
    cosh0 = 0.5 * (exp_p0 + exp_m0)
    sech0 = 1.0 / cosh0
    tanh0 = (exp_p0 - exp_m0) / (exp_p0 + exp_m0)

    exp_p1 = tl.exp(arg1)
    exp_m1 = tl.exp(-arg1)
    cosh1 = 0.5 * (exp_p1 + exp_m1)
    sech1 = 1.0 / cosh1
    tanh1 = (exp_p1 - exp_m1) / (exp_p1 + exp_m1)

    denom = 1.0 + 0.3 * tanh0 * tanh1
    denom_safe = tl.maximum(denom, 0.1)

    amp = (2.0 * m1 * sech0 * sech1) / denom_safe
    blp_pot = amp * amp
    tl.store(blp_pot_ptr + offs, blp_pot, mask=mask)

    # 3. Conformal Hyperbolic Gradient Flow
    decay_factor = (one_minus_r2_safe * one_minus_r2_safe) * 0.25

    for d in range(D):
        u_val = tl.load(u_ptr + offs * D + d, mask=mask, other=0.0)
        if d == 0:
            force = -2.0 * m1 * tanh0 * blp_pot
        elif d == 1:
            force = -2.0 * n1 * tanh1 * blp_pot
        else:
            force = -0.5 * u_val * blp_pot

        u_new = u_val + dt * decay_factor * force
        tl.store(u_out_ptr + offs * D + d, u_new, mask=mask)


def triton_poincare_discrete_blp(
    u: torch.Tensor, dt: float = 0.01, m1: float = 1.3, n1: float = 1.1
):
    """
    Executes the Fused Poincaré Discrete BLP Soliton flow kernel.
    u: [N, D] tensor on CUDA (D >= 2).
    """
    assert u.is_cuda and u.is_contiguous()
    N, D = u.shape
    assert D >= 2, "BLP requires at least D=2 dimensions."

    u_out = torch.empty_like(u)
    metric = torch.empty(N, dtype=torch.float32, device=u.device)
    pot = torch.empty(N, dtype=torch.float32, device=u.device)

    BLOCK_SIZE = 1024
    grid = (triton.cdiv(N, BLOCK_SIZE),)

    _poincare_discrete_blp_kernel[grid](
        u, u_out, metric, pot,
        N=N, D=D, dt=dt, m1=m1, n1=n1,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return u_out, metric, pot


def pytorch_poincare_discrete_blp_ref(
    u: torch.Tensor, dt: float = 0.01, m1: float = 1.3, n1: float = 1.1
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
    arg0 = torch.clamp(m1 * u0, -10.0, 10.0)
    arg1 = torch.clamp(n1 * u1, -10.0, 10.0)

    cosh0 = torch.cosh(arg0)
    sech0 = 1.0 / cosh0
    tanh0 = torch.tanh(arg0)

    cosh1 = torch.cosh(arg1)
    sech1 = 1.0 / cosh1
    tanh1 = torch.tanh(arg1)

    denom = 1.0 + 0.3 * tanh0 * tanh1
    denom_safe = torch.clamp(denom, min=0.1)

    amp = (2.0 * m1 * sech0 * sech1) / denom_safe
    blp_pot = amp ** 2

    decay_factor = (one_minus_r2_safe ** 2) * 0.25
    u_out = u.clone()

    f0 = -2.0 * m1 * tanh0 * blp_pot
    f1 = -2.0 * n1 * tanh1 * blp_pot

    u_out[:, 0] = u[:, 0] + dt * decay_factor * f0
    u_out[:, 1] = u[:, 1] + dt * decay_factor * f1
    if u.shape[1] > 2:
        for d in range(2, u.shape[1]):
            fd = -0.5 * u[:, d] * blp_pot
            u_out[:, d] = u[:, d] + dt * decay_factor * fd

    return u_out, metric, blp_pot


if __name__ == "__main__":
    if not torch.cuda.is_available():
        print("CUDA not available, skipping.")
        exit(0)

    torch.manual_seed(42)
    N = 131072 # 128k nodes
    D = 16
    u = (torch.rand(N, D, device="cuda") - 0.5) * 0.8

    # Correctness check
    u_tri, m_tri, p_tri = triton_poincare_discrete_blp(u)
    u_ref, m_ref, p_ref = pytorch_poincare_discrete_blp_ref(u)

    max_u_err = (u_tri - u_ref).abs().max().item()
    max_p_err = (p_tri - p_ref).abs().max().item()

    print(f"Correctness: Max u error: {max_u_err:.2e}, Max pot error: {max_p_err:.2e}")
    assert max_u_err < 1e-4, f"u error too high: {max_u_err}"
    assert max_p_err < 1e-4, f"pot error too high: {max_p_err}"

    # Benchmark
    warmup = 20
    iters = 100
    for _ in range(warmup):
        _ = triton_poincare_discrete_blp(u)
    torch.cuda.synchronize()

    start_event = torch.cuda.Event(enable_timing=True)
    end_event = torch.cuda.Event(enable_timing=True)

    start_event.record()
    for _ in range(iters):
        _ = triton_poincare_discrete_blp(u)
    end_event.record()
    torch.cuda.synchronize()

    elapsed_ms = start_event.elapsed_time(end_event) / iters
    throughput = (N / (elapsed_ms / 1000.0)) / 1e6
    print(f"Triton Discrete BLP Kernel Latency: {elapsed_ms * 1000:.2f} us | Throughput: {throughput:.2f} M nodes/s")
