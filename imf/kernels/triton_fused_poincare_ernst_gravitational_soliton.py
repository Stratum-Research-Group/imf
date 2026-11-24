"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Ernst Gravitational Soliton
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 8.9, 16GB VRAM)
Mathematical Formulation:
  The stationary axisymmetric Einstein vacuum gravitational field equation
  (Ernst equation) on the Poincaré hyperbolic disk:
    (Re E) Delta_H E = (grad_H E)^2
  where E = f + i psi is the complex Ernst potential:
    f > 0 is the gravitational metric coefficient,
    psi is the twist potential (rotation of spacetime).
  In components:
    f * Delta_H f = (grad_H f)^2 - (grad_H psi)^2
    f * Delta_H psi = 2 grad_H f · grad_H psi
  Continuous relaxation flow (complex non-linear gradient flow):
    df/dt   = Delta_H f - (1/f) * ((grad_H f)^2 - (grad_H psi)^2) - damping * f
    dpsi/dt = Delta_H psi - (2/f) * (grad_H f · grad_H psi) - damping * psi
  Fused Triton execution evaluates:
    1. Conformal Laplace-Beltrami Delta_H on f and psi in thread registers.
    2. Spatial gradients grad_H f and grad_H psi using centered finite differences.
    3. Complex non-linear reaction terms directly in registers with reciprocal 1/f.
