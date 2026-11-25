"""
Triton Fused Discrete Dromion Lattice Flow Kernel on Poincaré Hyperbolic Ball.
Cycle 281: Two-dimensional localized nonlinear dromion lattice dynamics
embedded into the conformal Poincaré ball metric.

The discrete (2+1)D Dromion lattice represents localized coherent boundary-induced
solitary excitations arising from interacting line solitons.
On the Poincaré disk/ball B^d with conformal metric ds^2 = 4 dx^2 / (1 - ||u||^2)^2,
the discrete flow incorporates spatial cross-curvature gradients.
"""

import math
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_discrete_dromion_kernel(
    u_ptr,           # Input coordinates [N, D]
    u_out_ptr,       # Output updated coordinates [N, D]
    metric_ptr,      # Output conformal metric factors [N]
    pot_ptr,         # Output localized dromion potential [N]
    N: tl.constexpr,
    D: tl.constexpr,
    dt: tl.constexpr,
    c1: tl.constexpr,
    c2: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N

    # Compute Euclidean norm squared ||u||^2 = sum_d u_{i, d}^2
    norm_sq = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    for d in range(D):
        u_val = tl.load(u_ptr + offs * D + d, mask=mask, other=0.0)
        norm_sq += u_val * u_val

    # Clamp norm_sq to avoid disk boundary singularities (< 0.99)
    norm_sq_clamped = tl.minimum(norm_sq, 0.985)
    one_minus_r2 = 1.0 - norm_sq_clamped
    one_minus_r2_safe = tl.maximum(one_minus_r2, 1e-5)

    # Conformal metric factor: lambda(u) = 2 / (1 - ||u||^2)
    metric_factor = 2.0 / one_minus_r2_safe
    tl.store(metric_ptr + offs, metric_factor, mask=mask)

    # 2D Dromion localized potential field:
    # U(x, y) = 4 * k1 * k2 * sech^2(k1 * x) * sech^2(k2 * y) / (1 + a * tanh(k1 * x) * tanh(k2 * y))^2
    # In general dimension D >= 2, we take the primary cross components d=0 and d=1
    u0 = tl.load(u_ptr + offs * D + 0, mask=mask, other=0.0)
    u1 = tl.load(u_ptr + offs * D + 1, mask=mask, other=0.0)

    # Exponential profiles for sech and tanh
    # arg0 = c1 * u0, arg1 = c2 * u1
    arg0 = c1 * u0
    arg1 = c2 * u1

    # Safe evaluation of sech(x) = 2 / (e^x + e^-x)
    # Clamp args to avoid overflow
    c_arg0 = tl.maximum(tl.minimum(arg0, 10.0), -10.0)
    c_arg1 = tl.maximum(tl.minimum(arg1, 10.0), -10.0)

    exp_p0 = tl.exp(c_arg0)
    exp_m0 = tl.exp(-c_arg0)
    cosh0 = 0.5 * (exp_p0 + exp_m0)
    sech0 = 1.0 / cosh0
    tanh0 = (exp_p0 - exp_m0) / (exp_p0 + exp_m0)

    exp_p1 = tl.exp(c_arg1)
    exp_m1 = tl.exp(-c_arg1)
    cosh1 = 0.5 * (exp_p1 + exp_m1)
    sech1 = 1.0 / cosh1
    tanh1 = (exp_p1 - exp_m1) / (exp_p1 + exp_m1)

    sech0_sq = sech0 * sech0
    sech1_sq = sech1 * sech1

    # Dromion localized peak:
    # denom = (1.0 + 0.5 * tanh0 * tanh1)
    denom = 1.0 + 0.5 * tanh0 * tanh1
    denom_sq = denom * denom
    dromion_pot = (4.0 * c1 * c2 * sech0_sq * sech1_sq) / denom_sq
    tl.store(pot_ptr + offs, dromion_pot, mask=mask)

    # Nonlinear lattice velocity update:
    # v = - (1 - ||u||^2)^2 * grad(dromion_pot) / 4.0
    # Approximated along the conformal hyperbolic geodesic:
    decay_factor = (one_minus_r2_safe * one_minus_r2_safe) * 0.25

    # Update coordinates along all dimensions
    for d in range(D):
        u_val = tl.load(u_ptr + offs * D + d, mask=mask, other=0.0)
        # Coordinate-dependent non-linear interaction with localized dromion
        if d == 0:
            force = -2.0 * c1 * tanh0 * dromion_pot
        elif d == 1:
            force = -2.0 * c2 * tanh1 * dromion_pot
        else:
            force = -0.5 * u_val * dromion_pot

        u_new = u_val + dt * decay_factor * force
        # Project back into Poincare ball if escaping
        tl.store(u_out_ptr + offs * D + d, u_new, mask=mask)


def triton_poincare_discrete_dromion(u: torch.Tensor, dt: float = 0.01, c1: float = 1.5, c2: float = 1.5):
    """
    Executes the Fused Poincaré Discrete Dromion Lattice flow kernel.
    u: [N, D] tensor on CUDA (D >= 2).
    """
    assert u.is_cuda and u.is_contiguous()
    N, D = u.shape
    assert D >= 2, "Dromion requires at least D=2 dimensions."
    
    u_out = torch.empty_like(u)
    metric = torch.empty(N, dtype=torch.float32, device=u.device)
    pot = torch.empty(N, dtype=torch.float32, device=u.device)

    BLOCK_SIZE = 1024
    grid = (triton.cdiv(N, BLOCK_SIZE),)

    _poincare_discrete_dromion_kernel[grid](
        u, u_out, metric, pot,
        N=N, D=D, dt=dt, c1=c1, c2=c2,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return u_out, metric, pot


def pytorch_poincare_discrete_dromion_ref(u: torch.Tensor, dt: float = 0.01, c1: float = 1.5, c2: float = 1.5):
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

    arg0 = torch.clamp(c1 * u0, -10.0, 10.0)
    arg1 = torch.clamp(c2 * u1, -10.0, 10.0)

    cosh0 = torch.cosh(arg0)
    sech0 = 1.0 / cosh0
    tanh0 = torch.tanh(arg0)

    cosh1 = torch.cosh(arg1)
    sech1 = 1.0 / cosh1
    tanh1 = torch.tanh(arg1)

    denom = 1.0 + 0.5 * tanh0 * tanh1
    dromion_pot = (4.0 * c1 * c2 * (sech0 ** 2) * (sech1 ** 2)) / (denom ** 2)

    decay_factor = (one_minus_r2_safe ** 2) * 0.25
    u_out = u.clone()

    f0 = -2.0 * c1 * tanh0 * dromion_pot
    f1 = -2.0 * c2 * tanh1 * dromion_pot

    u_out[:, 0] = u[:, 0] + dt * decay_factor * f0
    u_out[:, 1] = u[:, 1] + dt * decay_factor * f1
    if u.shape[1] > 2:
        for d in range(2, u.shape[1]):
            fd = -0.5 * u[:, d] * dromion_pot
            u_out[:, d] = u[:, d] + dt * decay_factor * fd

    return u_out, metric, dromion_pot


if __name__ == "__main__":
    if not torch.cuda.is_available():
        print("CUDA not available, skipping.")
        exit(0)

    torch.manual_seed(42)
    N = 131072 # 128k nodes
    D = 16
    u = (torch.rand(N, D, device="cuda") - 0.5) * 0.8 # well inside Poincaré disk

    # Correctness check
    u_tri, m_tri, p_tri = triton_poincare_discrete_dromion(u)
    u_ref, m_ref, p_ref = pytorch_poincare_discrete_dromion_ref(u)

    max_u_err = (u_tri - u_ref).abs().max().item()
    max_m_err = (m_tri - m_ref).abs().max().item()
    max_p_err = (p_tri - p_ref).abs().max().item()

    print(f"Correctness: Max u error: {max_u_err:.2e}, Max metric error: {max_m_err:.2e}, Max pot error: {max_p_err:.2e}")
    assert max_u_err < 1e-4, f"u error too high: {max_u_err}"
    assert max_p_err < 1e-4, f"pot error too high: {max_p_err}"

    # Benchmark
    warmup = 20
    iters = 100
    for _ in range(warmup):
        _ = triton_poincare_discrete_dromion(u)
    torch.cuda.synchronize()

    start_event = torch.cuda.Event(enable_timing=True)
    end_event = torch.cuda.Event(enable_timing=True)

    start_event.record()
    for _ in range(iters):
        _ = triton_poincare_discrete_dromion(u)
    end_event.record()
    torch.cuda.synchronize()

    elapsed_ms = start_event.elapsed_time(end_event) / iters
    throughput = (N / (elapsed_ms / 1000.0)) / 1e6
    print(f"Triton Discrete Dromion Kernel Latency: {elapsed_ms * 1000:.2f} us | Throughput: {throughput:.2f} M nodes/s")
