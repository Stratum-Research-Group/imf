"""
Physical Workstation Triton Kernel: Fused Poincaré Boiti-Leon-Pempinelli (BLP) Integrable Flow (Cycle 216)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 12.0), 16GB VRAM.

The Boiti-Leon-Pempinelli (BLP) system is an integrable 2D extension of the sine-Gordon and KdV systems:
    u_t = u_{xxy} - 4 u^2 u_y - 2 u_x v
    v_x = (u^2)_y
It models nonlinear wave packets with cross-derivative dispersion. In Poincaré hyperbolic space H^2,
the metric factor y^{-3} regularizes transverse wave collapse.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_poincare_blp_kernel(
    U_ptr,         # [H, W] wave field u
    V_ptr,         # [H, W] auxiliary field v
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

    row_up = tl.where(row > 0, row - 1, row)
    row_dn = tl.where(row < H - 1, row + 1, row)
    col_lf = tl.where(col > 0, col - 1, col)
    col_rt = tl.where(col < W - 1, col + 1, col)

    idx_curr = row * W + col
    u = tl.load(U_ptr + idx_curr, mask=mask, other=0.0)
    v = tl.load(V_ptr + idx_curr, mask=mask, other=0.0)

    # First derivatives
    u_rt = tl.load(U_ptr + row * W + col_rt, mask=mask, other=0.0)
    u_lf = tl.load(U_ptr + row * W + col_lf, mask=mask, other=0.0)
    ux = 0.5 * (u_rt - u_lf)

    u_dn = tl.load(U_ptr + row_dn * W + col, mask=mask, other=0.0)
    u_up = tl.load(U_ptr + row_up * W + col, mask=mask, other=0.0)
    uy = 0.5 * (u_dn - u_up)

    # Mixed dispersion: u_{xxy} = d_y (u_{xx})
    u_dn_rt = tl.load(U_ptr + row_dn * W + col_rt, mask=mask, other=0.0)
    u_dn_lf = tl.load(U_ptr + row_dn * W + col_lf, mask=mask, other=0.0)
    uxx_dn = u_dn_rt - 2.0 * u_dn + u_dn_lf

    u_up_rt = tl.load(U_ptr + row_up * W + col_rt, mask=mask, other=0.0)
    u_up_lf = tl.load(U_ptr + row_up * W + col_lf, mask=mask, other=0.0)
    uxx_up = u_up_rt - 2.0 * u_up + u_up_lf

    uxxy = 0.5 * (uxx_dn - uxx_up)

    # BLP equation: u_t = (u_{xxy} - 4 u^2 u_y - 2 u_x v) * metric_scale
    rhs = (uxxy - 4.0 * (u * u) * uy - 2.0 * ux * v) * metric_scale
    new_u = u + dt * rhs

    tl.store(Out_U_ptr + idx_curr, new_u, mask=mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")
    H, W = 256, 256
    total_nodes = H * W
    dt = 0.0005

    torch.manual_seed(42)
    u = torch.randn(H, W, device=device, dtype=torch.float32) * 0.1
    v = torch.randn(H, W, device=device, dtype=torch.float32) * 0.1
    y = torch.linspace(0.6, 2.8, H, device=device, dtype=torch.float32)

    def ref_blp(u, v, y, dt):
        metric_scale = 1.0 / (y.view(H, 1) ** 3 + 1e-5)
        u_pad = torch.nn.functional.pad(u.unsqueeze(0).unsqueeze(0), (1, 1, 1, 1), mode='replicate')[0, 0]

        ux = 0.5 * (u_pad[1:-1, 2:] - u_pad[1:-1, :-2])
        uy = 0.5 * (u_pad[2:, 1:-1] - u_pad[:-2, 1:-1])

        uxx = u_pad[1:-1, 2:] - 2*u + u_pad[1:-1, :-2]
        uxx_pad = torch.nn.functional.pad(uxx.unsqueeze(0).unsqueeze(0), (0, 0, 1, 1), mode='replicate')[0, 0]
        uxxy = 0.5 * (uxx_pad[2:, :] - uxx_pad[:-2, :])

        rhs = (uxxy - 4.0 * (u**2) * uy - 2.0 * ux * v) * metric_scale
        return u + dt * rhs

    for _ in range(20):
        ref_out = ref_blp(u, v, y, dt)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 100
    for _ in range(iters):
        ref_out = ref_blp(u, v, y, dt)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out_u = torch.empty_like(u)
    BLOCK_M = 256
    grid = ((total_nodes + BLOCK_M - 1) // BLOCK_M,)

    for _ in range(20):
        fused_poincare_blp_kernel[grid](
            u, v, out_u, y, dt, H, W, BLOCK_M
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_poincare_blp_kernel[grid](
            u, v, out_u, y, dt, H, W, BLOCK_M
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    max_err = torch.max(torch.abs(out_u - ref_out)).item()
    speedup = ref_time / triton_time
    throughput = total_nodes / triton_time / 1e6

    print(f"=== Workstation Benchmark: Cycle 216 Poincaré Boiti-Leon-Pempinelli (BLP) Flow ===")
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
