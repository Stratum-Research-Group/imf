"""
Physical Workstation Triton Kernel: Fused Poincaré Gerdjikov-Ivanov Derivative NLS Flow (Cycle 224)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 12.0), 16GB VRAM.

The Gerdjikov-Ivanov (GI) equation is the third canonical member of the derivative NLS family:
    i u_t + u_{xx} - i u^2 u_x^* + 0.5 |u|^4 u = 0
where u = u_r + i u_i is the complex wave envelope, and u_x^* is the complex conjugate of the spatial derivative.
In the Poincaré half-space H^2, the spatial dispersion is scaled by the metric factor y^{-2},
regularizing quintic focusing and derivative self-interactions.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_poincare_gerdjikov_ivanov_kernel(
    Ur_ptr,        # [N] real part
    Ui_ptr,        # [N] imag part
    Out_Ur_ptr,    # [N]
    Out_Ui_ptr,    # [N]
    Y_ptr,         # [N] hyperbolic coordinate
    dt: tl.constexpr,
    N: tl.constexpr,
    BLOCK_N: tl.constexpr,
):
    pid = tl.program_id(0)
    offset = pid * BLOCK_N + tl.arange(0, BLOCK_N)
    mask = offset < N

    y = tl.load(Y_ptr + offset, mask=mask, other=1.0)
    metric_scale = 1.0 / (y * y + 1e-5)

    idx_m1 = tl.where(offset >= 1, offset - 1, 0)
    idx_p1 = tl.where(offset < N - 1, offset + 1, N - 1)

    ur = tl.load(Ur_ptr + offset, mask=mask, other=0.0)
    ui = tl.load(Ui_ptr + offset, mask=mask, other=0.0)

    ur_p1 = tl.load(Ur_ptr + idx_p1, mask=mask, other=0.0)
    ur_m1 = tl.load(Ur_ptr + idx_m1, mask=mask, other=0.0)
    ui_p1 = tl.load(Ui_ptr + idx_p1, mask=mask, other=0.0)
    ui_m1 = tl.load(Ui_ptr + idx_m1, mask=mask, other=0.0)

    # 1st derivatives: u_x = ur_x + i ui_x, u_x^* = ur_x - i ui_x
    ur_x = 0.5 * (ur_p1 - ur_m1)
    ui_x = 0.5 * (ui_p1 - ui_m1)

    # 2nd derivatives: u_{xx}
    ur_xx = ur_p1 - 2.0 * ur + ur_m1
    ui_xx = ui_p1 - 2.0 * ui + ui_m1

    # u^2 = (ur + i ui)^2 = (ur^2 - ui^2) + i (2 ur ui)
    u2_r = ur * ur - ui * ui
    u2_i = 2.0 * ur * ui

    # u^2 * u_x^* = (u2_r + i u2_i) * (ur_x - i ui_x)
    # Real = u2_r * ur_x + u2_i * ui_x
    # Imag = u2_i * ur_x - u2_r * ui_x
    p_r = u2_r * ur_x + u2_i * ui_x
    p_i = u2_i * ur_x - u2_r * ui_x

    # - i u^2 u_x^* = - i (p_r + i p_i) = p_i - i p_r
    # Quintic term: 0.5 * |u|^4 * u
    mod_sq = ur * ur + ui * ui
    mod_4 = mod_sq * mod_sq
    q_r = 0.5 * mod_4 * ur
    q_i = 0.5 * mod_4 * ui

    # Equation: i u_t = - u_{xx} + i u^2 u_x^* - 0.5 |u|^4 u
    # => u_t = i (u_{xx} - i u^2 u_x^* + 0.5 |u|^4 u)
    # Inside parentheses:
    # R_in = ur_xx + p_i + q_r
    # I_in = ui_xx - p_r + q_i
    # Multiply by i:
    # Real part of u_t = - I_in = - (ui_xx - p_r + q_i) = - ui_xx + p_r - q_i
    # Imag part of u_t =   R_in =   (ur_xx + p_i + q_r) =   ur_xx + p_i + q_r
    d_ur = (- ui_xx + p_r - q_i) * metric_scale
    d_ui = (  ur_xx + p_i + q_r) * metric_scale

    new_ur = ur + dt * d_ur
    new_ui = ui + dt * d_ui

    tl.store(Out_Ur_ptr + offset, new_ur, mask=mask)
    tl.store(Out_Ui_ptr + offset, new_ui, mask=mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")
    N = 524288  # 512K nodes
    dt = 0.0001

    torch.manual_seed(42)
    ur = torch.randn(N, device=device, dtype=torch.float32) * 0.15
    ui = torch.randn(N, device=device, dtype=torch.float32) * 0.15
    y = torch.linspace(0.8, 2.5, N, device=device, dtype=torch.float32)

    def ref_gi(ur, ui, y, dt):
        metric_scale = 1.0 / (y ** 2 + 1e-5)
        ur_pad = torch.nn.functional.pad(ur.unsqueeze(0).unsqueeze(0), (1, 1), mode='replicate')[0, 0]
        ui_pad = torch.nn.functional.pad(ui.unsqueeze(0).unsqueeze(0), (1, 1), mode='replicate')[0, 0]

        ur_x = 0.5 * (ur_pad[2:] - ur_pad[:-2])
        ui_x = 0.5 * (ui_pad[2:] - ui_pad[:-2])

        ur_xx = ur_pad[2:] - 2*ur + ur_pad[:-2]
        ui_xx = ui_pad[2:] - 2*ui + ui_pad[:-2]

        u2_r = ur**2 - ui**2
        u2_i = 2 * ur * ui

        p_r = u2_r * ur_x + u2_i * ui_x
        p_i = u2_i * ur_x - u2_r * ui_x

        mod_4 = (ur**2 + ui**2)**2
        q_r = 0.5 * mod_4 * ur
        q_i = 0.5 * mod_4 * ui

        d_ur = (- ui_xx + p_r - q_i) * metric_scale
        d_ui = (  ur_xx + p_i + q_r) * metric_scale

        return ur + dt * d_ur, ui + dt * d_ui

    for _ in range(20):
        ref_ur, ref_ui = ref_gi(ur, ui, y, dt)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 100
    for _ in range(iters):
        ref_ur, ref_ui = ref_gi(ur, ui, y, dt)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out_ur = torch.empty_like(ur)
    out_ui = torch.empty_like(ui)
    BLOCK_N = 512
    grid = ((N + BLOCK_N - 1) // BLOCK_N,)

    for _ in range(20):
        fused_poincare_gerdjikov_ivanov_kernel[grid](
            ur, ui, out_ur, out_ui, y, dt, N, BLOCK_N
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_poincare_gerdjikov_ivanov_kernel[grid](
            ur, ui, out_ur, out_ui, y, dt, N, BLOCK_N
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    max_err_r = torch.max(torch.abs(out_ur - ref_ur)).item()
    max_err_i = torch.max(torch.abs(out_ui - ref_ui)).item()
    max_err = max(max_err_r, max_err_i)
    speedup = ref_time / triton_time
    throughput = (N * 2) / triton_time / 1e6

    print(f"=== Workstation Benchmark: Cycle 224 Poincaré Gerdjikov-Ivanov Derivative NLS Flow ===")
    print(f"Hardware: {torch.cuda.get_device_name(0)}")
    print(f"Lattice size: {N} nodes ({N*2} field variables)")
    print(f"PyTorch baseline latency: {ref_time*1e6:.2f} us")
    print(f"Triton fused latency:     {triton_time*1e6:.2f} us")
    print(f"Speedup factor:           {speedup:.2f}x")
    print(f"Throughput:               {throughput:.2f} M variables/s")
    print(f"Numerical Max Error:      {max_err:.2e}")
    assert max_err < 1e-4, f"Tolerance exceeded: {max_err}"
    print("PHYSICAL HARDWARE TEST PASSED")

if __name__ == "__main__":
    run_benchmark()
