"""
Triton GPU Kernel: Fused Poincaré Continuous Flow ODE Solver (RK4) (RTX 5060 Ti)

Implements continuous-depth hyperbolic Neural ODE integration via 4th-order Runge-Kutta:
  Given initial state X_0 in B^D, integrate along vector field f(x, t) in tangent space T_x B^D:
  For step size dt:
    k1 = f(x_n, t_n)
    k2 = f(x_n + 0.5 * dt * k1, t_n + 0.5 * dt)
    k3 = f(x_n + 0.5 * dt * k2, t_n + 0.5 * dt)
    k4 = f(x_n + dt * k3, t_n + dt)
    x_{n+1} = exp_0(log_0(x_n) + (dt / 6) * (k1 + 2*k2 + 2*k3 + k4))

Enables continuous-depth generative flows directly constrained to the Poincaré ball.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_continuous_flow_rk4_kernel(
    X_ptr,          # [M, D] (fp16)
    W_flow_ptr,     # [D, D] (fp16)
    Out_ptr,        # [M, D] (fp16)
    dt: tl.constexpr,
    STEPS: tl.constexpr,
    M: tl.constexpr,
    D: tl.constexpr,
    BLOCK_M: tl.constexpr,
    c: tl.constexpr,
):
    pid = tl.program_id(0)
    offs_m = pid * BLOCK_M + tl.arange(0, BLOCK_M)
    mask_m = offs_m < M
    offs_d = tl.arange(0, D)

    # 1. Load initial state X_0: [BLOCK_M, D]
    x_curr = tl.load(X_ptr + offs_m[:, None] * D + offs_d[None, :], mask=mask_m[:, None], other=0.0)
    w_flow = tl.load(W_flow_ptr + offs_d[:, None] * D + offs_d[None, :])

    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))

    # Iterate over continuous integration steps
    for step in range(STEPS):
        x_f32 = x_curr.to(tl.float32)

        # k1 = x @ W_flow
        k1 = tl.dot(x_curr, w_flow) # fp32

        # k2 = (x + 0.5 * dt * k1) @ W_flow
        x_k2 = (x_f32 + 0.5 * dt * k1).to(tl.float16)
        k2 = tl.dot(x_k2, w_flow)

        # k3 = (x + 0.5 * dt * k2) @ W_flow
        x_k3 = (x_f32 + 0.5 * dt * k2).to(tl.float16)
        k3 = tl.dot(x_k3, w_flow)

        # k4 = (x + dt * k3) @ W_flow
        x_k4 = (x_f32 + dt * k3).to(tl.float16)
        k4 = tl.dot(x_k4, w_flow)

        # RK4 weighted step: x_next = x + (dt / 6) * (k1 + 2*k2 + 2*k3 + k4)
        delta = (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        x_next_tan = x_f32 + delta

        # Retract to Poincare ball via exp_0^c
        sq_norm = tl.sum(x_next_tan * x_next_tan, axis=1)
        norm = tl.sqrt(sq_norm + 1e-12)
        u = sqrt_c * norm
        u_clamped = tl.minimum(u, 15.0)
        exp_2u = tl.exp(2.0 * u_clamped)
        tanh_u = (exp_2u - 1.0) / (exp_2u + 1.0)
        scale = tanh_u / (sqrt_c * norm)

        x_curr = (x_next_tan * scale[:, None]).to(tl.float16)

    tl.store(Out_ptr + offs_m[:, None] * D + offs_d[None, :], x_curr, mask=mask_m[:, None])


def poincare_continuous_flow_pytorch(X, W_flow, dt=0.05, steps=4, c=1.0):
    """Reference PyTorch implementation."""
    x_curr = X.clone().float()
    w_f = W_flow.float()
    sqrt_c = math.sqrt(c)

    for _ in range(steps):
        k1 = torch.matmul(x_curr, w_f)
        k2 = torch.matmul(x_curr + 0.5 * dt * k1, w_f)
        k3 = torch.matmul(x_curr + 0.5 * dt * k2, w_f)
        k4 = torch.matmul(x_curr + dt * k3, w_f)

        delta = (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        x_next_tan = x_curr + delta

        norm = torch.norm(x_next_tan, p=2, dim=-1, keepdim=True).clamp(min=1e-8)
        scale = torch.tanh(sqrt_c * norm) / (sqrt_c * norm)
        x_curr = x_next_tan * scale

    return x_curr.half()


def poincare_continuous_flow_triton(X, W_flow, dt=0.05, steps=4, c=1.0):
    M, D = X.shape
    out = torch.empty_like(X)

    BLOCK_M = 32
    grid = (triton.cdiv(M, BLOCK_M),)
    _poincare_continuous_flow_rk4_kernel[grid](
        X, W_flow, out,
        dt=dt, STEPS=steps, M=M, D=D, BLOCK_M=BLOCK_M, c=c,
    )
    return out


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré Continuous Flow ODE (RK4) on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    M = 2048         # Tokens
    D = 64           # Dimension
    dt = 0.05        # Integration time-step
    steps = 4        # Continuous flow steps
    c = 1.0

    X = (torch.randn((M, D), device=device, dtype=torch.float32) * 0.05).half()
    W_flow = (torch.randn((D, D), device=device, dtype=torch.float32) * (0.5 / math.sqrt(D))).half()

    # Correctness check
    out_pt = poincare_continuous_flow_pytorch(X, W_flow, dt, steps, c)
    out_triton = poincare_continuous_flow_triton(X, W_flow, dt, steps, c)

    max_err = (out_pt.float() - out_triton.float()).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-2, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-2 fp16 error)!")

    # Warmup
    for _ in range(50):
        poincare_continuous_flow_pytorch(X, W_flow, dt, steps, c)
        poincare_continuous_flow_triton(X, W_flow, dt, steps, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 300
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_continuous_flow_pytorch(X, W_flow, dt, steps, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_continuous_flow_triton(X, W_flow, dt, steps, c)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    tokens_per_sec = M / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {tokens_per_sec / 1e6:.2f} M tokens/sec")


if __name__ == "__main__":
    benchmark()
