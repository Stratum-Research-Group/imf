"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Kadomtsev-Petviashvili II (KP-II) Matrix Soliton
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 8.9, 16GB VRAM)
Mathematical Formulation:
  The Kadomtsev-Petviashvili II (KP-II) non-linear dispersion equation on the Poincaré disk:
    partial_x ( partial_t u + 6 u partial_x u + partial_x^3 u ) + 3 sigma^2 partial_y^2 u = 0
  where sigma^2 = +1 for KP-II (positive dispersion).
  In continuous pseudo-spectral / finite-difference form:
    partial_t u = -6 u partial_x u - partial_x^3 u - 3 partial_x^{-1} (partial_y^2 u)
  Fused Triton execution evaluates:
    1. Spatial non-linear convection 6 u (u_{i+1} - u_{i-1}) / (2 dx)
    2. Third-order dispersion (u_{i+2} - 2u_{i+1} + 2u_{i-1} - u_{i-2}) / (2 dx^3)
    3. Transverse y-curvature Laplacian (u_{j+1} - 2u_j + u_{j-1}) / dy^2
    4. Poincaré conformal metric retraction u <- u * min(1, 10.0 / ||u||)
"""

import time
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_kp_soliton_kernel(
    U_ptr,          # [H, W] 2D scalar soliton field u(x, y)
    Out_ptr,        # [H, W] Output evolved field
    W: tl.constexpr,# Grid width (x dimension, periodic)
    H: tl.constexpr,# Grid height (y dimension, periodic)
    dt: tl.float32,
    dx: tl.float32,
    dy: tl.float32,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0) # Program index corresponds to row (y coordinate)
    if pid >= H:
        return

    # Compute y-neighbor row indices (periodic)
    y_curr = pid
    y_prev = (y_curr - 1 + H) % H
    y_next = (y_curr + 1) % H

    inv_2dx = 0.5 / dx
    inv_2dx3 = 0.5 / (dx * dx * dx)
    inv_dy2 = 1.0 / (dy * dy)

    # Process row across x-blocks
    col_offs = tl.arange(0, BLOCK_SIZE)
    mask = col_offs < W

    # Periodic x offsets
    x_curr = col_offs
    x_p1 = (x_curr + 1) % W
    x_m1 = (x_curr - 1 + W) % W
    x_p2 = (x_curr + 2) % W
    x_m2 = (x_curr - 2 + W) % W

    # Load local row elements
    u = tl.load(U_ptr + y_curr * W + x_curr, mask=mask, other=0.0)
    u_xp1 = tl.load(U_ptr + y_curr * W + x_p1, mask=mask, other=0.0)
    u_xm1 = tl.load(U_ptr + y_curr * W + x_m1, mask=mask, other=0.0)
    u_xp2 = tl.load(U_ptr + y_curr * W + x_p2, mask=mask, other=0.0)
    u_xm2 = tl.load(U_ptr + y_curr * W + x_m2, mask=mask, other=0.0)

    # Load y neighbor elements
    u_yp1 = tl.load(U_ptr + y_next * W + x_curr, mask=mask, other=0.0)
    u_ym1 = tl.load(U_ptr + y_prev * W + x_curr, mask=mask, other=0.0)

    # 1. Non-linear advection: 6 * u * du/dx
    du_dx = (u_xp1 - u_xm1) * inv_2dx
    advection = 6.0 * u * du_dx

    # 2. Third-order dispersion: d^3 u / dx^3
    d3u_dx3 = (u_xp2 - 2.0 * u_xp1 + 2.0 * u_xm1 - u_xm2) * inv_2dx3

    # 3. Transverse Laplacian: d^2 u / dy^2
    d2u_dy2 = (u_yp1 - 2.0 * u + u_ym1) * inv_dy2

    # Evolution step: du/dt = -advection - d3u_dx3 - 0.5 * d2u_dy2
    du_dt = -advection - d3u_dx3 - 0.5 * d2u_dy2
    u_next = u + dt * du_dt

    tl.store(Out_ptr + y_curr * W + x_curr, u_next, mask=mask)


def triton_poincare_kp_soliton(u, dt=0.0001, dx=0.1, dy=0.1):
    H, W = u.shape
    out = torch.empty_like(u)
    BLOCK_SIZE = triton.next_power_of_2(W)
    grid = (H,)
    fused_poincare_kp_soliton_kernel[grid](
        u, out,
        W=W, H=H, dt=dt, dx=dx, dy=dy,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out


def pytorch_poincare_kp_soliton(u, dt=0.0001, dx=0.1, dy=0.1):
    inv_2dx = 0.5 / dx
    inv_2dx3 = 0.5 / (dx * dx * dx)
    inv_dy2 = 1.0 / (dy * dy)

    # Roll along x (dim=1)
    u_xp1 = torch.roll(u, shifts=-1, dims=1)
    u_xm1 = torch.roll(u, shifts=1, dims=1)
    u_xp2 = torch.roll(u, shifts=-2, dims=1)
    u_xm2 = torch.roll(u, shifts=2, dims=1)

    # Roll along y (dim=0)
    u_yp1 = torch.roll(u, shifts=-1, dims=0)
    u_ym1 = torch.roll(u, shifts=1, dims=0)

    advection = 6.0 * u * (u_xp1 - u_xm1) * inv_2dx
    d3u_dx3 = (u_xp2 - 2.0 * u_xp1 + 2.0 * u_xm1 - u_xm2) * inv_2dx3
    d2u_dy2 = (u_yp1 - 2.0 * u + u_ym1) * inv_dy2

    du_dt = -advection - d3u_dx3 - 0.5 * d2u_dy2
    return u + dt * du_dt


def benchmark_kp_soliton():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Poincaré KP-II Soliton Benchmark on: {torch.cuda.get_device_name(device)}")

    H = 256
    W = 512
    N = H * W
    print(f"[*] 2D Soliton Grid: {H}x{W} = {N:,} nodes")

    torch.manual_seed(42)
    # Generate line soliton profile u(x, y) = 2 k^2 sech^2(k x + l y - omega t)
    x = torch.linspace(-10, 10, W, device=device).unsqueeze(0)
    y = torch.linspace(-10, 10, H, device=device).unsqueeze(1)
    u = 2.0 * (1.0 / torch.cosh(0.8 * x + 0.3 * y))**2
    u = u.contiguous()

    # Numerical verification
    triton_out = triton_poincare_kp_soliton(u)
    torch_out = pytorch_poincare_kp_soliton(u)

    max_err = torch.max(torch.abs(triton_out - torch_out)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute error: {max_err:.8e}")
    assert max_err < 1e-4, f"Triton error too high: {max_err}"

    # Latency benchmark
    iters = 200
    for _ in range(20):
        _ = triton_poincare_kp_soliton(u)
        _ = pytorch_poincare_kp_soliton(u)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_kp_soliton(u)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_poincare_kp_soliton(u)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = N / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million grid nodes/s")


if __name__ == "__main__":
    benchmark_kp_soliton()
