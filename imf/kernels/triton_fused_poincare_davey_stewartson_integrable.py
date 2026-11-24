"""
Physical Workstation Triton Kernel: Fused Poincaré Davey-Stewartson Integrable System (Cycle 207)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 8.9), 16GB VRAM.

The Davey-Stewartson (DS) equations describe 2D modulated nonlinear wave packets:
    i A_t + c0 A_{xx} + A_{yy} = alpha |A|^2 A + beta A Q_x
    Q_{xx} + m Q_{yy} = (|A|^2)_x
where A = A_r + i A_i is complex envelope and Q is the mean flow potential.
In the Poincaré half-space, hyperbolic coordinate scaling y^{-2} regularizes wave collapse.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_poincare_davey_stewartson_kernel(
    Ar_ptr,        # [H, W] real part of envelope
    Ai_ptr,        # [H, W] imag part of envelope
    Q_ptr,         # [H, W] mean flow potential
    Out_Ar_ptr,    # [H, W]
    Out_Ai_ptr,    # [H, W]
    Y_ptr,         # [H] hyperbolic metric coordinate
    c0: tl.constexpr,      # dispersion coeff x
    alpha: tl.constexpr,   # cubic self-focusing coeff
    beta: tl.constexpr,    # coupling to mean flow
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
    metric_scale = 1.0 / (y * y + 1e-5)

    row_up = tl.where(row > 0, row - 1, row)
    row_dn = tl.where(row < H - 1, row + 1, row)
    col_lf = tl.where(col > 0, col - 1, col)
    col_rt = tl.where(col < W - 1, col + 1, col)

    idx_curr = row * W + col
    idx_up = row_up * W + col
    idx_dn = row_dn * W + col
    idx_lf = row * W + col_lf
    idx_rt = row * W + col_rt

    ar = tl.load(Ar_ptr + idx_curr, mask=mask, other=0.0)
    ai = tl.load(Ai_ptr + idx_curr, mask=mask, other=0.0)

    # 2D Laplacian components for Real part
    ar_up = tl.load(Ar_ptr + idx_up, mask=mask, other=0.0)
    ar_dn = tl.load(Ar_ptr + idx_dn, mask=mask, other=0.0)
    ar_lf = tl.load(Ar_ptr + idx_lf, mask=mask, other=0.0)
    ar_rt = tl.load(Ar_ptr + idx_rt, mask=mask, other=0.0)
    lap_ar = c0 * (ar_rt - 2.0 * ar + ar_lf) + (ar_dn - 2.0 * ar + ar_up)

    # 2D Laplacian components for Imag part
    ai_up = tl.load(Ai_ptr + idx_up, mask=mask, other=0.0)
    ai_dn = tl.load(Ai_ptr + idx_dn, mask=mask, other=0.0)
    ai_lf = tl.load(Ai_ptr + idx_lf, mask=mask, other=0.0)
    ai_rt = tl.load(Ai_ptr + idx_rt, mask=mask, other=0.0)
    lap_ai = c0 * (ai_rt - 2.0 * ai + ai_lf) + (ai_dn - 2.0 * ai + ai_up)

    # Mean flow potential gradient Q_x
    q_rt = tl.load(Q_ptr + idx_rt, mask=mask, other=0.0)
    q_lf = tl.load(Q_ptr + idx_lf, mask=mask, other=0.0)
    qx = 0.5 * (q_rt - q_lf)

    # Modulus squared |A|^2
    mod_sq = ar * ar + ai * ai

    # Non-linear potential: V = alpha * |A|^2 + beta * Q_x
    v_pot = alpha * mod_sq + beta * qx

    # i A_t = - lap_A + V A
    # => A_t = -i (- lap_A + V A) = i lap_A - i V A
    # d(Ar)/dt = - (lap_ai - V * ai)
    # d(Ai)/dt =   (lap_ar - V * ar)
    d_ar = - (lap_ai - v_pot * ai) * metric_scale
    d_ai =   (lap_ar - v_pot * ar) * metric_scale

    new_ar = ar + dt * d_ar
    new_ai = ai + dt * d_ai

    tl.store(Out_Ar_ptr + idx_curr, new_ar, mask=mask)
    tl.store(Out_Ai_ptr + idx_curr, new_ai, mask=mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")
    H, W = 256, 256
    total_nodes = H * W
    dt = 0.001
    c0 = 1.0
    alpha = 1.5
    beta = 0.8

    torch.manual_seed(42)
    ar = torch.randn(H, W, device=device, dtype=torch.float32) * 0.5
    ai = torch.randn(H, W, device=device, dtype=torch.float32) * 0.5
    q = torch.randn(H, W, device=device, dtype=torch.float32) * 0.2
    y = torch.linspace(0.5, 3.0, H, device=device, dtype=torch.float32)

    def ref_ds(ar, ai, q, y, dt, c0, alpha, beta):
        metric_scale = (1.0 / (y.view(H, 1) ** 2 + 1e-5))
        ar_pad = torch.nn.functional.pad(ar.unsqueeze(0).unsqueeze(0), (1, 1, 1, 1), mode='replicate')[0, 0]
        ai_pad = torch.nn.functional.pad(ai.unsqueeze(0).unsqueeze(0), (1, 1, 1, 1), mode='replicate')[0, 0]
        q_pad = torch.nn.functional.pad(q.unsqueeze(0).unsqueeze(0), (1, 1, 1, 1), mode='replicate')[0, 0]

        lap_ar = c0 * (ar_pad[1:-1, 2:] - 2*ar + ar_pad[1:-1, :-2]) + (ar_pad[2:, 1:-1] - 2*ar + ar_pad[:-2, 1:-1])
        lap_ai = c0 * (ai_pad[1:-1, 2:] - 2*ai + ai_pad[1:-1, :-2]) + (ai_pad[2:, 1:-1] - 2*ai + ai_pad[:-2, 1:-1])
        qx = 0.5 * (q_pad[1:-1, 2:] - q_pad[1:-1, :-2])

        v_pot = alpha * (ar**2 + ai**2) + beta * qx
        d_ar = - (lap_ai - v_pot * ai) * metric_scale
        d_ai =   (lap_ar - v_pot * ar) * metric_scale

        return ar + dt * d_ar, ai + dt * d_ai

    # Warmup reference
    for _ in range(20):
        ref_ar, ref_ai = ref_ds(ar, ai, q, y, dt, c0, alpha, beta)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 100
    for _ in range(iters):
        ref_ar, ref_ai = ref_ds(ar, ai, q, y, dt, c0, alpha, beta)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out_ar = torch.empty_like(ar)
    out_ai = torch.empty_like(ai)
    BLOCK_M = 256
    grid = ((total_nodes + BLOCK_M - 1) // BLOCK_M,)

    # Warmup Triton
    for _ in range(20):
        fused_poincare_davey_stewartson_kernel[grid](
            ar, ai, q, out_ar, out_ai, y, c0, alpha, beta, dt, H, W, BLOCK_M
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_poincare_davey_stewartson_kernel[grid](
            ar, ai, q, out_ar, out_ai, y, c0, alpha, beta, dt, H, W, BLOCK_M
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    max_err_r = torch.max(torch.abs(out_ar - ref_ar)).item()
    max_err_i = torch.max(torch.abs(out_ai - ref_ai)).item()
    max_err = max(max_err_r, max_err_i)
    speedup = ref_time / triton_time
    throughput = (total_nodes * 2) / triton_time / 1e6

    print(f"=== Workstation Benchmark: Cycle 207 Poincaré Davey-Stewartson Integrable System ===")
    print(f"Hardware: {torch.cuda.get_device_name(0)}")
    print(f"Grid size: {H}x{W} ({total_nodes} nodes, {total_nodes*2} field variables)")
    print(f"PyTorch baseline latency: {ref_time*1e6:.2f} us")
    print(f"Triton fused latency:     {triton_time*1e6:.2f} us")
    print(f"Speedup factor:           {speedup:.2f}x")
    print(f"Throughput:               {throughput:.2f} M variables/s")
    print(f"Numerical Max Error:      {max_err:.2e}")
    assert max_err < 1e-4, f"Tolerance exceeded: {max_err}"
    print("PHYSICAL HARDWARE TEST PASSED")

if __name__ == "__main__":
    run_benchmark()
