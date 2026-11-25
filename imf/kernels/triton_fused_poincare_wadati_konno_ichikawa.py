"""
Physical Workstation Triton Kernel: Fused Poincaré Wadati-Konno-Ichikawa (WKI) Integrable Flow (Cycle 225)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 12.0), 16GB VRAM.

The Wadati-Konno-Ichikawa (WKI) equation describes nonlinear loop soliton dynamics in elastic media:
    u_t + ( u_{xx} / (1 + u_x^2)^{3/2} )_x = 0
or resolved:
    u_t = - ∂_x [ u_{xx} * (1 + u_x^2)^{-3/2} ]
In the Poincaré half-space H^2, the spatial derivative is scaled by the metric factor y^{-3},
damping loop curvature singularities near the horizon boundary.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_poincare_wki_kernel(
    U_ptr,         # [N] field u
    Out_U_ptr,     # [N]
    Y_ptr,         # [N] hyperbolic coordinate
    dt: tl.constexpr,
    N: tl.constexpr,
    BLOCK_N: tl.constexpr,
):
    pid = tl.program_id(0)
    offset = pid * BLOCK_N + tl.arange(0, BLOCK_N)
    mask = offset < N

    y = tl.load(Y_ptr + offset, mask=mask, other=1.0)
    metric_scale = 1.0 / (y * y * y + 1e-5)

    idx_m2 = tl.where(offset >= 2, offset - 2, 0)
    idx_m1 = tl.where(offset >= 1, offset - 1, 0)
    idx_p1 = tl.where(offset < N - 1, offset + 1, N - 1)
    idx_p2 = tl.where(offset < N - 2, offset + 2, N - 1)

    u = tl.load(U_ptr + offset, mask=mask, other=0.0)

    u_m2 = tl.load(U_ptr + idx_m2, mask=mask, other=0.0)
    u_m1 = tl.load(U_ptr + idx_m1, mask=mask, other=0.0)
    u_p1 = tl.load(U_ptr + idx_p1, mask=mask, other=0.0)
    u_p2 = tl.load(U_ptr + idx_p2, mask=mask, other=0.0)

    # First derivatives at offset-1, offset, offset+1
    ux_m1 = 0.5 * (u - u_m2)
    ux_p1 = 0.5 * (u_p2 - u)
    ux = 0.5 * (u_p1 - u_m1)

    # Second derivatives at offset-1, offset, offset+1
    uxx_m1 = u - 2.0 * u_m1 + u_m2
    uxx_p1 = u_p2 - 2.0 * u_p1 + u
    uxx = u_p1 - 2.0 * u + u_m1

    # Curvature term: kappa = u_{xx} / (1 + u_x^2)^{3/2}
    denom_p1 = tl.sqrt(1.0 + ux_p1 * ux_p1)
    denom_p1_cube = denom_p1 * denom_p1 * denom_p1
    kappa_p1 = uxx_p1 / (denom_p1_cube + 1e-5)

    denom_m1 = tl.sqrt(1.0 + ux_m1 * ux_m1)
    denom_m1_cube = denom_m1 * denom_m1 * denom_m1
    kappa_m1 = uxx_m1 / (denom_m1_cube + 1e-5)

    # Derivative of curvature: ∂_x kappa ~ 0.5 * (kappa_{i+1} - kappa_{i-1})
    d_kappa_x = 0.5 * (kappa_p1 - kappa_m1)

    # WKI equation: u_t = - d_kappa_x * metric_scale
    rhs = - d_kappa_x * metric_scale
    new_u = u + dt * rhs

    tl.store(Out_U_ptr + offset, new_u, mask=mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")
    N = 524288  # 512K nodes
    dt = 0.0001

    torch.manual_seed(42)
    u = torch.randn(N, device=device, dtype=torch.float32) * 0.1
    y = torch.linspace(0.8, 2.5, N, device=device, dtype=torch.float32)

    def ref_wki(u, y, dt):
        metric_scale = 1.0 / (y ** 3 + 1e-5)
        u_pad = torch.nn.functional.pad(u.unsqueeze(0).unsqueeze(0), (2, 2), mode='replicate')[0, 0]

        # Evaluate kappa at i-1, i, i+1
        # u_pad has length N+4. indices 1..N+2 correspond to shifted points
        # ux at all internal points
        ux_all = 0.5 * (u_pad[2:] - u_pad[:-2]) # length N+2
        uxx_all = u_pad[2:] - 2*u_pad[1:-1] + u_pad[:-2] # length N+2

        denom = torch.sqrt(1.0 + ux_all**2)**3 + 1e-5
        kappa = uxx_all / denom # length N+2

        d_kappa = 0.5 * (kappa[2:] - kappa[:-2]) # length N
        rhs = - d_kappa * metric_scale
        return u + dt * rhs

    for _ in range(20):
        ref_out = ref_wki(u, y, dt)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 100
    for _ in range(iters):
        ref_out = ref_wki(u, y, dt)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out_u = torch.empty_like(u)
    BLOCK_N = 512
    grid = ((N + BLOCK_N - 1) // BLOCK_N,)

    for _ in range(20):
        fused_poincare_wki_kernel[grid](
            u, out_u, y, dt, N, BLOCK_N
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_poincare_wki_kernel[grid](
            u, out_u, y, dt, N, BLOCK_N
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    max_err = torch.max(torch.abs(out_u - ref_out)).item()
    speedup = ref_time / triton_time
    throughput = N / triton_time / 1e6

    print(f"=== Workstation Benchmark: Cycle 225 Poincaré Wadati-Konno-Ichikawa Flow ===")
    print(f"Hardware: {torch.cuda.get_device_name(0)}")
    print(f"Lattice size: {N} nodes")
    print(f"PyTorch baseline latency: {ref_time*1e6:.2f} us")
    print(f"Triton fused latency:     {triton_time*1e6:.2f} us")
    print(f"Speedup factor:           {speedup:.2f}x")
    print(f"Throughput:               {throughput:.2f} M nodes/s")
    print(f"Numerical Max Error:      {max_err:.2e}")
    assert max_err < 1e-4, f"Tolerance exceeded: {max_err}"
    print("PHYSICAL HARDWARE TEST PASSED")

if __name__ == "__main__":
    run_benchmark()
