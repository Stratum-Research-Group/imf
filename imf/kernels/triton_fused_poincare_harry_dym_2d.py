"""
Physical Workstation Triton Kernel: Fused Poincaré Harry Dym (2+1)D Reciprocal System (Cycle 221)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 8.9), 16GB VRAM.

The (2+1)D Harry Dym equation is an integrable hodograph-reciprocal system describing cuspon singular dynamics:
    u_t = u^3 u_{xxx} + 3 u^2 u_x v_y
    v_x = u_y
In the Poincaré metric ds^2 = y^{-2}(dx^2 + dy^2), the third-order dispersion is scaled by y^{-3},
regularizing cuspon singularities near the horizon boundary.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_poincare_harry_dym_2d_kernel(
    U_ptr,         # [H, W] field u
    V_ptr,         # [H, W] auxiliary velocity v
    Out_U_ptr,     # [H, W]
    Y_ptr,         # [H] hyperbolic coordinate
    dt: tl.constexpr,
    H: tl.constexpr,
    W: tl.constexpr,
    BLOCK_M: tl.constexpr,
):
    pid = tl.program_id(0)
    total_nodes = H * W
    offset = pid * BLOCK_M + tl.arange(0, BLOCK_M)
    mask = offset < total_nodes

    row = offset // W
    col = offset % W

    # Hyperbolic metric factor
    y = tl.load(Y_ptr + row, mask=mask, other=1.0)
    metric_scale = 1.0 / (y * y * y + 1e-5)

    col_lf = tl.where(col > 0, col - 1, col)
    col_rt = tl.where(col < W - 1, col + 1, col)
    col_lf2 = tl.where(col > 1, col - 2, col_lf)
    col_rt2 = tl.where(col < W - 2, col + 2, col_rt)

    row_up = tl.where(row > 0, row - 1, row)
    row_dn = tl.where(row < H - 1, row + 1, row)

    idx_curr = row * W + col
    u = tl.load(U_ptr + idx_curr, mask=mask, other=0.0)

    # 1st derivatives: u_x and v_y
    u_rt = tl.load(U_ptr + row * W + col_rt, mask=mask, other=0.0)
    u_lf = tl.load(U_ptr + row * W + col_lf, mask=mask, other=0.0)
    ux = 0.5 * (u_rt - u_lf)

    v_dn = tl.load(V_ptr + row_dn * W + col, mask=mask, other=0.0)
    v_up = tl.load(V_ptr + row_up * W + col, mask=mask, other=0.0)
    vy = 0.5 * (v_dn - v_up)

    # 3rd derivative: u_{xxx}
    u_rt2 = tl.load(U_ptr + row * W + col_rt2, mask=mask, other=0.0)
    u_lf2 = tl.load(U_ptr + row * W + col_lf2, mask=mask, other=0.0)
    uxxx = 0.5 * (u_rt2 - 2.0 * u_rt + 2.0 * u_lf - u_lf2)

    # Harry Dym (2+1)D: u_t = (u^3 * uxxx + 3 * u^2 * ux * vy) * metric_scale
    u_cube = u * u * u
    u_sq = u * u
    rhs = (u_cube * uxxx + 3.0 * u_sq * ux * vy) * metric_scale
    new_u = u + dt * rhs

    tl.store(Out_U_ptr + idx_curr, new_u, mask=mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")
    H, W = 256, 256
    total_nodes = H * W
    dt = 0.0002

    torch.manual_seed(42)
    u = torch.randn(H, W, device=device, dtype=torch.float32) * 0.1 + 0.5
    v = torch.randn(H, W, device=device, dtype=torch.float32) * 0.1
    y = torch.linspace(0.8, 2.5, H, device=device, dtype=torch.float32)

    def ref_hd_2d(u, v, y, dt):
        metric_scale = 1.0 / (y.view(H, 1) ** 3 + 1e-5)
        u_pad = torch.nn.functional.pad(u.unsqueeze(0).unsqueeze(0), (2, 2, 0, 0), mode='replicate')[0, 0]
        v_pad = torch.nn.functional.pad(v.unsqueeze(0).unsqueeze(0), (0, 0, 1, 1), mode='replicate')[0, 0]

        ux = 0.5 * (u_pad[:, 3:-1] - u_pad[:, 1:-3])
        uxxx = 0.5 * (u_pad[:, 4:] - 2*u_pad[:, 3:-1] + 2*u_pad[:, 1:-3] - u_pad[:, :-4])
        vy = 0.5 * (v_pad[2:, :] - v_pad[:-2, :])

        rhs = ((u**3) * uxxx + 3.0 * (u**2) * ux * vy) * metric_scale
        return u + dt * rhs

    for _ in range(20):
        ref_out = ref_hd_2d(u, v, y, dt)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 100
    for _ in range(iters):
        ref_out = ref_hd_2d(u, v, y, dt)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out_u = torch.empty_like(u)
    BLOCK_M = 256
    grid = ((total_nodes + BLOCK_M - 1) // BLOCK_M,)

    for _ in range(20):
        fused_poincare_harry_dym_2d_kernel[grid](
            u, v, out_u, y, dt, H, W, BLOCK_M
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_poincare_harry_dym_2d_kernel[grid](
            u, v, out_u, y, dt, H, W, BLOCK_M
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    max_err = torch.max(torch.abs(out_u - ref_out)).item()
    speedup = ref_time / triton_time
    throughput = total_nodes / triton_time / 1e6

    print(f"=== Workstation Benchmark: Cycle 221 Poincaré Harry Dym (2+1)D Flow ===")
    print(f"Hardware: {torch.cuda.get_device_name(0)}")
    print(f"Grid size: {H}x{W} ({total_nodes} lattice nodes)")
    print(f"PyTorch baseline latency: {ref_time*1e6:.2f} us")
    print(f"Triton fused latency:     {triton_time*1e6:.2f} us")
    print(f"Speedup factor:           {speedup:.2f}x")
    print(f"Throughput:               {throughput:.2f} M nodes/s")
    print(f"Numerical Max Error:      {max_err:.2e}")
    assert max_err < 1e-4, f"Tolerance exceeded: {max_err}"
    print("PHYSICAL HARDWARE TEST PASSED")

if __name__ == "__main__":
    run_benchmark()
