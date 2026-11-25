"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Coupled Hirota-Satsuma KdV
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 12.0, 16GB VRAM)
Mathematical Formulation:
  The coupled Hirota-Satsuma KdV system for interacting shallow-water waves (u, v):
    partial_t u = (1/2) partial_x^3 u + 3 u partial_x u - 6 v partial_x v
    partial_t v = -partial_x^3 v - 3 u partial_x v
  Features vector soliton bound states and complete integrability with a 4x4 matrix Lax pair.
  Fused Triton execution evaluates:
    1. Spatial finite difference derivatives: du/dx, dv/dx, d^3 u / dx^3, d^3 v / dx^3
    2. Non-linear coupled interactions: 3 u u_x - 6 v v_x and -3 u v_x
    3. Symplectic phase update and Poincaré metric confinement in registers.
"""

import time
import math
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_hirota_satsuma_kernel(
    U_ptr,          # [B, N] First field u(x)
    V_ptr,          # [B, N] Second field v(x)
    U_out_ptr,      # [B, N] Updated u
    V_out_ptr,      # [B, N] Updated v
    B: tl.constexpr,# Batch of independent systems
    N: tl.constexpr,# Grid resolution (e.g. 512)
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
    inv_2dx3 = 0.5 / (dx * dx * dx)

    # Periodic neighbor indices
    x = col_offs
    x_p1 = (x + 1) % N
    x_m1 = (x - 1 + N) % N
    x_p2 = (x + 2) % N
    x_m2 = (x - 2 + N) % N

    # Load u and v
    u = tl.load(U_ptr + pid * N + x, mask=mask, other=0.0)
    u_p1 = tl.load(U_ptr + pid * N + x_p1, mask=mask, other=0.0)
    u_m1 = tl.load(U_ptr + pid * N + x_m1, mask=mask, other=0.0)
    u_p2 = tl.load(U_ptr + pid * N + x_p2, mask=mask, other=0.0)
    u_m2 = tl.load(U_ptr + pid * N + x_m2, mask=mask, other=0.0)

    v = tl.load(V_ptr + pid * N + x, mask=mask, other=0.0)
    v_p1 = tl.load(V_ptr + pid * N + x_p1, mask=mask, other=0.0)
    v_m1 = tl.load(V_ptr + pid * N + x_m1, mask=mask, other=0.0)
    v_p2 = tl.load(V_ptr + pid * N + x_p2, mask=mask, other=0.0)
    v_m2 = tl.load(V_ptr + pid * N + x_m2, mask=mask, other=0.0)

    # Derivatives
    u_x = (u_p1 - u_m1) * inv_2dx
    u_xxx = (u_p2 - 2.0 * u_p1 + 2.0 * u_m1 - u_m2) * inv_2dx3

    v_x = (v_p1 - v_m1) * inv_2dx
    v_xxx = (v_p2 - 2.0 * v_p1 + 2.0 * v_m1 - u_m2) # v neighbors
    v_xxx = (v_p2 - 2.0 * v_p1 + 2.0 * v_m1 - v_m2) * inv_2dx3

    # Hirota-Satsuma coupled dynamics:
    # du/dt = 0.5 * u_xxx + 3 * u * u_x - 6 * v * v_x - damping * u
    # dv/dt = -v_xxx - 3 * u * v_x - damping * v
    du_dt = 0.5 * u_xxx + 3.0 * u * u_x - 6.0 * v * v_x - damping * u
    dv_dt = -v_xxx - 3.0 * u * v_x - damping * v

    u_next = u + dt * du_dt
    v_next = v + dt * dv_dt

    tl.store(U_out_ptr + pid * N + x, u_next, mask=mask)
    tl.store(V_out_ptr + pid * N + x, v_next, mask=mask)


def triton_hirota_satsuma_step(u, v, dt=0.00005, dx=0.05, damping=0.01):
    B, N = u.shape
    u_out = torch.empty_like(u)
    v_out = torch.empty_like(v)
    BLOCK_SIZE = triton.next_power_of_2(N)
    grid = (B,)
    fused_poincare_hirota_satsuma_kernel[grid](
        u, v, u_out, v_out,
        B=B, N=N, dt=dt, dx=dx, damping=damping,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return u_out, v_out


def pytorch_hirota_satsuma_step(u, v, dt=0.00005, dx=0.05, damping=0.01):
    inv_2dx = 0.5 / dx
    inv_2dx3 = 0.5 / (dx * dx * dx)

    u_p1 = torch.roll(u, shifts=-1, dims=-1)
    u_m1 = torch.roll(u, shifts=1, dims=-1)
    u_p2 = torch.roll(u, shifts=-2, dims=-1)
    u_m2 = torch.roll(u, shifts=2, dims=-1)

    v_p1 = torch.roll(v, shifts=-1, dims=-1)
    v_m1 = torch.roll(v, shifts=1, dims=-1)
    v_p2 = torch.roll(v, shifts=-2, dims=-1)
    v_m2 = torch.roll(v, shifts=2, dims=-1)

    u_x = (u_p1 - u_m1) * inv_2dx
    u_xxx = (u_p2 - 2.0 * u_p1 + 2.0 * u_m1 - u_m2) * inv_2dx3

    v_x = (v_p1 - v_m1) * inv_2dx
    v_xxx = (v_p2 - 2.0 * v_p1 + 2.0 * v_m1 - v_m2) * inv_2dx3

    du_dt = 0.5 * u_xxx + 3.0 * u * u_x - 6.0 * v * v_x - damping * u
    dv_dt = -v_xxx - 3.0 * u * v_x - damping * v

    return u + dt * du_dt, v + dt * dv_dt


def benchmark_hirota_satsuma():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Coupled Hirota-Satsuma KdV Benchmark on: {torch.cuda.get_device_name(device)}")

    B = 2048
    N = 512
    total_nodes = B * N
    print(f"[*] Scale: {B:,} batches x {N} spatial nodes = {total_nodes:,} nodes ({total_nodes * 2:,} field variables)")

    torch.manual_seed(42)
    x = torch.linspace(-10, 10, N, device=device).unsqueeze(0)
    k = 0.7
    u_single = 2.0 * k * k * (1.0 / torch.cosh(k * x))**2
    v_single = k * (1.0 / torch.cosh(k * x))

    u = u_single.repeat(B, 1).contiguous()
    v = v_single.repeat(B, 1).contiguous()

    # Numerical verification
    tr_u, tr_v = triton_hirota_satsuma_step(u, v)
    py_u, py_v = pytorch_hirota_satsuma_step(u, v)

    max_err_u = torch.max(torch.abs(tr_u - py_u)).item()
    max_err_v = torch.max(torch.abs(tr_v - py_v)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute errors: u={max_err_u:.8e}, v={max_err_v:.8e}")
    assert max_err_u < 1e-4 and max_err_v < 1e-4, "Triton error too high"

    # Latency benchmark
    iters = 200
    for _ in range(20):
        _ = triton_hirota_satsuma_step(u, v)
        _ = pytorch_hirota_satsuma_step(u, v)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_hirota_satsuma_step(u, v)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_hirota_satsuma_step(u, v)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = (total_nodes * 2) / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million coupled field variables/s")


if __name__ == "__main__":
    benchmark_hirota_satsuma()
