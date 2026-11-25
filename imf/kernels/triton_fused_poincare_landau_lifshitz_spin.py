"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Landau-Lifshitz Spin Wave
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 12.0, 16GB VRAM)
Mathematical Formulation:
  The non-linear Landau-Lifshitz equation for classical anisotropic Heisenberg ferromagnetic spin chains:
    partial_t S = S x partial_x^2 S + S x (J_diag · S) - lambda * S x (S x partial_x^2 S)
  where S(x, t) in S^2 (|S| = 1), J_diag = diag(J_x, J_y, J_z) is the easy-axis/easy-plane anisotropy,
  and lambda is the Gilbert damping parameter.
  Fused Triton execution evaluates:
    1. Centered spatial finite difference laplacian d^2 S / dx^2
    2. Anisotropic Zeeman/crystalline field torque: S x (J_diag · S)
    3. Precession torque: S x d^2 S / dx^2
    4. Gilbert dissipation damping: -lambda * S x (precession torque)
    5. Unit sphere retraction: S_{new} <- S_{new} / |S_{new}|
"""

import time
import math
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_landau_lifshitz_kernel(
    S_ptr,          # [B, N, 3] Spin vector field S(x)
    Out_ptr,        # [B, N, 3] Updated spin vector field
    B: tl.constexpr,# Batch of independent spin chains
    N: tl.constexpr,# Spatial resolution (power of 2, e.g. 512)
    dt: tl.float32,
    dx: tl.float32,
    Jx: tl.float32,
    Jy: tl.float32,
    Jz: tl.float32,
    damping: tl.float32,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0) # Batch index b
    if pid >= B:
        return

    col_offs = tl.arange(0, BLOCK_SIZE)
    mask = col_offs < N

    inv_dx2 = 1.0 / (dx * dx)

    # Periodic neighbor indices
    x = col_offs
    x_p1 = (x + 1) % N
    x_m1 = (x - 1 + N) % N

    # Load S_i = (sx, sy, sz)
    sx = tl.load(S_ptr + (pid * N + x) * 3 + 0, mask=mask, other=0.0)
    sy = tl.load(S_ptr + (pid * N + x) * 3 + 1, mask=mask, other=0.0)
    sz = tl.load(S_ptr + (pid * N + x) * 3 + 2, mask=mask, other=1.0)

    # Load S_{i+1}
    sx_p = tl.load(S_ptr + (pid * N + x_p1) * 3 + 0, mask=mask, other=0.0)
    sy_p = tl.load(S_ptr + (pid * N + x_p1) * 3 + 1, mask=mask, other=0.0)
    sz_p = tl.load(S_ptr + (pid * N + x_p1) * 3 + 2, mask=mask, other=1.0)

    # Load S_{i-1}
    sx_m = tl.load(S_ptr + (pid * N + x_m1) * 3 + 0, mask=mask, other=0.0)
    sy_m = tl.load(S_ptr + (pid * N + x_m1) * 3 + 1, mask=mask, other=0.0)
    sz_m = tl.load(S_ptr + (pid * N + x_m1) * 3 + 2, mask=mask, other=1.0)

    # Spatial exchange field: B_exch = d^2 S / dx^2
    bx = (sx_p - 2.0 * sx + sx_m) * inv_dx2
    by = (sy_p - 2.0 * sy + sy_m) * inv_dx2
    bz = (sz_p - 2.0 * sz + sz_m) * inv_dx2

    # Total effective field: H_eff = B_exch + J_diag * S
    hx = bx + Jx * sx
    hy = by + Jy * sy
    hz = bz + Jz * sz

    # Precession torque = S x H_eff
    tx = sy * hz - sz * hy
    ty = sz * hx - sx * hz
    tz = sx * hy - sy * hx

    # Gilbert damping torque = S x torque
    dx_t = sy * tz - sz * ty
    dy_t = sz * tx - sx * tz
    dz_t = sx * ty - sy * tx

    # Total dS/dt = torque - damping * damping_torque
    ds_x = tx - damping * dx_t
    ds_y = ty - damping * dy_t
    ds_z = tz - damping * dz_t

    # Step update:
    s_next_x = sx + dt * ds_x
    s_next_y = sy + dt * ds_y
    s_next_z = sz + dt * ds_z

    # Renormalize to unit sphere |S| = 1
    norm = tl.sqrt(s_next_x * s_next_x + s_next_y * s_next_y + s_next_z * s_next_z + 1e-12)
    s_next_x = s_next_x / norm
    s_next_y = s_next_y / norm
    s_next_z = s_next_z / norm

    tl.store(Out_ptr + (pid * N + x) * 3 + 0, s_next_x, mask=mask)
    tl.store(Out_ptr + (pid * N + x) * 3 + 1, s_next_y, mask=mask)
    tl.store(Out_ptr + (pid * N + x) * 3 + 2, s_next_z, mask=mask)


def triton_landau_lifshitz_step(S, dt=0.001, dx=0.1, Jx=0.0, Jy=0.0, Jz=1.0, damping=0.02):
    B, N, _ = S.shape
    out = torch.empty_like(S)
    BLOCK_SIZE = triton.next_power_of_2(N)
    grid = (B,)
    fused_poincare_landau_lifshitz_kernel[grid](
        S, out,
        B=B, N=N, dt=dt, dx=dx, Jx=Jx, Jy=Jy, Jz=Jz, damping=damping,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out


def pytorch_landau_lifshitz_step(S, dt=0.001, dx=0.1, Jx=0.0, Jy=0.0, Jz=1.0, damping=0.02):
    inv_dx2 = 1.0 / (dx * dx)

    S_p = torch.roll(S, shifts=-1, dims=1)
    S_m = torch.roll(S, shifts=1, dims=1)

    B_exch = (S_p - 2.0 * S + S_m) * inv_dx2

    J_diag = torch.tensor([Jx, Jy, Jz], device=S.device, dtype=S.dtype)
    H_aniso = S * J_diag
    H_eff = B_exch + H_aniso

    torque = torch.cross(S, H_eff, dim=-1)
    damping_torque = torch.cross(S, torque, dim=-1)

    dS = torque - damping * damping_torque
    S_next = S + dt * dS
    norm = torch.norm(S_next, dim=-1, keepdim=True)
    return S_next / (norm + 1e-12)


def benchmark_landau_lifshitz():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Landau-Lifshitz Spin Wave Benchmark on: {torch.cuda.get_device_name(device)}")

    B = 1024
    N = 512
    total_spins = B * N
    print(f"[*] Scale: {B:,} chains x {N} spins = {total_spins:,} spin vectors ({total_spins * 3:,} components)")

    torch.manual_seed(42)
    S = torch.randn(B, N, 3, device=device)
    S[:, :, 2] += 2.0 # Ferromagnetic alignment
    S = S / torch.norm(S, dim=-1, keepdim=True)
    S = S.contiguous()

    # Numerical verification
    tr_S = triton_landau_lifshitz_step(S)
    py_S = pytorch_landau_lifshitz_step(S)

    max_err = torch.max(torch.abs(tr_S - py_S)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute error: {max_err:.8e}")
    assert max_err < 1e-5, f"Triton error too high: {max_err}"

    # Latency benchmark
    iters = 200
    for _ in range(20):
        _ = triton_landau_lifshitz_step(S)
        _ = pytorch_landau_lifshitz_step(S)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_landau_lifshitz_step(S)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_landau_lifshitz_step(S)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = (total_spins * 3) / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million spin elements/s")


if __name__ == "__main__":
    benchmark_landau_lifshitz()
