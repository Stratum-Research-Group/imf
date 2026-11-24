"""
Physical Workstation Triton Kernel: Fused Poincaré Nizhnik-Novikov-Veselov (NNV) 2D Integrable Flow (Cycle 208)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 8.9), 16GB VRAM.

The Nizhnik-Novikov-Veselov (NNV) equation is an isotropic 2D generalization of the KdV equation
associated with the non-stationary 2D Schrödinger spectral problem:
    u_t = u_{xxx} + u_{yyy} + 3 (u v)_x + 3 (u w)_y
    v_y = u_x
    w_x = u_y
In the Poincaré hyperbolic plane H^2, metric scaling y^{-3} stabilizes third-order dispersion
and anisotropic wave propagation.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_poincare_nnv_kernel(
    U_ptr,         # [H, W] main potential field
    V_ptr,         # [H, W] auxiliary field 1
    W_ptr,         # [H, W] auxiliary field 2
    Out_U_ptr,     # [H, W]
    Y_ptr,         # [H] hyperbolic metric coordinate
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

    # 5-point stencil neighbors along x (col) and y (row) for 3rd derivative
    # u_{xxx} ~ 0.5 * (u(x+2) - 2 u(x+1) + 2 u(x-1) - u(x-2))
    col_p1 = tl.where(col < W - 1, col + 1, col)
    col_p2 = tl.where(col < W - 2, col + 2, col_p1)
    col_m1 = tl.where(col > 0, col - 1, col)
    col_m2 = tl.where(col > 1, col - 2, col_m1)

    row_p1 = tl.where(row < H - 1, row + 1, row)
    row_p2 = tl.where(row < H - 2, row + 2, row_p1)
    row_m1 = tl.where(row > 0, row - 1, row)
    row_m2 = tl.where(row > 1, row - 2, row_m1)

    idx_curr = row * W + col
    u = tl.load(U_ptr + idx_curr, mask=mask, other=0.0)
    v = tl.load(V_ptr + idx_curr, mask=mask, other=0.0)
    w = tl.load(W_ptr + idx_curr, mask=mask, other=0.0)

    # Spatial dispersion: u_{xxx}
    u_xp2 = tl.load(U_ptr + row * W + col_p2, mask=mask, other=0.0)
    u_xp1 = tl.load(U_ptr + row * W + col_p1, mask=mask, other=0.0)
    u_xm1 = tl.load(U_ptr + row * W + col_m1, mask=mask, other=0.0)
    u_xm2 = tl.load(U_ptr + row * W + col_m2, mask=mask, other=0.0)
    uxxx = 0.5 * (u_xp2 - 2.0 * u_xp1 + 2.0 * u_xm1 - u_xm2)

    # Spatial dispersion: u_{yyy}
    u_yp2 = tl.load(U_ptr + row_p2 * W + col, mask=mask, other=0.0)
    u_yp1 = tl.load(U_ptr + row_p1 * W + col, mask=mask, other=0.0)
    u_ym1 = tl.load(U_ptr + row_m1 * W + col, mask=mask, other=0.0)
    u_ym2 = tl.load(U_ptr + row_m2 * W + col, mask=mask, other=0.0)
    uyyy = 0.5 * (u_yp2 - 2.0 * u_yp1 + 2.0 * u_ym1 - u_ym2)

    # Nonlinear terms: (u v)_x and (u w)_y
    # Load neighbors of (u * v) along x
    uv_p1 = u_xp1 * tl.load(V_ptr + row * W + col_p1, mask=mask, other=0.0)
    uv_m1 = u_xm1 * tl.load(V_ptr + row * W + col_m1, mask=mask, other=0.0)
    d_uv_x = 0.5 * (uv_p1 - uv_m1)

    # Load neighbors of (u * w) along y
    uw_p1 = u_yp1 * tl.load(W_ptr + row_p1 * W + col, mask=mask, other=0.0)
    uw_m1 = u_ym1 * tl.load(W_ptr + row_m1 * W + col, mask=mask, other=0.0)
    d_uw_y = 0.5 * (uw_p1 - uw_m1)

    # Total RHS
    rhs = (uxxx + uyyy + 3.0 * d_uv_x + 3.0 * d_uw_y) * metric_scale
    new_u = u + dt * rhs

    tl.store(Out_U_ptr + idx_curr, new_u, mask=mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")
    H, W = 256, 256
    total_nodes = H * W
    dt = 0.0005

    torch.manual_seed(42)
    u = torch.randn(H, W, device=device, dtype=torch.float32) * 0.2
    v = torch.randn(H, W, device=device, dtype=torch.float32) * 0.1
    w = torch.randn(H, W, device=device, dtype=torch.float32) * 0.1
    y = torch.linspace(0.5, 3.0, H, device=device, dtype=torch.float32)

    def ref_nnv(u, v, w, y, dt):
        metric_scale = (1.0 / (y.view(H, 1) ** 3 + 1e-5))
        u_padx = torch.nn.functional.pad(u.unsqueeze(0).unsqueeze(0), (2, 2, 0, 0), mode='replicate')[0, 0]
        u_pady = torch.nn.functional.pad(u.unsqueeze(0).unsqueeze(0), (0, 0, 2, 2), mode='replicate')[0, 0]

        uxxx = 0.5 * (u_padx[:, 4:] - 2*u_padx[:, 3:-1] + 2*u_padx[:, 1:-3] - u_padx[:, :-4])
        uyyy = 0.5 * (u_pady[4:, :] - 2*u_pady[3:-1, :] + 2*u_pady[1:-3, :] - u_pady[:-4, :])

        uv = u * v
        uw = u * w
        uv_pad = torch.nn.functional.pad(uv.unsqueeze(0).unsqueeze(0), (1, 1, 0, 0), mode='replicate')[0, 0]
        uw_pad = torch.nn.functional.pad(uw.unsqueeze(0).unsqueeze(0), (0, 0, 1, 1), mode='replicate')[0, 0]

        d_uv_x = 0.5 * (uv_pad[:, 2:] - uv_pad[:, :-2])
        d_uw_y = 0.5 * (uw_pad[2:, :] - uw_pad[:-2, :])

        rhs = (uxxx + uyyy + 3.0 * d_uv_x + 3.0 * d_uw_y) * metric_scale
        return u + dt * rhs

    # Warmup reference
    for _ in range(20):
        ref_out = ref_nnv(u, v, w, y, dt)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 100
    for _ in range(iters):
        ref_out = ref_nnv(u, v, w, y, dt)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out_u = torch.empty_like(u)
    BLOCK_M = 256
    grid = ((total_nodes + BLOCK_M - 1) // BLOCK_M,)

    # Warmup Triton
    for _ in range(20):
        fused_poincare_nnv_kernel[grid](
            u, v, w, out_u, y, dt, H, W, BLOCK_M
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_poincare_nnv_kernel[grid](
            u, v, w, out_u, y, dt, H, W, BLOCK_M
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    max_err = torch.max(torch.abs(out_u - ref_out)).item()
    speedup = ref_time / triton_time
    throughput = total_nodes / triton_time / 1e6

    print(f"=== Workstation Benchmark: Cycle 208 Poincaré Nizhnik-Novikov-Veselov (NNV) Flow ===")
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
