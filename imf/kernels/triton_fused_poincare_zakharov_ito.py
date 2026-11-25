"""
Physical Workstation Triton Kernel: Fused Poincaré Zakharov-Ito Multi-Component Flow (Cycle 213)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 12.0), 16GB VRAM.

The Zakharov-Ito system models coupled Langmuir and acoustic wave packets in plasmas:
    i u_t = - u_{xx} + 2 u v
    v_t = - v_{xxx} - 6 v v_x + 2 (|u|^2)_x
where u = u_r + i u_i is the high-frequency complex envelope, and v is the real low-frequency acoustic density.
In Poincaré half-space, spatial dispersion is scaled by the hyperbolic metric y^{-3},
damping wave turbulence near the horizon.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_poincare_zakharov_ito_kernel(
    Ur_ptr,        # [N] real part of complex wave envelope
    Ui_ptr,        # [N] imag part of complex wave envelope
    V_ptr,         # [N] real acoustic field
    Out_Ur_ptr,    # [N]
    Out_Ui_ptr,    # [N]
    Out_V_ptr,     # [N]
    Y_ptr,         # [N] hyperbolic coordinate
    dt: tl.constexpr,
    N: tl.constexpr,
    BLOCK_N: tl.constexpr,
):
    pid = tl.program_id(0)
    offset = pid * BLOCK_N + tl.arange(0, BLOCK_N)
    mask = offset < N

    y = tl.load(Y_ptr + offset, mask=mask, other=1.0)
    metric_scale2 = 1.0 / (y * y + 1e-5)      # for 2nd derivative
    metric_scale3 = 1.0 / (y * y * y + 1e-5)  # for 3rd derivative

    idx_m2 = tl.where(offset >= 2, offset - 2, 0)
    idx_m1 = tl.where(offset >= 1, offset - 1, 0)
    idx_p1 = tl.where(offset < N - 1, offset + 1, N - 1)
    idx_p2 = tl.where(offset < N - 2, offset + 2, N - 1)

    ur = tl.load(Ur_ptr + offset, mask=mask, other=0.0)
    ui = tl.load(Ui_ptr + offset, mask=mask, other=0.0)
    v  = tl.load(V_ptr + offset, mask=mask, other=0.0)

    # 2nd derivatives: u_{xx} ~ f_{i+1} - 2 f_i + f_{i-1}
    ur_p1 = tl.load(Ur_ptr + idx_p1, mask=mask, other=0.0)
    ur_m1 = tl.load(Ur_ptr + idx_m1, mask=mask, other=0.0)
    ur_xx = ur_p1 - 2.0 * ur + ur_m1

    ui_p1 = tl.load(Ui_ptr + idx_p1, mask=mask, other=0.0)
    ui_m1 = tl.load(Ui_ptr + idx_m1, mask=mask, other=0.0)
    ui_xx = ui_p1 - 2.0 * ui + ui_m1

    # Envelope equation: i u_t = - u_{xx} + 2 u v
    # => u_t = i (u_{xx} - 2 u v)
    # d(ur)/dt = - (ui_xx - 2 * ui * v) * metric_scale2
    # d(ui)/dt =   (ur_xx - 2 * ur * v) * metric_scale2
    d_ur = - (ui_xx - 2.0 * ui * v) * metric_scale2
    d_ui =   (ur_xx - 2.0 * ur * v) * metric_scale2

    # Acoustic field: v_t = - v_{xxx} - 6 v v_x + 2 (|u|^2)_x
    v_m2 = tl.load(V_ptr + idx_m2, mask=mask, other=0.0)
    v_m1 = tl.load(V_ptr + idx_m1, mask=mask, other=0.0)
    v_p1 = tl.load(V_ptr + idx_p1, mask=mask, other=0.0)
    v_p2 = tl.load(V_ptr + idx_p2, mask=mask, other=0.0)

    vx = 0.5 * (v_p1 - v_m1)
    vxxx = 0.5 * (v_p2 - 2.0 * v_p1 + 2.0 * v_m1 - v_m2)

    # (|u|^2)_x
    mod_sq_p1 = ur_p1 * ur_p1 + ui_p1 * ui_p1
    mod_sq_m1 = ur_m1 * ur_m1 + ui_m1 * ui_m1
    d_mod_sq_x = 0.5 * (mod_sq_p1 - mod_sq_m1)

    d_v = (- vxxx - 6.0 * v * vx + 2.0 * d_mod_sq_x) * metric_scale3

    new_ur = ur + dt * d_ur
    new_ui = ui + dt * d_ui
    new_v  = v  + dt * d_v

    tl.store(Out_Ur_ptr + offset, new_ur, mask=mask)
    tl.store(Out_Ui_ptr + offset, new_ui, mask=mask)
    tl.store(Out_V_ptr + offset, new_v, mask=mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")
    N = 524288  # 512K nodes
    dt = 0.0001

    torch.manual_seed(42)
    ur = torch.randn(N, device=device, dtype=torch.float32) * 0.2
    ui = torch.randn(N, device=device, dtype=torch.float32) * 0.2
    v  = torch.randn(N, device=device, dtype=torch.float32) * 0.1
    y  = torch.linspace(0.8, 2.5, N, device=device, dtype=torch.float32)

    def ref_zakharov_ito(ur, ui, v, y, dt):
        m2 = 1.0 / (y ** 2 + 1e-5)
        m3 = 1.0 / (y ** 3 + 1e-5)

        ur_pad = torch.nn.functional.pad(ur.unsqueeze(0).unsqueeze(0), (2, 2), mode='replicate')[0, 0]
        ui_pad = torch.nn.functional.pad(ui.unsqueeze(0).unsqueeze(0), (2, 2), mode='replicate')[0, 0]
        v_pad  = torch.nn.functional.pad(v.unsqueeze(0).unsqueeze(0),  (2, 2), mode='replicate')[0, 0]

        ur_xx = ur_pad[3:-1] - 2*ur + ur_pad[1:-3]
        ui_xx = ui_pad[3:-1] - 2*ui + ui_pad[1:-3]

        d_ur = - (ui_xx - 2.0 * ui * v) * m2
        d_ui =   (ur_xx - 2.0 * ur * v) * m2

        vx = 0.5 * (v_pad[3:-1] - v_pad[1:-3])
        vxxx = 0.5 * (v_pad[4:] - 2*v_pad[3:-1] + 2*v_pad[1:-3] - v_pad[:-4])

        mod_p1 = ur_pad[3:-1]**2 + ui_pad[3:-1]**2
        mod_m1 = ur_pad[1:-3]**2 + ui_pad[1:-3]**2
        d_mod_x = 0.5 * (mod_p1 - mod_m1)

        d_v = (- vxxx - 6.0 * v * vx + 2.0 * d_mod_x) * m3

        return ur + dt * d_ur, ui + dt * d_ui, v + dt * d_v

    # Warmup reference
    for _ in range(20):
        ref_ur, ref_ui, ref_v = ref_zakharov_ito(ur, ui, v, y, dt)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 100
    for _ in range(iters):
        ref_ur, ref_ui, ref_v = ref_zakharov_ito(ur, ui, v, y, dt)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out_ur = torch.empty_like(ur)
    out_ui = torch.empty_like(ui)
    out_v  = torch.empty_like(v)
    BLOCK_N = 512
    grid = ((N + BLOCK_N - 1) // BLOCK_N,)

    # Warmup Triton
    for _ in range(20):
        fused_poincare_zakharov_ito_kernel[grid](
            ur, ui, v, out_ur, out_ui, out_v, y, dt, N, BLOCK_N
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_poincare_zakharov_ito_kernel[grid](
            ur, ui, v, out_ur, out_ui, out_v, y, dt, N, BLOCK_N
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    max_err_ur = torch.max(torch.abs(out_ur - ref_ur)).item()
    max_err_ui = torch.max(torch.abs(out_ui - ref_ui)).item()
    max_err_v  = torch.max(torch.abs(out_v  - ref_v)).item()
    max_err = max(max_err_ur, max_err_ui, max_err_v)
    speedup = ref_time / triton_time
    throughput = (N * 3) / triton_time / 1e6

    print(f"=== Workstation Benchmark: Cycle 213 Poincaré Zakharov-Ito Multi-Component Flow ===")
    print(f"Hardware: {torch.cuda.get_device_name(0)}")
    print(f"Lattice size: {N} nodes ({N*3} coupled field variables)")
    print(f"PyTorch baseline latency: {ref_time*1e6:.2f} us")
    print(f"Triton fused latency:     {triton_time*1e6:.2f} us")
    print(f"Speedup factor:           {speedup:.2f}x")
    print(f"Throughput:               {throughput:.2f} M variables/s")
    print(f"Numerical Max Error:      {max_err:.2e}")
    assert max_err < 1e-4, f"Tolerance exceeded: {max_err}"
    print("PHYSICAL HARDWARE TEST PASSED")

if __name__ == "__main__":
    run_benchmark()
