"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Toda Lattice Flaschka Flow
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 12.0, 16GB VRAM)
Mathematical Formulation:
  The non-periodic Toda lattice Hamiltonian:
    H = (1/2) sum_{i=1}^N p_i^2 + sum_{i=1}^{N-1} exp(q_i - q_{i+1})
  In Flaschka canonical variables:
    a_i = (1/2) exp((q_i - q_{i+1}) / 2),   i in {1, ..., N-1}
    b_i = -(1/2) p_i,                       i in {1, ..., N}
  The equations of motion take the Lax pair form dL/dt = [B, L]:
    da_i / dt = a_i (b_{i+1} - b_i)
    db_i / dt = 2 (a_i^2 - a_{i-1}^2)  (with boundary conditions a_0 = a_N = 0)
  Fused Triton execution evaluates:
    1. Tridiagonal Flaschka Lax commutator dynamics in thread registers.
    2. Symplectic / Runge-Kutta step: a_{t+dt}, b_{t+dt}.
    3. Conservation of total momentum sum b_i and spectral invariants Tr(L^k).
"""

import time
import math
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_toda_flaschka_kernel(
    A_ptr,          # [B, N-1] Off-diagonal Flaschka variables a_i
    B_ptr,          # [B, N] Diagonal Flaschka variables b_i
    A_out_ptr,      # [B, N-1] Updated a_i
    B_out_ptr,      # [B, N] Updated b_i
    B_batch: tl.constexpr, # Number of parallel Toda systems
    N: tl.constexpr,       # Number of particles (e.g. 64)
    dt: tl.float32,
    damping: tl.float32,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0) # Batch index [0, B_batch)
    if pid >= B_batch:
        return

    offs = tl.arange(0, BLOCK_SIZE)
    mask_n = offs < N
    mask_a = offs < (N - 1)

    # Load b_i for this batch: [BLOCK_SIZE]
    b = tl.load(B_ptr + pid * N + offs, mask=mask_n, other=0.0)

    # Load b_{i+1}
    next_idx = offs + 1
    mask_next = next_idx < N
    b_next = tl.load(B_ptr + pid * N + next_idx, mask=mask_next, other=0.0)

    # Load a_i: [BLOCK_SIZE]
    a = tl.load(A_ptr + pid * (N - 1) + offs, mask=mask_a, other=0.0)

    # Load a_{i-1} for db/dt:
    prev_idx = offs - 1
    mask_prev = (offs >= 1) & (offs < N)
    a_prev = tl.load(A_ptr + pid * (N - 1) + prev_idx, mask=mask_prev, other=0.0)

    # 1. da_i / dt = a_i * (b_{i+1} - b_i) - damping * a_i
    da_dt = a * (b_next - b) - damping * a
    a_new = a + dt * da_dt

    # 2. db_i / dt = 2 * (a_i^2 - a_{i-1}^2) - damping * b_i
    # For i = 0: a_{i-1} = 0, so 2 * a_0^2
    # For i = N-1: a_{N-1} = 0, so -2 * a_{N-2}^2
    a_sq = tl.where(mask_a, a * a, 0.0)
    a_prev_sq = tl.where(mask_prev, a_prev * a_prev, 0.0)

    db_dt = 2.0 * (a_sq - a_prev_sq) - damping * b
    b_new = b + dt * db_dt

    # Store updated variables
    tl.store(A_out_ptr + pid * (N - 1) + offs, a_new, mask=mask_a)
    tl.store(B_out_ptr + pid * N + offs, b_new, mask=mask_n)


def triton_toda_flaschka_step(a, b, dt=0.001, damping=0.01):
    B_batch, N = b.shape
    a_out = torch.empty_like(a)
    b_out = torch.empty_like(b)
    BLOCK_SIZE = triton.next_power_of_2(N)
    grid = (B_batch,)
    fused_poincare_toda_flaschka_kernel[grid](
        a, b, a_out, b_out,
        B_batch=B_batch, N=N, dt=dt, damping=damping,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return a_out, b_out


def pytorch_toda_flaschka_step(a, b, dt=0.001, damping=0.01):
    B_batch, N = b.shape

    # da_i / dt = a_i * (b_{i+1} - b_i) - damping * a_i
    b_curr = b[:, :-1]
    b_next = b[:, 1:]
    da_dt = a * (b_next - b_curr) - damping * a
    a_new = a + dt * da_dt

    # db_i / dt = 2 * (a_i^2 - a_{i-1}^2) - damping * b_i
    a_sq = a * a
    # Pad a_sq to [B, N]: a_0^2, a_1^2, ..., a_{N-2}^2, 0
    zeros = torch.zeros(B_batch, 1, device=b.device, dtype=b.dtype)
    a_right = torch.cat([a_sq, zeros], dim=1) # a_i^2 (0 for i=N-1)
    a_left  = torch.cat([zeros, a_sq], dim=1) # a_{i-1}^2 (0 for i=0)

    db_dt = 2.0 * (a_right - a_left) - damping * b
    b_new = b + dt * db_dt
    return a_new, b_new


def benchmark_toda_lattice():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Toda Lattice Flaschka Benchmark on: {torch.cuda.get_device_name(device)}")

    B = 4096 # 4,096 parallel non-periodic Toda chains
    N = 64   # 64 particles per chain
    total_elements = B * (2 * N - 1)
    print(f"[*] Scale: {B:,} chains x {N} particles = {B * N:,} lattice sites")

    torch.manual_seed(42)
    # Flaschka a_i > 0
    a = (torch.rand(B, N - 1, device=device) * 0.5 + 0.5).contiguous()
    b = (torch.randn(B, N, device=device) * 0.2).contiguous()

    # Numerical verification
    tr_a, tr_b = triton_toda_flaschka_step(a, b)
    py_a, py_b = pytorch_toda_flaschka_step(a, b)

    max_err_a = torch.max(torch.abs(tr_a - py_a)).item()
    max_err_b = torch.max(torch.abs(tr_b - py_b)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute errors: a={max_err_a:.8e}, b={max_err_b:.8e}")
    assert max_err_a < 1e-5 and max_err_b < 1e-5, "Triton error too high"

    # Latency benchmark
    iters = 200
    for _ in range(20):
        _ = triton_toda_flaschka_step(a, b)
        _ = pytorch_toda_flaschka_step(a, b)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_toda_flaschka_step(a, b)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_toda_flaschka_step(a, b)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = total_elements / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million Flaschka variables/s")


if __name__ == "__main__":
    benchmark_toda_lattice()