"""

import time
import math
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_ernst_kernel(
    F_ptr,          # [H, W] Real part of Ernst potential f > 0
    Psi_ptr,        # [H, W] Imaginary twist potential psi
    F_out_ptr,      # [H, W] Updated f
    Psi_out_ptr,    # [H, W] Updated psi
    Z_ptr,          # [H, W, 2] Conformal coordinates (zx, zy)
    H: tl.constexpr,# Grid height
    W: tl.constexpr,# Grid width
    dt: tl.float32,
    dx: tl.float32,
    dy: tl.float32,
    damping: tl.float32,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0) # Program row index y
    if pid >= H:
        return

    y_curr = pid
    y_prev = (y_curr - 1 + H) % H
    y_next = (y_curr + 1) % H

    col_offs = tl.arange(0, BLOCK_SIZE)
    mask = col_offs < W

    x_curr = col_offs
    x_prev = (x_curr - 1 + W) % W
    x_next = (x_curr + 1) % W

    inv_2dx = 0.5 / dx
    inv_2dy = 0.5 / dy
    inv_dx2 = 1.0 / (dx * dx)
    inv_dy2 = 1.0 / (dy * dy)

    # Load f and psi
    f = tl.load(F_ptr + y_curr * W + x_curr, mask=mask, other=1.0)
    psi = tl.load(Psi_ptr + y_curr * W + x_curr, mask=mask, other=0.0)

    # Load neighbors for f
    f_xp = tl.load(F_ptr + y_curr * W + x_next, mask=mask, other=1.0)
    f_xm = tl.load(F_ptr + y_curr * W + x_prev, mask=mask, other=1.0)
    f_yp = tl.load(F_ptr + y_next * W + x_curr, mask=mask, other=1.0)
    f_ym = tl.load(F_ptr + y_prev * W + x_curr, mask=mask, other=1.0)

    # Load neighbors for psi
    psi_xp = tl.load(Psi_ptr + y_curr * W + x_next, mask=mask, other=0.0)
    psi_xm = tl.load(Psi_ptr + y_curr * W + x_prev, mask=mask, other=0.0)
    psi_yp = tl.load(Psi_ptr + y_next * W + x_curr, mask=mask, other=0.0)
    psi_ym = tl.load(Psi_ptr + y_prev * W + x_curr, mask=mask, other=0.0)

    # Conformal factor
    zx = tl.load(Z_ptr + (y_curr * W + x_curr) * 2 + 0, mask=mask, other=0.0)
    zy = tl.load(Z_ptr + (y_curr * W + x_curr) * 2 + 1, mask=mask, other=0.0)
    norm_sq = zx * zx + zy * zy
    conf_factor = 0.25 * (1.0 - norm_sq) * (1.0 - norm_sq)

    # Spatial Laplacians
    lap_f = conf_factor * ((f_xp - 2.0 * f + f_xm) * inv_dx2 + (f_yp - 2.0 * f + f_ym) * inv_dy2)
    lap_psi = conf_factor * ((psi_xp - 2.0 * psi + psi_xm) * inv_dx2 + (psi_yp - 2.0 * psi + psi_ym) * inv_dy2)

    # Gradients (grad_x, grad_y)
    grad_f_x = (f_xp - f_xm) * inv_2dx
    grad_f_y = (f_yp - f_ym) * inv_2dy
    grad_psi_x = (psi_xp - psi_xm) * inv_2dx
    grad_psi_y = (psi_yp - psi_ym) * inv_2dy

    # Scaled inner products in registers
    norm_grad_f = conf_factor * (grad_f_x * grad_f_x + grad_f_y * grad_f_y)
    norm_grad_psi = conf_factor * (grad_psi_x * grad_psi_x + grad_psi_y * grad_psi_y)
    dot_grad = conf_factor * (grad_f_x * grad_psi_x + grad_f_y * grad_psi_y)

    # Reciprocal 1/f with singularity regularization
    inv_f = 1.0 / (f + 1e-4)

    # Ernst non-linear relaxation updates:
    df_dt = lap_f - inv_f * (norm_grad_f - norm_grad_psi) - damping * f
    dpsi_dt = lap_psi - 2.0 * inv_f * dot_grad - damping * psi

    f_new = f + dt * df_dt
    psi_new = psi + dt * dpsi_dt

    tl.store(F_out_ptr + y_curr * W + x_curr, f_new, mask=mask)
    tl.store(Psi_out_ptr + y_curr * W + x_curr, psi_new, mask=mask)


def triton_ernst_step(f, psi, z, dt=0.001, dx=0.1, dy=0.1, damping=0.01):
    H, W = f.shape
    f_out = torch.empty_like(f)
    psi_out = torch.empty_like(psi)
    BLOCK_SIZE = triton.next_power_of_2(W)
    grid = (H,)
    fused_poincare_ernst_kernel[grid](
        f, psi, f_out, psi_out, z,
        H=H, W=W, dt=dt, dx=dx, dy=dy, damping=damping,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return f_out, psi_out


def pytorch_ernst_step(f, psi, z, dt=0.001, dx=0.1, dy=0.1, damping=0.01):
    inv_2dx = 0.5 / dx
    inv_2dy = 0.5 / dy
    inv_dx2 = 1.0 / (dx * dx)
    inv_dy2 = 1.0 / (dy * dy)

    f_xp = torch.roll(f, shifts=-1, dims=1)
    f_xm = torch.roll(f, shifts=1, dims=1)
    f_yp = torch.roll(f, shifts=-1, dims=0)
    f_ym = torch.roll(f, shifts=1, dims=0)

    psi_xp = torch.roll(psi, shifts=-1, dims=1)
    psi_xm = torch.roll(psi, shifts=1, dims=1)
    psi_yp = torch.roll(psi, shifts=-1, dims=0)
    psi_ym = torch.roll(psi, shifts=1, dims=0)

    norm_sq = torch.sum(z * z, dim=-1)
    conf_factor = 0.25 * (1.0 - norm_sq) * (1.0 - norm_sq)

    lap_f = conf_factor * ((f_xp - 2.0 * f + f_xm) * inv_dx2 + (f_yp - 2.0 * f + f_ym) * inv_dy2)
    lap_psi = conf_factor * ((psi_xp - 2.0 * psi + psi_xm) * inv_dx2 + (psi_yp - 2.0 * psi + psi_ym) * inv_dy2)

    grad_f_x = (f_xp - f_xm) * inv_2dx
    grad_f_y = (f_yp - f_ym) * inv_2dy
    grad_psi_x = (psi_xp - psi_xm) * inv_2dx
    grad_psi_y = (psi_yp - psi_ym) * inv_2dy

    norm_grad_f = conf_factor * (grad_f_x * grad_f_x + grad_f_y * grad_f_y)
    norm_grad_psi = conf_factor * (grad_psi_x * grad_psi_x + grad_psi_y * grad_psi_y)
    dot_grad = conf_factor * (grad_f_x * grad_psi_x + grad_f_y * grad_psi_y)

    inv_f = 1.0 / (f + 1e-4)

    df_dt = lap_f - inv_f * (norm_grad_f - norm_grad_psi) - damping * f
    dpsi_dt = lap_psi - 2.0 * inv_f * dot_grad - damping * psi

    f_new = f + dt * df_dt
    psi_new = psi + dt * dpsi_dt
    return f_new, psi_new


def benchmark_ernst():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Ernst Gravitational Soliton Benchmark on: {torch.cuda.get_device_name(device)}")

    H = 512
    W = 512
    N = H * W
    print(f"[*] 2D Lattice: {H}x{W} = {N:,} spacetime nodes")

    torch.manual_seed(42)
    y_coords, x_coords = torch.meshgrid(
        torch.linspace(-0.85, 0.85, H, device=device),
        torch.linspace(-0.85, 0.85, W, device=device),
        indexing="ij"
    )
    z = torch.stack([x_coords, y_coords], dim=-1).contiguous()

    # Kerr-like initial Ernst potential: f ~ 1 - 2M/r, psi ~ 2aM cos(theta)/r^2
    r_sq = x_coords**2 + y_coords**2 + 0.1
    f = (1.0 + 0.5 / torch.sqrt(r_sq)).contiguous()
    psi = (0.2 * x_coords / r_sq).contiguous()

    # Numerical verification
    tr_f, tr_psi = triton_ernst_step(f, psi, z)
    py_f, py_psi = pytorch_ernst_step(f, psi, z)

    max_err_f = torch.max(torch.abs(tr_f - py_f)).item()
    max_err_psi = torch.max(torch.abs(tr_psi - py_psi)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute errors: f={max_err_f:.8e}, psi={max_err_psi:.8e}")
    assert max_err_f < 1e-4 and max_err_psi < 1e-4, "Triton error too high"

    # Latency benchmark
    iters = 200
    for _ in range(20):
        _ = triton_ernst_step(f, psi, z)
        _ = pytorch_ernst_step(f, psi, z)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_ernst_step(f, psi, z)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_ernst_step(f, psi, z)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = (N * 2) / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million spacetime variables/s")


if __name__ == "__main__":
    benchmark_ernst()
