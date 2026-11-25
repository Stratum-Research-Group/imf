"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Benjamin-Ono Soliton (Tiled Matrix-Vector GEMV)
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 12.0, 16GB VRAM)
"""

import time
import math
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_benjamin_ono_tiled_kernel(
    U_ptr,          # [B, N] Soliton field u(x)
    Out_ptr,        # [B, N] Output evolved field
    Cot_matrix_ptr, # [N, N] Precomputed cotangent convolution kernel
    B: tl.constexpr,# Batch of independent 1D boundaries
    N: tl.constexpr,# Spatial grid resolution (e.g. 512, power of 2)
    dt: tl.float32,
    dx: tl.float32,
    damping: tl.float32,
    BLOCK_M: tl.constexpr, # Number of rows (i indices) processed by this CTA
    BLOCK_K: tl.constexpr, # Reduction tile size along j
):
    pid_b = tl.program_id(0) # Batch index [0, B)
    pid_m = tl.program_id(1) # Tile index along spatial dimension N

    offs_i = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
    mask_i = offs_i < N

    # Load u_i
    u_i = tl.load(U_ptr + pid_b * N + offs_i, mask=mask_i, other=0.0)

    # Periodic neighbors for advection
    prev_i = (offs_i - 1 + N) % N
    next_i = (offs_i + 1) % N
    u_prev = tl.load(U_ptr + pid_b * N + prev_i, mask=mask_i, other=0.0)
    u_next = tl.load(U_ptr + pid_b * N + next_i, mask=mask_i, other=0.0)

    inv_2dx = 0.5 / dx
    inv_dx2 = 1.0 / (dx * dx)

    # 1. Non-linear advection: u * du/dx
    du_dx = (u_next - u_prev) * inv_2dx
    advection = u_i * du_dx

    # Accumulator for Hilbert transform H(d2u)_i = sum_j Cot_{i, j} * d2u_j
    acc = tl.zeros([BLOCK_M], dtype=tl.float32)

    # Loop over j in tiles of BLOCK_K
    for k_start in range(0, N, BLOCK_K):
        offs_k = k_start + tl.arange(0, BLOCK_K)
        mask_k = offs_k < N

        # Compute d2u along tile k
        u_k = tl.load(U_ptr + pid_b * N + offs_k, mask=mask_k, other=0.0)
        prev_k = (offs_k - 1 + N) % N
        next_k = (offs_k + 1) % N
        u_k_prev = tl.load(U_ptr + pid_b * N + prev_k, mask=mask_k, other=0.0)
        u_k_next = tl.load(U_ptr + pid_b * N + next_k, mask=mask_k, other=0.0)
        d2u_k = (u_k_next - 2.0 * u_k + u_k_prev) * inv_dx2

        # Load 2D tile from Cot_matrix: [BLOCK_M, BLOCK_K]
        cot_tile = tl.load(Cot_matrix_ptr + offs_i[:, None] * N + offs_k[None, :],
                           mask=mask_i[:, None] & mask_k[None, :], other=0.0)

        # Matrix-vector multiplication tile
        acc += tl.sum(cot_tile * d2u_k[None, :], axis=1)

    # du/dt update
    du_dt = -advection - acc - damping * u_i
    u_new = u_i + dt * du_dt

    tl.store(Out_ptr + pid_b * N + offs_i, u_new, mask=mask_i)


def precompute_cot_matrix(N, device):
    indices = torch.arange(N, device=device).float()
    diff = indices.unsqueeze(1) - indices.unsqueeze(0)
    mask = diff != 0
    theta = math.pi * diff / N
    cot_val = torch.cos(theta) / (torch.sin(theta) + 1e-7)
    cot_matrix = torch.where(mask, cot_val / (2.0 * N), torch.zeros_like(cot_val))
    return cot_matrix.contiguous()


def triton_benjamin_ono_step(u, cot_matrix, dt=0.0005, dx=0.05, damping=0.01):
    B, N = u.shape
    out = torch.empty_like(u)
    BLOCK_M = 64
    BLOCK_K = 64
    grid = (B, triton.cdiv(N, BLOCK_M))
    fused_poincare_benjamin_ono_tiled_kernel[grid](
        u, out, cot_matrix,
        B=B, N=N, dt=dt, dx=dx, damping=damping,
        BLOCK_M=BLOCK_M, BLOCK_K=BLOCK_K,
    )
    return out


def pytorch_benjamin_ono_step(u, cot_matrix, dt=0.0005, dx=0.05, damping=0.01):
    inv_2dx = 0.5 / dx
    inv_dx2 = 1.0 / (dx * dx)

    u_next = torch.roll(u, shifts=-1, dims=-1)
    u_prev = torch.roll(u, shifts=1, dims=-1)

    advection = u * (u_next - u_prev) * inv_2dx
    d2u = (u_next - 2.0 * u + u_prev) * inv_dx2

    h_d2u = torch.matmul(d2u, cot_matrix.t())
    du_dt = -advection - h_d2u - damping * u
    return u + dt * du_dt


def benchmark_benjamin_ono():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Benjamin-Ono Soliton Benchmark on: {torch.cuda.get_device_name(device)}")

    B = 256
    N = 512
    total_nodes = B * N
    print(f"[*] Scale: {B} batches x {N} spatial nodes = {total_nodes:,} field points")

    cot_matrix = precompute_cot_matrix(N, device)

    torch.manual_seed(42)
    x = torch.linspace(-10, 10, N, device=device).unsqueeze(0)
    c = 1.5
    u_single = 4.0 * c / (1.0 + (c * x)**2)
    u = u_single.repeat(B, 1).contiguous()

    # Numerical correctness check
    triton_out = triton_benjamin_ono_step(u, cot_matrix)
    torch_out = pytorch_benjamin_ono_step(u, cot_matrix)

    max_err = torch.max(torch.abs(triton_out - torch_out)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute error: {max_err:.8e}")
    assert max_err < 1e-4, f"Triton error too high: {max_err}"

    # Latency benchmark
    iters = 200
    for _ in range(20):
        _ = triton_benjamin_ono_step(u, cot_matrix)
        _ = pytorch_benjamin_ono_step(u, cot_matrix)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_benjamin_ono_step(u, cot_matrix)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_benjamin_ono_step(u, cot_matrix)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = total_nodes / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million field nodes/s")


if __name__ == "__main__":
    benchmark_benjamin_ono()
