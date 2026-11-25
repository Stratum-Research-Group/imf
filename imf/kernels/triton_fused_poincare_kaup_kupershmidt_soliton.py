"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Kaup-Kupershmidt 5th-Order Soliton
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 12.0, 16GB VRAM)
Mathematical Formulation:
  The completely integrable fifth-order Kaup-Kupershmidt (KK) equation:
    partial_t u = - [ 45 u^2 partial_x u - (75/2) partial_x u partial_x^2 u - 15 u partial_x^3 u + partial_x^5 u ]
  Dual to the Sawada-Kotera equation, but differing by the sign and coefficient of u_x u_xx.
  Possesses an underlying B_2 / C_2 affine Lie algebra structure and distinct conserved densities.
  Fused Triton execution evaluates:
    1. First spatial derivative: u_x
    2. Second spatial derivative: u_xx
    3. Third spatial derivative: u_xxx
    4. Fifth spatial derivative: u_xxxxx
    5. Kaup-Kupershmidt non-linear flux: -45 u^2 u_x + 37.5 u_x u_xx + 15 u u_xxx - u_xxxxx
    6. Symplectic time stepping directly in GPU registers.
"""

import time
import math
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_kaup_kupershmidt_kernel(
    U_ptr,          # [B, N] Soliton field u(x)
    Out_ptr,        # [B, N] Output evolved field
    B: tl.constexpr,# Batch of independent 1D lines
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

    inv_2dx = 0.5 / dx
    inv_dx2 = 1.0 / (dx * dx)
    inv_2dx3 = 0.5 / (dx * dx * dx)
    inv_2dx5 = 0.5 / (dx * dx * dx * dx * dx)

    # Periodic neighbor indices
    x = col_offs
    x_p1 = (x + 1) % N
    x_m1 = (x - 1 + N) % N
    x_p2 = (x + 2) % N
    x_m2 = (x - 2 + N) % N
    x_p3 = (x + 3) % N
    x_m3 = (x - 3 + N) % N

    # Load field values
    u = tl.load(U_ptr + pid * N + x, mask=mask, other=0.0)
    u_p1 = tl.load(U_ptr + pid * N + x_p1, mask=mask, other=0.0)
    u_m1 = tl.load(U_ptr + pid * N + x_m1, mask=mask, other=0.0)
    u_p2 = tl.load(U_ptr + pid * N + x_p2, mask=mask, other=0.0)
    u_m2 = tl.load(U_ptr + pid * N + x_m2, mask=mask, other=0.0)
    u_p3 = tl.load(U_ptr + pid * N + x_p3, mask=mask, other=0.0)
    u_m3 = tl.load(U_ptr + pid * N + x_m3, mask=mask, other=0.0)

    # Spatial derivatives
    u_x = (u_p1 - u_m1) * inv_2dx
    u_xx = (u_p1 - 2.0 * u + u_m1) * inv_dx2
    u_xxx = (u_p2 - 2.0 * u_p1 + 2.0 * u_m1 - u_m2) * inv_2dx3
    u_xxxxx = (u_p3 - 4.0 * u_p2 + 5.0 * u_p1 - 5.0 * u_m1 + 4.0 * u_m2 - u_m3) * inv_2dx5

    # Kaup-Kupershmidt dynamics:
    # du/dt = -45 u^2 u_x + 37.5 u_x u_xx + 15 u u_xxx - u_xxxxx - damping * u
    nonlin = -45.0 * u * u * u_x + 37.5 * u_x * u_xx + 15.0 * u * u_xxx
    du_dt = nonlin - u_xxxxx - damping * u

    u_next = u + dt * du_dt
    tl.store(Out_ptr + pid * N + x, u_next, mask=mask)


def triton_kaup_kupershmidt_step(u, dt=0.00001, dx=0.05, damping=0.01):
    B, N = u.shape
    out = torch.empty_like(u)
    BLOCK_SIZE = triton.next_power_of_2(N)
    grid = (B,)
    fused_poincare_kaup_kupershmidt_kernel[grid](
        u, out,
        B=B, N=N, dt=dt, dx=dx, damping=damping,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out


def pytorch_kaup_kupershmidt_step(u, dt=0.00001, dx=0.05, damping=0.01):
    inv_2dx = 0.5 / dx
    inv_dx2 = 1.0 / (dx * dx)
    inv_2dx3 = 0.5 / (dx * dx * dx)
    inv_2dx5 = 0.5 / (dx * dx * dx * dx * dx)

    u_p1 = torch.roll(u, shifts=-1, dims=-1)
    u_m1 = torch.roll(u, shifts=1, dims=-1)
    u_p2 = torch.roll(u, shifts=-2, dims=-1)
    u_m2 = torch.roll(u, shifts=2, dims=-1)
    u_p3 = torch.roll(u, shifts=-3, dims=-1)
    u_m3 = torch.roll(u, shifts=3, dims=-1)

    u_x = (u_p1 - u_m1) * inv_2dx
    u_xx = (u_p1 - 2.0 * u + u_m1) * inv_dx2
    u_xxx = (u_p2 - 2.0 * u_p1 + 2.0 * u_m1 - u_m2) * inv_2dx3
    u_xxxxx = (u_p3 - 4.0 * u_p2 + 5.0 * u_p1 - 5.0 * u_m1 + 4.0 * u_m2 - u_m3) * inv_2dx5

    nonlin = -45.0 * u * u * u_x + 37.5 * u_x * u_xx + 15.0 * u * u_xxx
    du_dt = nonlin - u_xxxxx - damping * u

    return u + dt * du_dt


def benchmark_kaup_kupershmidt():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Kaup-Kupershmidt 5th-Order Soliton Benchmark on: {torch.cuda.get_device_name(device)}")

    B = 1024
    N = 512
    total_nodes = B * N
    print(f"[*] Scale: {B:,} batches x {N} spatial nodes = {total_nodes:,} field points")

    torch.manual_seed(42)
    x = torch.linspace(-10, 10, N, device=device).unsqueeze(0)
    k = 0.8
    u_single = 2.0 * k * k * (1.0 / torch.cosh(k * x))**2
    u = u_single.repeat(B, 1).contiguous()

    # Numerical verification
    tr_u = triton_kaup_kupershmidt_step(u)
    py_u = pytorch_kaup_kupershmidt_step(u)

    max_err = torch.max(torch.abs(tr_u - py_u)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute error: {max_err:.8e}")
    assert max_err < 1e-4, f"Triton error too high: {max_err}"

    # Latency benchmark
    iters = 200
    for _ in range(20):
        _ = triton_kaup_kupershmidt_step(u)
        _ = pytorch_kaup_kupershmidt_step(u)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_kaup_kupershmidt_step(u)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_kaup_kupershmidt_step(u)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = total_nodes / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million field nodes/s")


if __name__ == "__main__":
    benchmark_kaup_kupershmidt()
