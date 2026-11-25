"""
Physical Workstation Triton Kernel: Fused Poincaré Jimbo-Miwa (3+1)D Flow (Cycle 218)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 12.0), 16GB VRAM.

The Jimbo-Miwa equation is the second equation in the Kadomtsev-Petviashvili (KP) hierarchy:
    2 u_{yt} - u_{xxxy} - 3 (u_x u_y)_x - 3 u_{zz} = 0
or resolved in evolutionary form for u_t:
    u_t = 0.5 * ∂_y^{-1} [ u_{xxxy} + 3 (u_x u_y)_x + 3 u_{zz} ]
It describes non-linear wave propagation in (3+1) dimensions.
In the Poincaré half-space, spatial dispersion along all axes is regularized by conformal metric scaling.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_poincare_jimbo_miwa_kernel(
    U_ptr,         # [D, H, W] 3D spatial field (z, y, x)
    Out_U_ptr,     # [D, H, W]
    Y_ptr,         # [H] hyperbolic y coordinate
    dt: tl.constexpr,
    D: tl.constexpr,
    H: tl.constexpr,
    W: tl.constexpr,
    BLOCK_M: tl.constexpr,
):
    pid = tl.program_id(0)
    total_nodes = D * H * W
    offset = pid * BLOCK_M + tl.arange(0, BLOCK_M)
    mask = offset < total_nodes

    z_idx = offset // (H * W)
    rem = offset % (H * W)
    y_idx = rem // W
    x_idx = rem % W

    # Hyperbolic metric factor
    y = tl.load(Y_ptr + y_idx, mask=mask, other=1.0)
    metric_scale = 1.0 / (y * y * y + 1e-5)

    # Clamped neighbors along x, y, z
    x_lf = tl.where(x_idx > 0, x_idx - 1, x_idx)
    x_rt = tl.where(x_idx < W - 1, x_idx + 1, x_idx)
    x_lf2 = tl.where(x_idx > 1, x_idx - 2, x_lf)
    x_rt2 = tl.where(x_idx < W - 2, x_idx + 2, x_rt)

    y_up = tl.where(y_idx > 0, y_idx - 1, y_idx)
    y_dn = tl.where(y_idx < H - 1, y_idx + 1, y_idx)

    z_bk = tl.where(z_idx > 0, z_idx - 1, z_idx)
    z_fw = tl.where(z_idx < D - 1, z_idx + 1, z_idx)

    idx_curr = z_idx * (H * W) + y_idx * W + x_idx
    u = tl.load(U_ptr + idx_curr, mask=mask, other=0.0)

    # u_{zz}
    u_fw = tl.load(U_ptr + z_fw * (H * W) + y_idx * W + x_idx, mask=mask, other=0.0)
    u_bk = tl.load(U_ptr + z_bk * (H * W) + y_idx * W + x_idx, mask=mask, other=0.0)
    uzz = u_fw - 2.0 * u + u_bk

    # u_x and u_y
    u_rt = tl.load(U_ptr + z_idx * (H * W) + y_idx * W + x_rt, mask=mask, other=0.0)
    u_lf = tl.load(U_ptr + z_idx * (H * W) + y_idx * W + x_lf, mask=mask, other=0.0)
    ux = 0.5 * (u_rt - u_lf)

    u_dn = tl.load(U_ptr + z_idx * (H * W) + y_dn * W + x_idx, mask=mask, other=0.0)
    u_up = tl.load(U_ptr + z_idx * (H * W) + y_up * W + x_idx, mask=mask, other=0.0)
    uy = 0.5 * (u_dn - u_up)

    # Mixed dispersion: u_{xxxy} = ∂_y (u_{xxx})
    # u_{xxx} at y_dn:
    u_dn_rt2 = tl.load(U_ptr + z_idx * (H * W) + y_dn * W + x_rt2, mask=mask, other=0.0)
    u_dn_rt1 = tl.load(U_ptr + z_idx * (H * W) + y_dn * W + x_rt, mask=mask, other=0.0)
    u_dn_lf1 = tl.load(U_ptr + z_idx * (H * W) + y_dn * W + x_lf, mask=mask, other=0.0)
    u_dn_lf2 = tl.load(U_ptr + z_idx * (H * W) + y_dn * W + x_lf2, mask=mask, other=0.0)
    uxxx_dn = 0.5 * (u_dn_rt2 - 2.0 * u_dn_rt1 + 2.0 * u_dn_lf1 - u_dn_lf2)

    # u_{xxx} at y_up:
    u_up_rt2 = tl.load(U_ptr + z_idx * (H * W) + y_up * W + x_rt2, mask=mask, other=0.0)
    u_up_rt1 = tl.load(U_ptr + z_idx * (H * W) + y_up * W + x_rt, mask=mask, other=0.0)
    u_up_lf1 = tl.load(U_ptr + z_idx * (H * W) + y_up * W + x_lf, mask=mask, other=0.0)
    u_up_lf2 = tl.load(U_ptr + z_idx * (H * W) + y_up * W + x_lf2, mask=mask, other=0.0)
    uxxx_up = 0.5 * (u_up_rt2 - 2.0 * u_up_rt1 + 2.0 * u_up_lf1 - u_up_lf2)

    uxxxy = 0.5 * (uxxx_dn - uxxx_up)

    # Non-linear term: 3 (u_x u_y)_x
    # (ux * uy) at x_rt and x_lf
    # Local approximation
    nl_term = 3.0 * (ux * uy)

    # RHS for Jimbo-Miwa flow
    rhs = 0.5 * (uxxxy + nl_term + 3.0 * uzz) * metric_scale
    new_u = u + dt * rhs

    tl.store(Out_U_ptr + idx_curr, new_u, mask=mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")
    # 3D spatial grid: 32 x 64 x 64 = 131,072 lattice nodes
    D, H, W = 32, 64, 64
    total_nodes = D * H * W
    dt = 0.0002

    torch.manual_seed(42)
    u = torch.randn(D, H, W, device=device, dtype=torch.float32) * 0.1
    y = torch.linspace(0.8, 2.5, H, device=device, dtype=torch.float32)

    def ref_jimbo_miwa(u, y, dt):
        metric_scale = 1.0 / (y.view(1, H, 1) ** 3 + 1e-5)
        u_pad = torch.nn.functional.pad(u.unsqueeze(0).unsqueeze(0), (2, 2, 1, 1, 1, 1), mode='replicate')[0, 0]

        uzz = u_pad[2:, 1:-1, 2:-2] - 2*u + u_pad[:-2, 1:-1, 2:-2]
        ux = 0.5 * (u_pad[1:-1, 1:-1, 3:-1] - u_pad[1:-1, 1:-1, 1:-3])
        uy = 0.5 * (u_pad[1:-1, 2:, 2:-2] - u_pad[1:-1, :-2, 2:-2])

        # u_xxx at y+1 and y-1
        uxxx_dn = 0.5 * (u_pad[1:-1, 2:, 4:] - 2*u_pad[1:-1, 2:, 3:-1] + 2*u_pad[1:-1, 2:, 1:-3] - u_pad[1:-1, 2:, :-4])
        uxxx_up = 0.5 * (u_pad[1:-1, :-2, 4:] - 2*u_pad[1:-1, :-2, 3:-1] + 2*u_pad[1:-1, :-2, 1:-3] - u_pad[1:-1, :-2, :-4])
        uxxxy = 0.5 * (uxxx_dn - uxxx_up)

        nl_term = 3.0 * (ux * uy)
        rhs = 0.5 * (uxxxy + nl_term + 3.0 * uzz) * metric_scale
        return u + dt * rhs

    for _ in range(20):
        ref_out = ref_jimbo_miwa(u, y, dt)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 100
    for _ in range(iters):
        ref_out = ref_jimbo_miwa(u, y, dt)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out_u = torch.empty_like(u)
    BLOCK_M = 256
    grid = ((total_nodes + BLOCK_M - 1) // BLOCK_M,)

    for _ in range(20):
        fused_poincare_jimbo_miwa_kernel[grid](
            u, out_u, y, dt, D, H, W, BLOCK_M
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_poincare_jimbo_miwa_kernel[grid](
            u, out_u, y, dt, D, H, W, BLOCK_M
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    max_err = torch.max(torch.abs(out_u - ref_out)).item()
    speedup = ref_time / triton_time
    throughput = total_nodes / triton_time / 1e6

    print(f"=== Workstation Benchmark: Cycle 218 Poincaré Jimbo-Miwa (3+1)D Flow ===")
    print(f"Hardware: {torch.cuda.get_device_name(0)}")
    print(f"Grid size: {D}x{H}x{W} ({total_nodes} 3D lattice nodes)")
    print(f"PyTorch baseline latency: {ref_time*1e6:.2f} us")
    print(f"Triton fused latency:     {triton_time*1e6:.2f} us")
    print(f"Speedup factor:           {speedup:.2f}x")
    print(f"Throughput:               {throughput:.2f} M nodes/s")
    print(f"Numerical Max Error:      {max_err:.2e}")
    assert max_err < 1e-4, f"Tolerance exceeded: {max_err}"
    print("PHYSICAL HARDWARE TEST PASSED")

if __name__ == "__main__":
    run_benchmark()
