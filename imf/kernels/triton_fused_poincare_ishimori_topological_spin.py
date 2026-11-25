"""
Physical Workstation Triton Kernel: Fused Poincaré Ishimori Topological Spin Flow (Cycle 206)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 12.0), 16GB VRAM.

The Ishimori equation is a 2D integrable generalization of the Heisenberg ferromagnet
coupled to a scalar potential:
    S_t = S x (S_{xx} + a^2 S_{yy}) + u_x S_y + u_y S_x
    u_{xx} - a^2 u_{yy} = -2 a^2 S . (S_x x S_y)
where S in S^2 (|S|=1). In Poincaré hyperbolic half-space, the metric factor y^{-2}
couples to the spatial dispersion, scaling the spin precession and topological vortex charge.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_poincare_ishimori_kernel(
    S_ptr,         # [B, 3, H, W]
    U_ptr,         # [B, H, W]
    Out_S_ptr,     # [B, 3, H, W]
    Y_ptr,         # [H] (hyperbolic coordinate)
    a_sq: tl.constexpr, # coupling constant (e.g. 1.0)
    dt: tl.constexpr,   # time step
    H: tl.constexpr,
    W: tl.constexpr,
    BLOCK_M: tl.constexpr,
):
    pid = tl.program_id(0)
    # 1D flattened index across spatial nodes H * W
    total_nodes = H * W
    offset = pid * BLOCK_M + tl.arange(0, BLOCK_M)
    mask = offset < total_nodes

    row = offset // W
    col = offset % W

    # Load hyperbolic metric factor: y coordinate
    y = tl.load(Y_ptr + row, mask=mask, other=1.0)
    metric_scale = 1.0 / (y * y + 1e-5)

    # Periodic/clamped neighbors
    row_up = tl.where(row > 0, row - 1, row)
    row_dn = tl.where(row < H - 1, row + 1, row)
    col_lf = tl.where(col > 0, col - 1, col)
    col_rt = tl.where(col < W - 1, col + 1, col)

    idx_curr = row * W + col
    idx_up = row_up * W + col
    idx_dn = row_dn * W + col
    idx_lf = row * W + col_lf
    idx_rt = row * W + col_rt

    # Stride for channels [B, 3, H, W]
    stride_c = H * W

    # Load S = (Sx, Sy, Sz)
    sx = tl.load(S_ptr + idx_curr, mask=mask, other=0.0)
    sy = tl.load(S_ptr + stride_c + idx_curr, mask=mask, other=0.0)
    sz = tl.load(S_ptr + 2 * stride_c + idx_curr, mask=mask, other=1.0)

    # Laplacians for S components
    # d2S/dx2 ~ (S_rt - 2S + S_lf)
    # d2S/dy2 ~ (S_dn - 2S + S_up)
    sx_rt = tl.load(S_ptr + idx_rt, mask=mask, other=0.0)
    sx_lf = tl.load(S_ptr + idx_lf, mask=mask, other=0.0)
    sx_dn = tl.load(S_ptr + idx_dn, mask=mask, other=0.0)
    sx_up = tl.load(S_ptr + idx_up, mask=mask, other=0.0)
    lap_sx = (sx_rt - 2.0 * sx + sx_lf) + a_sq * (sx_dn - 2.0 * sx + sx_up)

    sy_rt = tl.load(S_ptr + stride_c + idx_rt, mask=mask, other=0.0)
    sy_lf = tl.load(S_ptr + stride_c + idx_lf, mask=mask, other=0.0)
    sy_dn = tl.load(S_ptr + stride_c + idx_dn, mask=mask, other=0.0)
    sy_up = tl.load(S_ptr + stride_c + idx_up, mask=mask, other=0.0)
    lap_sy = (sy_rt - 2.0 * sy + sy_lf) + a_sq * (sy_dn - 2.0 * sy + sy_up)

    sz_rt = tl.load(S_ptr + 2 * stride_c + idx_rt, mask=mask, other=1.0)
    sz_lf = tl.load(S_ptr + 2 * stride_c + idx_lf, mask=mask, other=1.0)
    sz_dn = tl.load(S_ptr + 2 * stride_c + idx_dn, mask=mask, other=1.0)
    sz_up = tl.load(S_ptr + 2 * stride_c + idx_up, mask=mask, other=1.0)
    lap_sz = (sz_rt - 2.0 * sz + sz_lf) + a_sq * (sz_dn - 2.0 * sz + sz_up)

    # First derivatives of S
    sx_x = 0.5 * (sx_rt - sx_lf)
    sx_y = 0.5 * (sx_dn - sx_up)
    sy_x = 0.5 * (sy_rt - sy_lf)
    sy_y = 0.5 * (sy_dn - sy_up)
    sz_x = 0.5 * (sz_rt - sz_lf)
    sz_y = 0.5 * (sz_dn - sz_up)

    # Load potential U derivatives
    u_rt = tl.load(U_ptr + idx_rt, mask=mask, other=0.0)
    u_lf = tl.load(U_ptr + idx_lf, mask=mask, other=0.0)
    u_dn = tl.load(U_ptr + idx_dn, mask=mask, other=0.0)
    u_up = tl.load(U_ptr + idx_up, mask=mask, other=0.0)
    u_x = 0.5 * (u_rt - u_lf)
    u_y = 0.5 * (u_dn - u_up)

    # Cross product: S x Lap(S)
    cross_x = sy * lap_sz - sz * lap_sy
    cross_y = sz * lap_sx - sx * lap_sz
    cross_z = sx * lap_sy - sy * lap_sx

    # Convective coupling: u_x * S_y + u_y * S_x
    conv_x = u_x * sx_y + u_y * sx_x
    conv_y = u_x * sy_y + u_y * sy_x
    conv_z = u_x * sz_y + u_y * sz_x

    # Total flux scaled by hyperbolic metric
    flux_x = (cross_x + conv_x) * metric_scale
    flux_y = (cross_y + conv_y) * metric_scale
    flux_z = (cross_z + conv_z) * metric_scale

    # Update spin: S_new = S + dt * flux
    new_sx = sx + dt * flux_x
    new_sy = sy + dt * flux_y
    new_sz = sz + dt * flux_z

    # Renormalize spin to unit sphere |S| = 1
    norm = tl.sqrt(new_sx * new_sx + new_sy * new_sy + new_sz * new_sz + 1e-12)
    new_sx = new_sx / norm
    new_sy = new_sy / norm
    new_sz = new_sz / norm

    tl.store(Out_S_ptr + idx_curr, new_sx, mask=mask)
    tl.store(Out_S_ptr + stride_c + idx_curr, new_sy, mask=mask)
    tl.store(Out_S_ptr + 2 * stride_c + idx_curr, new_sz, mask=mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")
    H, W = 256, 256
    total_nodes = H * W
    dt = 0.005
    a_sq = 1.0

    torch.manual_seed(42)
    # Generate random unit spins
    raw_s = torch.randn(1, 3, H, W, device=device, dtype=torch.float32)
    s = raw_s / torch.norm(raw_s, dim=1, keepdim=True)
    u = torch.randn(1, H, W, device=device, dtype=torch.float32) * 0.1
    y = torch.linspace(0.5, 3.0, H, device=device, dtype=torch.float32)

    # PyTorch reference
    def ref_ishimori(s, u, y, dt, a_sq):
        metric_scale = (1.0 / (y.view(1, 1, H, 1) ** 2 + 1e-5))
        # Central differences with replicate padding
        s_pad = torch.nn.functional.pad(s, (1, 1, 1, 1), mode='replicate')
        u_pad = torch.nn.functional.pad(u.unsqueeze(1), (1, 1, 1, 1), mode='replicate').squeeze(1)

        lap_x = s_pad[:, :, 1:-1, 2:] - 2 * s + s_pad[:, :, 1:-1, :-2]
        lap_y = s_pad[:, :, 2:, 1:-1] - 2 * s + s_pad[:, :, :-2, 1:-1]
        lap_s = lap_x + a_sq * lap_y

        sx = 0.5 * (s_pad[:, :, 1:-1, 2:] - s_pad[:, :, 1:-1, :-2])
        sy = 0.5 * (s_pad[:, :, 2:, 1:-1] - s_pad[:, :, :-2, 1:-1])

        ux = 0.5 * (u_pad[:, 1:-1, 2:] - u_pad[:, 1:-1, :-2]).unsqueeze(1)
        uy = 0.5 * (u_pad[:, 2:, 1:-1] - u_pad[:, :-2, 1:-1]).unsqueeze(1)

        cross = torch.cross(s, lap_s, dim=1)
        conv = ux * sy + uy * sx
        flux = (cross + conv) * metric_scale
        s_next = s + dt * flux
        return s_next / torch.norm(s_next, dim=1, keepdim=True)

    # Warmup reference
    for _ in range(20):
        ref_out = ref_ishimori(s, u, y, dt, a_sq)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 100
    for _ in range(iters):
        ref_out = ref_ishimori(s, u, y, dt, a_sq)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out_s = torch.empty_like(s)
    BLOCK_M = 256
    grid = ((total_nodes + BLOCK_M - 1) // BLOCK_M,)

    # Warmup Triton
    for _ in range(20):
        fused_poincare_ishimori_kernel[grid](
            s, u, out_s, y, a_sq, dt, H, W, BLOCK_M
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_poincare_ishimori_kernel[grid](
            s, u, out_s, y, a_sq, dt, H, W, BLOCK_M
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    max_err = torch.max(torch.abs(out_s - ref_out)).item()
    speedup = ref_time / triton_time
    throughput = (total_nodes * 3) / triton_time / 1e6

    print(f"=== Workstation Benchmark: Cycle 206 Poincaré Ishimori Topological Spin Flow ===")
    print(f"Hardware: {torch.cuda.get_device_name(0)}")
    print(f"Grid size: {H}x{W} ({total_nodes} nodes, {total_nodes*3} spin components)")
    print(f"PyTorch baseline latency: {ref_time*1e6:.2f} us")
    print(f"Triton fused latency:     {triton_time*1e6:.2f} us")
    print(f"Speedup factor:           {speedup:.2f}x")
    print(f"Throughput:               {throughput:.2f} M spin elem/s")
    print(f"Numerical Max Error:      {max_err:.2e}")
    assert max_err < 1e-4, f"Tolerance exceeded: {max_err}"
    print("PHYSICAL HARDWARE TEST PASSED")

if __name__ == "__main__":
    run_benchmark()
