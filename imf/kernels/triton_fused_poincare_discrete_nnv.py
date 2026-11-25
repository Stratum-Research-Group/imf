"""
Triton Fused Discrete Nizhnik-Novikov-Veselov (NNV) Soliton Flow Kernel on Poincaré Ball.
Cycle 284: (2+1)D isotropic Lax-integrable Nizhnik-Novikov-Veselov lattice dynamics
on the Poincaré hyperbolic unit ball B^d.

The NNV equation is the symmetric, isotropic (2+1)-dimensional generalization of KdV:
  u_t + a u_{xxx} + b u_{yyy} + 3 a (u v)_x + 3 b (u w)_y = 0
  v_y = u_x,  w_x = u_y
where u(x, y, t) represents localized multidimensional coherent dromion wave packets.
On the Poincaré ball B^d with conformal metric ds^2 = 4 dx^2 / (1 - ||u||^2)^2,
we discretize the symmetric bi-directional dispersion and gradient flow.
"""

import math
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_discrete_nnv_kernel(
    u_ptr,           # Input coordinates [N, D]
    u_out_ptr,       # Output updated coordinates [N, D]
    metric_ptr,      # Output conformal metric factors [N]
    nnv_pot_ptr,     # Output NNV localized dromion potential [N]
    N: tl.constexpr,
    D: tl.constexpr,
    dt: tl.constexpr,
    p1: tl.constexpr,
    q1: tl.constexpr,
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

    # 2. Symmetric NNV Isotropic Soliton Potential
    # In transverse plane x = u[0], y = u[1]:
    # u_{NNV}(x, y) = 2 * (p1 + q1) * sech^2(p1 * x) * sech^2(q1 * y) / (1 + 0.25 * tanh(p1 * x) * tanh(q1 * y))^2
    u0 = tl.load(u_ptr + offs * D + 0, mask=mask, other=0.0)
    u1 = tl.load(u_ptr + offs * D + 1, mask=mask, other=0.0)

    arg0 = tl.maximum(tl.minimum(p1 * u0, 10.0), -10.0)
    arg1 = tl.maximum(tl.minimum(q1 * u1, 10.0), -10.0)

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

    denom = 1.0 + 0.25 * tanh0 * tanh1
    denom_sq = denom * denom

    nnv_pot = (2.0 * (p1 + q1) * (sech0 * sech0) * (sech1 * sech1)) / denom_sq
    tl.store(nnv_pot_ptr + offs, nnv_pot, mask=mask)

    # 3. Conformal Hyperbolic Gradient Flow
    decay_factor = (one_minus_r2_safe * one_minus_r2_safe) * 0.25

    for d in range(D):
        u_val = tl.load(u_ptr + offs * D + d, mask=mask, other=0.0)
        if d == 0:
            force = -2.0 * p1 * tanh0 * nnv_pot
        elif d == 1:
            force = -2.0 * q1 * tanh1 * nnv_pot
        else:
            force = -0.5 * u_val * nnv_pot

        u_new = u_val + dt * decay_factor * force
        tl.store(u_out_ptr + offs * D + d, u_new, mask=mask)


def triton_poincare_discrete_nnv(
    u: torch.Tensor, dt: float = 0.01, p1: float = 1.4, q1: float = 1.4
):
    """
    Executes the Fused Poincaré Discrete NNV Soliton flow kernel.
    u: [N, D] tensor on CUDA (D >= 2).
    """
    assert u.is_cuda and u.is_contiguous()
    N, D = u.shape
    assert D >= 2, "NNV requires at least D=2 dimensions."

    u_out = torch.empty_like(u)
    metric = torch.empty(N, dtype=torch.float32, device=u.device)
    pot = torch.empty(N, dtype=torch.float32, device=u.device)

    BLOCK_SIZE = 1024
    grid = (triton.cdiv(N, BLOCK_SIZE),)

    _poincare_discrete_nnv_kernel[grid](
        u, u_out, metric, pot,
        N=N, D=D, dt=dt, p1=p1, q1=q1,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return u_out, metric, pot


def pytorch_poincare_discrete_nnv_ref(
    u: torch.Tensor, dt: float = 0.01, p1: float = 1.4, q1: float = 1.4
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
    arg0 = torch.clamp(p1 * u0, -10.0, 10.0)
    arg1 = torch.clamp(q1 * u1, -10.0, 10.0)

    cosh0 = torch.cosh(arg0)
    sech0 = 1.0 / cosh0
    tanh0 = torch.tanh(arg0)

    cosh1 = torch.cosh(arg1)
    sech1 = 1.0 / cosh1
    tanh1 = torch.tanh(arg1)

    denom = 1.0 + 0.25 * tanh0 * tanh1
    nnv_pot = (2.0 * (p1 + q1) * (sech0 ** 2) * (sech1 ** 2)) / (denom ** 2)

    decay_factor = (one_minus_r2_safe ** 2) * 0.25
    u_out = u.clone()

    f0 = -2.0 * p1 * tanh0 * nnv_pot
    f1 = -2.0 * q1 * tanh1 * nnv_pot

    u_out[:, 0] = u[:, 0] + dt * decay_factor * f0
    u_out[:, 1] = u[:, 1] + dt * decay_factor * f1
    if u.shape[1] > 2:
        for d in range(2, u.shape[1]):
            fd = -0.5 * u[:, d] * nnv_pot
            u_out[:, d] = u[:, d] + dt * decay_factor * fd

    return u_out, metric, nnv_pot


if __name__ == "__main__":
    if not torch.cuda.is_available():
        print("CUDA not available, skipping.")
        exit(0)

    torch.manual_seed(42)
    N = 131072 # 128k nodes
    D = 16
    u = (torch.rand(N, D, device="cuda") - 0.5) * 0.8

    # Correctness check
    u_tri, m_tri, p_tri = triton_poincare_discrete_nnv(u)
    u_ref, m_ref, p_ref = pytorch_poincare_discrete_nnv_ref(u)

    max_u_err = (u_tri - u_ref).abs().max().item()
    max_p_err = (p_tri - p_ref).abs().max().item()

    print(f"Correctness: Max u error: {max_u_err:.2e}, Max pot error: {max_p_err:.2e}")
    assert max_u_err < 1e-4, f"u error too high: {max_u_err}"
    assert max_p_err < 1e-4, f"pot error too high: {max_p_err}"

    # Benchmark
    warmup = 20
    iters = 100
    for _ in range(warmup):
        _ = triton_poincare_discrete_nnv(u)
    torch.cuda.synchronize()

    start_event = torch.cuda.Event(enable_timing=True)
    end_event = torch.cuda.Event(enable_timing=True)

    start_event.record()
    for _ in range(iters):
        _ = triton_poincare_discrete_nnv(u)
    end_event.record()
    torch.cuda.synchronize()

    elapsed_ms = start_event.elapsed_time(end_event) / iters
    throughput = (N / (elapsed_ms / 1000.0)) / 1e6
    print(f"Triton Discrete NNV Kernel Latency: {elapsed_ms * 1000:.2f} us | Throughput: {throughput:.2f} M nodes/s")
