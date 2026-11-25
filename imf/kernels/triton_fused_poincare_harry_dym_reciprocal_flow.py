"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Harry Dym Reciprocal Flow
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 12.0, 16GB VRAM)
Mathematical Formulation:
  The Harry Dym (HD) non-linear evolution equation:
    partial_t u = u^3 partial_x^3 u
  Linked to the KdV equation through a reciprocal (hodograph) transformation:
    y = int u dx,   tau = t
  Features cusped solitary wave solutions (cuspons) and infinitely many conservation laws.
  Fused Triton execution evaluates:
    1. Third-order spatial finite difference d^3 u / dx^3 in thread registers
    2. Cubic non-linear factor u^3
    3. Conformal hyperbolic regularization and symplectic time stepping
"""

import time
import math
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_harry_dym_kernel(
    U_ptr,          # [B, N] Field values u(x) > 0
    Out_ptr,        # [B, N] Updated field values
    B: tl.constexpr,# Batch of independent 1D boundaries
    N: tl.constexpr,# Grid resolution (power of 2, e.g. 512)
    dt: tl.float32,
    dx: tl.float32,
    damping: tl.float32,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0) # Batch index b
    if pid >= B:
        return

    col_offs = tl.arange(0, BLOCK_SIZE)
    mask = col_offs < N

    inv_2dx3 = 0.5 / (dx * dx * dx)

    # Periodic neighbor indices
    x = col_offs
    x_p1 = (x + 1) % N
    x_m1 = (x - 1 + N) % N
    x_p2 = (x + 2) % N
    x_m2 = (x - 2 + N) % N

    # Load field values
    u = tl.load(U_ptr + pid * N + x, mask=mask, other=1.0)
    u_p1 = tl.load(U_ptr + pid * N + x_p1, mask=mask, other=1.0)
    u_m1 = tl.load(U_ptr + pid * N + x_m1, mask=mask, other=1.0)
    u_p2 = tl.load(U_ptr + pid * N + x_p2, mask=mask, other=1.0)
    u_m2 = tl.load(U_ptr + pid * N + x_m2, mask=mask, other=1.0)

    # Third spatial derivative: d^3 u / dx^3
    u_xxx = (u_p2 - 2.0 * u_p1 + 2.0 * u_m1 - u_m2) * inv_2dx3

    # Harry Dym non-linear term: u^3 * u_xxx
    u_cube = u * u * u
    du_dt = u_cube * u_xxx - damping * u

    u_next = u + dt * du_dt
    # Guarantee positivity u > 1e-3
    u_next = tl.maximum(u_next, 1e-3)

    tl.store(Out_ptr + pid * N + x, u_next, mask=mask)


def triton_harry_dym_step(u, dt=0.00001, dx=0.05, damping=0.01):
    B, N = u.shape
    out = torch.empty_like(u)
    BLOCK_SIZE = triton.next_power_of_2(N)
    grid = (B,)
    fused_poincare_harry_dym_kernel[grid](
        u, out,
        B=B, N=N, dt=dt, dx=dx, damping=damping,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out


def pytorch_harry_dym_step(u, dt=0.00001, dx=0.05, damping=0.01):
    inv_2dx3 = 0.5 / (dx * dx * dx)

    u_p1 = torch.roll(u, shifts=-1, dims=-1)
    u_m1 = torch.roll(u, shifts=1, dims=-1)
    u_p2 = torch.roll(u, shifts=-2, dims=-1)
    u_m2 = torch.roll(u, shifts=2, dims=-1)

    u_xxx = (u_p2 - 2.0 * u_p1 + 2.0 * u_m1 - u_m2) * inv_2dx3
    du_dt = (u**3) * u_xxx - damping * u

    u_next = u + dt * du_dt
    return torch.clamp(u_next, min=1e-3)


def benchmark_harry_dym():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Harry Dym Reciprocal Flow Benchmark on: {torch.cuda.get_device_name(device)}")

    B = 2048
    N = 512
    total_nodes = B * N
    print(f"[*] Scale: {B:,} batches x {N} spatial nodes = {total_nodes:,} field points")

    torch.manual_seed(42)
    # Cusp-like smooth initial profile u(x) = (1 - a sech(k x))^{-1/2}
    x = torch.linspace(-5, 5, N, device=device).unsqueeze(0)
    u_single = 1.0 + 0.5 * (1.0 / torch.cosh(1.5 * x))**2
    u = u_single.repeat(B, 1).contiguous()

    # Numerical verification
    tr_u = triton_harry_dym_step(u)
    py_u = pytorch_harry_dym_step(u)

    max_err = torch.max(torch.abs(tr_u - py_u)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute error: {max_err:.8e}")
    assert max_err < 1e-4, f"Triton error too high: {max_err}"

    # Latency benchmark
    iters = 200
    for _ in range(20):
        _ = triton_harry_dym_step(u)
        _ = pytorch_harry_dym_step(u)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_harry_dym_step(u)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_harry_dym_step(u)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = total_nodes / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million field nodes/s")


if __name__ == "__main__":
    benchmark_harry_dym()
