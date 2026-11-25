"""
Physical Workstation Triton Kernel: Fused Poincaré Calogero-Degasperis Integrable Flow (Cycle 220)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 8.9), 16GB VRAM.

The Calogero-Degasperis equation is a spectral dispersive equation with non-local boundary interactions:
    u_t = 0.25 u_{xxx} - 1.5 u^2 u_x + 0.125 (u_x)^3 / (u^2 + eps)
In Poincaré half-space, spatial derivatives are scaled by the hyperbolic metric y^{-3},
preserving solitary wave profiles and Hamiltonian energy.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_poincare_calogero_degasperis_kernel(
    U_ptr,         # [N] wave field u
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

    # First derivative
    ux = 0.5 * (u_p1 - u_m1)

    # Third derivative
    uxxx = 0.5 * (u_p2 - 2.0 * u_p1 + 2.0 * u_m1 - u_m2)

    # Calogero-Degasperis equation:
    # u_t = (0.25 * uxxx - 1.5 * u^2 * ux + 0.125 * (ux)^3 / (u^2 + 1e-4)) * metric_scale
    ux_cube = ux * ux * ux
    u_sq = u * u
    nl_ratio = 0.125 * ux_cube / (u_sq + 1e-4)

    rhs = (0.25 * uxxx - 1.5 * u_sq * ux + nl_ratio) * metric_scale
    new_u = u + dt * rhs

    tl.store(Out_U_ptr + offset, new_u, mask=mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")
    N = 524288  # 512K lattice nodes
    dt = 0.0001

    torch.manual_seed(42)
    u = torch.randn(N, device=device, dtype=torch.float32) * 0.2 + 0.5
    y = torch.linspace(0.8, 2.5, N, device=device, dtype=torch.float32)

    def ref_cd(u, y, dt):
        metric_scale = 1.0 / (y ** 3 + 1e-5)
        u_pad = torch.nn.functional.pad(u.unsqueeze(0).unsqueeze(0), (2, 2), mode='replicate')[0, 0]

        ux = 0.5 * (u_pad[3:-1] - u_pad[1:-3])
        uxxx = 0.5 * (u_pad[4:] - 2*u_pad[3:-1] + 2*u_pad[1:-3] - u_pad[:-4])

        ux_cube = ux ** 3
        u_sq = u ** 2
        nl_ratio = 0.125 * ux_cube / (u_sq + 1e-4)

        rhs = (0.25 * uxxx - 1.5 * u_sq * ux + nl_ratio) * metric_scale
        return u + dt * rhs

    for _ in range(20):
        ref_out = ref_cd(u, y, dt)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 100
    for _ in range(iters):
        ref_out = ref_cd(u, y, dt)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out_u = torch.empty_like(u)
    BLOCK_N = 512
    grid = ((N + BLOCK_N - 1) // BLOCK_N,)

    for _ in range(20):
        fused_poincare_calogero_degasperis_kernel[grid](
            u, out_u, y, dt, N, BLOCK_N
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_poincare_calogero_degasperis_kernel[grid](
            u, out_u, y, dt, N, BLOCK_N
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    max_err = torch.max(torch.abs(out_u - ref_out)).item()
    speedup = ref_time / triton_time
    throughput = N / triton_time / 1e6

    print(f"=== Workstation Benchmark: Cycle 220 Poincaré Calogero-Degasperis Flow ===")
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
