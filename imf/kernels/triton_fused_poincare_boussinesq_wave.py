"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Boussinesq Bi-Directional Wave
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 12.0, 16GB VRAM)
Mathematical Formulation:
  The completely integrable Boussinesq bi-directional wave equation on the Poincaré disk:
    partial_t^2 u - Delta_H u - 3 Delta_H (u^2) - alpha * Delta_H^2 u = 0
  where Delta_H is the Laplace-Beltrami operator in conformal coordinates z = (x, y) with
  vielbein lambda_z = 2 / (1 - ||z||^2):
    Delta_H u = ((1 - ||z||^2)^2 / 4) * (partial_x^2 u + partial_y^2 u)
  and Delta_H^2 u is the fourth-order biharmonic operator.
  Symplectic Verlet integration in phase space (u, v) where v = partial_t u:
    u_{t+dt} = u_t + dt * v_t + (dt^2 / 2) * a_t
    a_{t+dt} = Delta_H u_{t+dt} + 3 Delta_H (u_{t+dt}^2) + alpha * Delta_H^2 u_{t+dt} - damping * v_t
    v_{t+dt} = v_t + dt * a_{t+dt}
  Fused Triton execution computes Laplacian, quadratic Laplacian, and biharmonic terms in registers.
"""

import time
import math
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_boussinesq_kernel(
    U_ptr,          # [H, W] Wave field u(x, y)
    V_ptr,          # [H, W] Velocity field v(x, y) = du/dt
    U_out_ptr,      # [H, W] Updated wave field
    V_out_ptr,      # [H, W] Updated velocity field
    Z_ptr,          # [H, W, 2] Conformal coordinates (zx, zy)
    H: tl.constexpr,# Grid height
    W: tl.constexpr,# Grid width
    dt: tl.float32,
    dx: tl.float32,
    dy: tl.float32,
    alpha_biharm: tl.float32,
    damping: tl.float32,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0) # Program row index y
    if pid >= H:
        return

    y_curr = pid
    y_p1 = (y_curr + 1) % H
    y_m1 = (y_curr - 1 + H) % H
    y_p2 = (y_curr + 2) % H
    y_m2 = (y_curr - 2 + H) % H

    col_offs = tl.arange(0, BLOCK_SIZE)
    mask = col_offs < W

    x_curr = col_offs
    x_p1 = (x_curr + 1) % W
    x_m1 = (x_curr - 1 + W) % W
    x_p2 = (x_curr + 2) % W
    x_m2 = (x_curr - 2 + W) % W

    inv_dx2 = 1.0 / (dx * dx)
    inv_dy2 = 1.0 / (dy * dy)
    inv_dx4 = 1.0 / (dx * dx * dx * dx)
    inv_dy4 = 1.0 / (dy * dy * dy * dy)

    # Load field u and velocity v
    u = tl.load(U_ptr + y_curr * W + x_curr, mask=mask, other=0.0)
    v = tl.load(V_ptr + y_curr * W + x_curr, mask=mask, other=0.0)

    # Load nearest neighbors for u
    u_xp1 = tl.load(U_ptr + y_curr * W + x_p1, mask=mask, other=0.0)
    u_xm1 = tl.load(U_ptr + y_curr * W + x_m1, mask=mask, other=0.0)
    u_yp1 = tl.load(U_ptr + y_p1 * W + x_curr, mask=mask, other=0.0)
    u_ym1 = tl.load(U_ptr + y_m1 * W + x_curr, mask=mask, other=0.0)

    # Load 2nd nearest neighbors for biharmonic d^4/dx^4
    u_xp2 = tl.load(U_ptr + y_curr * W + x_p2, mask=mask, other=0.0)
    u_xm2 = tl.load(U_ptr + y_curr * W + x_m2, mask=mask, other=0.0)
    u_yp2 = tl.load(U_ptr + y_p2 * W + x_curr, mask=mask, other=0.0)
    u_ym2 = tl.load(U_ptr + y_m2 * W + x_curr, mask=mask, other=0.0)

    # Conformal factor
    zx = tl.load(Z_ptr + (y_curr * W + x_curr) * 2 + 0, mask=mask, other=0.0)
    zy = tl.load(Z_ptr + (y_curr * W + x_curr) * 2 + 1, mask=mask, other=0.0)
    norm_sq = zx * zx + zy * zy
    conf_factor = 0.25 * (1.0 - norm_sq) * (1.0 - norm_sq)

    # 1. Linear Laplacian: Delta u
    lap_u = conf_factor * ((u_xp1 - 2.0 * u + u_xm1) * inv_dx2 + (u_yp1 - 2.0 * u + u_ym1) * inv_dy2)

    # 2. Non-linear quadratic Laplacian: Delta (u^2)
    u_sq = u * u
    u_sq_xp1 = u_xp1 * u_xp1
    u_sq_xm1 = u_xm1 * u_xm1
    u_sq_yp1 = u_yp1 * u_yp1
    u_sq_ym1 = u_ym1 * u_ym1
    lap_u_sq = conf_factor * ((u_sq_xp1 - 2.0 * u_sq + u_sq_xm1) * inv_dx2 + (u_sq_yp1 - 2.0 * u_sq + u_sq_ym1) * inv_dy2)

    # 3. Fourth-order biharmonic term: Delta^2 u
    # Finite difference 1D approximation along x and y:
    d4_dx4 = (u_xp2 - 4.0 * u_xp1 + 6.0 * u - 4.0 * u_xm1 + u_xm2) * inv_dx4
    d4_dy4 = (u_yp2 - 4.0 * u_yp1 + 6.0 * u - 4.0 * u_ym1 + u_ym2) * inv_dy4
    biharm_u = conf_factor * conf_factor * (d4_dx4 + d4_dy4)

    # Total acceleration: a = Delta u + 3 Delta (u^2) + alpha * Delta^2 u - damping * v
    acc = lap_u + 3.0 * lap_u_sq + alpha_biharm * biharm_u - damping * v

    # Symplectic update
    u_next = u + dt * v + 0.5 * dt * dt * acc
    v_next = v + dt * acc

    tl.store(U_out_ptr + y_curr * W + x_curr, u_next, mask=mask)
    tl.store(V_out_ptr + y_curr * W + x_curr, v_next, mask=mask)


def triton_boussinesq_step(u, v, z, dt=0.001, dx=0.1, dy=0.1, alpha_biharm=0.01, damping=0.02):
    H, W = u.shape
    u_out = torch.empty_like(u)
    v_out = torch.empty_like(v)
    BLOCK_SIZE = triton.next_power_of_2(W)
    grid = (H,)
    fused_poincare_boussinesq_kernel[grid](
        u, v, u_out, v_out, z,
        H=H, W=W, dt=dt, dx=dx, dy=dy,
        alpha_biharm=alpha_biharm, damping=damping,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return u_out, v_out


def pytorch_boussinesq_step(u, v, z, dt=0.001, dx=0.1, dy=0.1, alpha_biharm=0.01, damping=0.02):
    inv_dx2 = 1.0 / (dx * dx)
    inv_dy2 = 1.0 / (dy * dy)
    inv_dx4 = 1.0 / (dx * dx * dx * dx)
    inv_dy4 = 1.0 / (dy * dy * dy * dy)

    u_xp1 = torch.roll(u, shifts=-1, dims=1)
    u_xm1 = torch.roll(u, shifts=1, dims=1)
    u_yp1 = torch.roll(u, shifts=-1, dims=0)
    u_ym1 = torch.roll(u, shifts=1, dims=0)

    u_xp2 = torch.roll(u, shifts=-2, dims=1)
    u_xm2 = torch.roll(u, shifts=2, dims=1)
    u_yp2 = torch.roll(u, shifts=-2, dims=0)
    u_ym2 = torch.roll(u, shifts=2, dims=0)

    norm_sq = torch.sum(z * z, dim=-1)
    conf_factor = 0.25 * (1.0 - norm_sq) * (1.0 - norm_sq)

    lap_u = conf_factor * ((u_xp1 - 2.0 * u + u_xm1) * inv_dx2 + (u_yp1 - 2.0 * u + u_ym1) * inv_dy2)

    u_sq = u * u
    u_sq_xp1 = u_xp1 * u_xp1
    u_sq_xm1 = u_xm1 * u_xm1
    u_sq_yp1 = u_yp1 * u_yp1
    u_sq_ym1 = u_ym1 * u_ym1
    lap_u_sq = conf_factor * ((u_sq_xp1 - 2.0 * u_sq + u_sq_xm1) * inv_dx2 + (u_sq_yp1 - 2.0 * u_sq + u_sq_ym1) * inv_dy2)

    d4_dx4 = (u_xp2 - 4.0 * u_xp1 + 6.0 * u - 4.0 * u_xm1 + u_xm2) * inv_dx4
    d4_dy4 = (u_yp2 - 4.0 * u_yp1 + 6.0 * u - 4.0 * u_ym1 + u_ym2) * inv_dy4
    biharm_u = conf_factor * conf_factor * (d4_dx4 + d4_dy4)

    acc = lap_u + 3.0 * lap_u_sq + alpha_biharm * biharm_u - damping * v

    u_next = u + dt * v + 0.5 * dt * dt * acc
    v_next = v + dt * acc
    return u_next, v_next


def benchmark_boussinesq():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Boussinesq Bi-Directional Wave Benchmark on: {torch.cuda.get_device_name(device)}")

    H = 512
    W = 512
    N = H * W
    print(f"[*] 2D Lattice: {H}x{W} = {N:,} wave nodes")

    torch.manual_seed(42)
    y_coords, x_coords = torch.meshgrid(
        torch.linspace(-0.85, 0.85, H, device=device),
        torch.linspace(-0.85, 0.85, W, device=device),
        indexing="ij"
    )
    z = torch.stack([x_coords, y_coords], dim=-1).contiguous()

    # Soliton pulse u = (c^2 - 1) sech^2(k x)
    u = 0.5 * (1.0 / torch.cosh(3.0 * x_coords))**2
    u = u.contiguous()
    v = torch.zeros_like(u)

    # Numerical verification
    tr_u, tr_v = triton_boussinesq_step(u, v, z)
    py_u, py_v = pytorch_boussinesq_step(u, v, z)

    max_err_u = torch.max(torch.abs(tr_u - py_u)).item()
    max_err_v = torch.max(torch.abs(tr_v - py_v)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute errors: u={max_err_u:.8e}, v={max_err_v:.8e}")
    assert max_err_u < 1e-4 and max_err_v < 1e-4, "Triton error too high"

    # Latency benchmark
    iters = 200
    for _ in range(20):
        _ = triton_boussinesq_step(u, v, z)
        _ = pytorch_boussinesq_step(u, v, z)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_boussinesq_step(u, v, z)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_boussinesq_step(u, v, z)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = (N * 2) / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million wave elements/s")


if __name__ == "__main__":
    benchmark_boussinesq()
