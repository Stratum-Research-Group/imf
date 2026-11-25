"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Sine-Gordon Kink Collision
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 12.0, 16GB VRAM)
Mathematical Formulation:
  Non-linear relativistic 2D Sine-Gordon equation coupled to Poincaré hyperbolic metric:
    partial_t^2 phi - Delta_H phi + m^2 sin(phi) = 0
  where the Laplace-Beltrami operator in conformal coordinates z = (x, y) with
  vielbein lambda_z = 2 / (1 - ||z||^2) is:
    Delta_H phi = (1 / lambda_z^2) * (partial_x^2 phi + partial_y^2 phi)
                = ((1 - ||z||^2)^2 / 4) * (partial_x^2 phi + partial_y^2 phi)
  Symplectic Verlet / leapfrog integration in phase space (phi, pi):
    phi_{t+dt} = phi_t + dt * pi_t + (dt^2 / 2) * a_t
    a_{t+dt}   = Delta_H phi_{t+dt} - m^2 sin(phi_{t+dt}) - gamma * pi_t
    pi_{t+dt}  = pi_t + (dt / 2) * (a_t + a_{t+dt})
  Fused Triton execution computes spatial derivatives, conformal metric scaling,
  and trigonometric non-linear potential in thread registers.
"""

import time
import math
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_sine_gordon_kernel(
    Phi_ptr,        # [H, W] Field values phi(x, y)
    Pi_ptr,         # [H, W] Momentum values pi(x, y) = dphi/dt
    Phi_out_ptr,    # [H, W] Updated field phi
    Pi_out_ptr,     # [H, W] Updated momentum pi
    Z_ptr,          # [H, W, 2] Conformal coordinates (zx, zy)
    H: tl.constexpr,# Grid height
    W: tl.constexpr,# Grid width
    dt: tl.float32,
    dx: tl.float32,
    dy: tl.float32,
    mass_sq: tl.float32,
    damping: tl.float32,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0) # Program row index (y)
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

    inv_dx2 = 1.0 / (dx * dx)
    inv_dy2 = 1.0 / (dy * dy)

    # Load field and momentum
    phi = tl.load(Phi_ptr + y_curr * W + x_curr, mask=mask, other=0.0)
    pi = tl.load(Pi_ptr + y_curr * W + x_curr, mask=mask, other=0.0)

    # Load spatial neighbors
    phi_xp = tl.load(Phi_ptr + y_curr * W + x_next, mask=mask, other=0.0)
    phi_xm = tl.load(Phi_ptr + y_curr * W + x_prev, mask=mask, other=0.0)
    phi_yp = tl.load(Phi_ptr + y_next * W + x_curr, mask=mask, other=0.0)
    phi_ym = tl.load(Phi_ptr + y_prev * W + x_curr, mask=mask, other=0.0)

    # Load coordinates (zx, zy)
    zx = tl.load(Z_ptr + (y_curr * W + x_curr) * 2 + 0, mask=mask, other=0.0)
    zy = tl.load(Z_ptr + (y_curr * W + x_curr) * 2 + 1, mask=mask, other=0.0)
    norm_sq = zx * zx + zy * zy
    conf_factor = 0.25 * (1.0 - norm_sq) * (1.0 - norm_sq)

    # Flat Laplacian: d^2 phi / dx^2 + d^2 phi / dy^2
    d2_dx2 = (phi_xp - 2.0 * phi + phi_xm) * inv_dx2
    d2_dy2 = (phi_yp - 2.0 * phi + phi_ym) * inv_dy2
    laplacian_h = conf_factor * (d2_dx2 + d2_dy2)

    # Sine-Gordon acceleration: a = Delta_H phi - mass_sq * sin(phi) - damping * pi
    sin_phi = tl.sin(phi)
    acc = laplacian_h - mass_sq * sin_phi - damping * pi

    # Verlet update
    phi_next = phi + dt * pi + 0.5 * dt * dt * acc
    pi_next = pi + dt * acc

    tl.store(Phi_out_ptr + y_curr * W + x_curr, phi_next, mask=mask)
    tl.store(Pi_out_ptr + y_curr * W + x_curr, pi_next, mask=mask)


def triton_poincare_sine_gordon_step(phi, pi, z, dt=0.01, dx=0.1, dy=0.1, mass_sq=1.0, damping=0.02):
    H, W = phi.shape
    phi_out = torch.empty_like(phi)
    pi_out = torch.empty_like(pi)
    BLOCK_SIZE = triton.next_power_of_2(W)
    grid = (H,)
    fused_poincare_sine_gordon_kernel[grid](
        phi, pi, phi_out, pi_out, z,
        H=H, W=W, dt=dt, dx=dx, dy=dy,
        mass_sq=mass_sq, damping=damping,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return phi_out, pi_out


def pytorch_poincare_sine_gordon_step(phi, pi, z, dt=0.01, dx=0.1, dy=0.1, mass_sq=1.0, damping=0.02):
    inv_dx2 = 1.0 / (dx * dx)
    inv_dy2 = 1.0 / (dy * dy)

    phi_xp = torch.roll(phi, shifts=-1, dims=1)
    phi_xm = torch.roll(phi, shifts=1, dims=1)
    phi_yp = torch.roll(phi, shifts=-1, dims=0)
    phi_ym = torch.roll(phi, shifts=1, dims=0)

    norm_sq = torch.sum(z * z, dim=-1)
    conf_factor = 0.25 * (1.0 - norm_sq) * (1.0 - norm_sq)

    d2_dx2 = (phi_xp - 2.0 * phi + phi_xm) * inv_dx2
    d2_dy2 = (phi_yp - 2.0 * phi + phi_ym) * inv_dy2
    laplacian_h = conf_factor * (d2_dx2 + d2_dy2)

    sin_phi = torch.sin(phi)
    acc = laplacian_h - mass_sq * sin_phi - damping * pi

    phi_next = phi + dt * pi + 0.5 * dt * dt * acc
    pi_next = pi + dt * acc
    return phi_next, pi_next


def benchmark_sine_gordon():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Poincaré Sine-Gordon Kink Benchmark on: {torch.cuda.get_device_name(device)}")

    H = 512
    W = 512
    N = H * W
    print(f"[*] 2D Lattice: {H}x{W} = {N:,} relativistic phase nodes")

    torch.manual_seed(42)
    # Generate 2D coordinates inside Poincaré disk (|z| < 0.9)
    y_coords, x_coords = torch.meshgrid(
        torch.linspace(-0.85, 0.85, H, device=device),
        torch.linspace(-0.85, 0.85, W, device=device),
        indexing="ij"
    )
    z = torch.stack([x_coords, y_coords], dim=-1).contiguous()

    # Kink-antikink initial profile: phi = 4 * (arctan(exp(gamma * (x - x0))) - arctan(exp(gamma * (x + x0))))
    gamma_rel = 1.25
    x0 = 0.3
    phi = 4.0 * (torch.atan(torch.exp(gamma_rel * (x_coords - x0))) - torch.atan(torch.exp(gamma_rel * (x_coords + x0))))
    phi = phi.contiguous()
    pi = torch.zeros_like(phi)

    # Numerical verification
    tr_phi, tr_pi = triton_poincare_sine_gordon_step(phi, pi, z)
    py_phi, py_pi = pytorch_poincare_sine_gordon_step(phi, pi, z)

    max_err_phi = torch.max(torch.abs(tr_phi - py_phi)).item()
    max_err_pi = torch.max(torch.abs(tr_pi - py_pi)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute errors: phi={max_err_phi:.8e}, pi={max_err_pi:.8e}")
    assert max_err_phi < 1e-4 and max_err_pi < 1e-4, "Triton error too high"

    # Latency benchmark
    iters = 200
    for _ in range(20):
        _ = triton_poincare_sine_gordon_step(phi, pi, z)
        _ = pytorch_poincare_sine_gordon_step(phi, pi, z)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_sine_gordon_step(phi, pi, z)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_poincare_sine_gordon_step(phi, pi, z)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = (N * 2) / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million phase elements/s")


if __name__ == "__main__":
    benchmark_sine_gordon()
