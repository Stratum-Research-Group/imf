"""
Physical Workstation Triton Kernel: Fused Poincaré Broer-Kaup Dispersive Flow (Cycle 217)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 8.9), 16GB VRAM.

The Broer-Kaup system models bidirectional shallow water waves with surface tension and dispersion:
    u_t = - u u_x - v_x + 0.5 u_{xx}
    v_t = - (u v)_x - 0.5 v_{xx}
In Poincaré half-space, the second-order dispersion is scaled by y^{-2}, preserving hyperbolic
momentum conservation.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_poincare_broer_kaup_kernel(
    U_ptr,         # [N] horizontal velocity field u
    V_ptr,         # [N] wave height / density deviation v
    Out_U_ptr,     # [N]
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
    metric_scale = 1.0 / (y * y + 1e-5)

    idx_m1 = tl.where(offset >= 1, offset - 1, 0)
    idx_p1 = tl.where(offset < N - 1, offset + 1, N - 1)

    u = tl.load(U_ptr + offset, mask=mask, other=0.0)
    v = tl.load(V_ptr + offset, mask=mask, other=0.0)

    u_p1 = tl.load(U_ptr + idx_p1, mask=mask, other=0.0)
    u_m1 = tl.load(U_ptr + idx_m1, mask=mask, other=0.0)
    v_p1 = tl.load(V_ptr + idx_p1, mask=mask, other=0.0)
    v_m1 = tl.load(V_ptr + idx_m1, mask=mask, other=0.0)

    # First derivatives
    ux = 0.5 * (u_p1 - u_m1)
    vx = 0.5 * (v_p1 - v_m1)

    # Second derivatives
    uxx = u_p1 - 2.0 * u + u_m1
    vxx = v_p1 - 2.0 * v + v_m1

    # (u * v)_x
    uv_p1 = u_p1 * v_p1
    uv_m1 = u_m1 * v_m1
    d_uv_x = 0.5 * (uv_p1 - uv_m1)

    # Broer-Kaup equations:
    # u_t = - u * ux - vx + 0.5 * uxx
    # v_t = - (u * v)_x - 0.5 * vxx
    rhs_u = (- u * ux - vx + 0.5 * uxx) * metric_scale
    rhs_v = (- d_uv_x - 0.5 * vxx) * metric_scale

    new_u = u + dt * rhs_u
    new_v = v + dt * rhs_v

    tl.store(Out_U_ptr + offset, new_u, mask=mask)
    tl.store(Out_V_ptr + offset, new_v, mask=mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")
    N = 524288  # 512K lattice nodes
    dt = 0.0001

    torch.manual_seed(42)
    u = torch.randn(N, device=device, dtype=torch.float32) * 0.1
    v = torch.randn(N, device=device, dtype=torch.float32) * 0.1
    y = torch.linspace(0.8, 2.5, N, device=device, dtype=torch.float32)

    def ref_broer_kaup(u, v, y, dt):
        metric_scale = 1.0 / (y ** 2 + 1e-5)
        u_pad = torch.nn.functional.pad(u.unsqueeze(0).unsqueeze(0), (1, 1), mode='replicate')[0, 0]
        v_pad = torch.nn.functional.pad(v.unsqueeze(0).unsqueeze(0), (1, 1), mode='replicate')[0, 0]

        ux = 0.5 * (u_pad[2:] - u_pad[:-2])
        vx = 0.5 * (v_pad[2:] - v_pad[:-2])

        uxx = u_pad[2:] - 2*u + u_pad[:-2]
        vxx = v_pad[2:] - 2*v + v_pad[:-2]

        uv = u_pad * v_pad
        d_uv_x = 0.5 * (uv[2:] - uv[:-2])

        rhs_u = (- u * ux - vx + 0.5 * uxx) * metric_scale
        rhs_v = (- d_uv_x - 0.5 * vxx) * metric_scale

        return u + dt * rhs_u, v + dt * rhs_v

    for _ in range(20):
        ref_u, ref_v = ref_broer_kaup(u, v, y, dt)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 100
    for _ in range(iters):
        ref_u, ref_v = ref_broer_kaup(u, v, y, dt)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out_u = torch.empty_like(u)
    out_v = torch.empty_like(v)
    BLOCK_N = 512
    grid = ((N + BLOCK_N - 1) // BLOCK_N,)

    for _ in range(20):
        fused_poincare_broer_kaup_kernel[grid](
            u, v, out_u, out_v, y, dt, N, BLOCK_N
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_poincare_broer_kaup_kernel[grid](
            u, v, out_u, out_v, y, dt, N, BLOCK_N
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    max_err_u = torch.max(torch.abs(out_u - ref_u)).item()
    max_err_v = torch.max(torch.abs(out_v - ref_v)).item()
    max_err = max(max_err_u, max_err_v)
    speedup = ref_time / triton_time
    throughput = (N * 2) / triton_time / 1e6

    print(f"=== Workstation Benchmark: Cycle 217 Poincaré Broer-Kaup Dispersive Flow ===")
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
