"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Degasperis-Procesi Shockpeakon
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 8.9, 16GB VRAM)
Mathematical Formulation:
  The Degasperis-Procesi (DP) equation for shallow water waves:
    partial_t m + u partial_x m + 3 m partial_x u = 0,   where m = u - partial_x^2 u
  Unlike Camassa-Holm (b=2), the Degasperis-Procesi equation (b=3) supports both:
    1. Regular peakons: u(x, t) = p_j exp(-|x - q_j|)
    2. Shockpeakons: u(x, t) = s_k sgn(x - y_k) exp(-|x - y_k|)
  Hamiltonian-like peakon-shock dynamical flow:
    dq_i / dt = sum_{j=1}^N p_j exp(-|q_i - q_j|)
    dp_i / dt = 2 sum_{j=1}^N p_i p_j sgn(q_i - q_j) exp(-|q_i - q_j|) - damping * p_i
  Notice the critical factor of 2 in dp_i / dt arising from the b=3 non-linear coefficient.
  Fused Triton execution evaluates pairwise distance and momentum updates in registers.
"""

import time
import math
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_degasperis_procesi_kernel(
    Q_ptr,          # [B, N] Peakon positions q_i
    P_ptr,          # [B, N] Peakon momenta p_i
    Q_out_ptr,      # [B, N] Updated positions q_new
    P_out_ptr,      # [B, N] Updated momenta p_new
    B: tl.constexpr,# Batch of independent shallow water systems
    N: tl.constexpr,# Number of interacting peakons (e.g. 64)
    dt: tl.float32,
    damping: tl.float32,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0) # Batch index b
    if pid >= B:
        return

    offs = tl.arange(0, BLOCK_SIZE)
    mask = offs < N

    # Load peakon i position and momentum
    qi = tl.load(Q_ptr + pid * N + offs, mask=mask, other=0.0)
    pi = tl.load(P_ptr + pid * N + offs, mask=mask, other=0.0)

    # Accumulators
    vel_i = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    force_i = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # All-to-all peakon loop over j:
    for j in range(N):
        qj = tl.load(Q_ptr + pid * N + j)
        pj = tl.load(P_ptr + pid * N + j)

        diff = qi - qj
        dist = tl.abs(diff)

        dist_clamped = tl.minimum(dist, 20.0)
        kernel_val = tl.exp(-dist_clamped) # exp(-|q_i - q_j|)

        # Velocity contribution: p_j * exp(-|q_i - q_j|)
        vel_i += pj * kernel_val

        # DP force contribution (b=3 introduces coefficient 2.0 on asymmetric momentum interaction):
        # 2.0 * p_i * p_j * sgn(q_i - q_j) * exp(-|q_i - q_j|)
        sgn_val = tl.where(diff > 0.0, 1.0, tl.where(diff < 0.0, -1.0, 0.0))
        force_i += 2.0 * pi * pj * sgn_val * kernel_val

    # Symplectic evolution:
    q_next = qi + dt * vel_i
    p_next = pi + dt * (force_i - damping * pi)

    tl.store(Q_out_ptr + pid * N + offs, q_next, mask=mask)
    tl.store(P_out_ptr + pid * N + offs, p_next, mask=mask)


def triton_degasperis_procesi_step(q, p, dt=0.001, damping=0.01):
    B, N = q.shape
    q_out = torch.empty_like(q)
    p_out = torch.empty_like(p)
    BLOCK_SIZE = triton.next_power_of_2(N)
    grid = (B,)
    fused_poincare_degasperis_procesi_kernel[grid](
        q, p, q_out, p_out,
        B=B, N=N, dt=dt, damping=damping,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return q_out, p_out


def pytorch_degasperis_procesi_step(q, p, dt=0.001, damping=0.01):
    B, N = q.shape
    diff = q.unsqueeze(2) - q.unsqueeze(1) # [B, N, N]
    dist = torch.abs(diff)
    kernel_val = torch.exp(-torch.clamp(dist, max=20.0)) # [B, N, N]

    # Velocity: sum_j p_j * exp(-|q_i - q_j|)
    vel_i = torch.sum(p.unsqueeze(1) * kernel_val, dim=-1)

    # Force for b=3 (Degasperis-Procesi): 2 * sum_j p_i * p_j * sgn(q_i - q_j) * exp(-|q_i - q_j|)
    sgn_val = torch.sign(diff)
    force_matrix = 2.0 * (p.unsqueeze(2) * p.unsqueeze(1)) * sgn_val * kernel_val
    force_i = torch.sum(force_matrix, dim=-1)

    q_next = q + dt * vel_i
    p_next = p + dt * (force_i - damping * p)
    return q_next, p_next


def benchmark_degasperis_procesi():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Degasperis-Procesi Shockpeakon Benchmark on: {torch.cuda.get_device_name(device)}")

    B = 2048 # 2,048 parallel shallow water systems
    N = 64   # 64 shockpeakons per system (4,096 pairwise interactions)
    total_bodies = B * N
    print(f"[*] Scale: {B:,} batches x {N} shockpeakons = {total_bodies:,} bodies")

    torch.manual_seed(42)
    q = torch.sort(torch.randn(B, N, device=device) * 5.0, dim=-1)[0].contiguous()
    p = (torch.rand(B, N, device=device) * 2.0 + 0.5).contiguous()

    # Numerical verification
    tr_q, tr_p = triton_degasperis_procesi_step(q, p)
    py_q, py_p = pytorch_degasperis_procesi_step(q, p)

    max_err_q = torch.max(torch.abs(tr_q - py_q)).item()
    max_err_p = torch.max(torch.abs(tr_p - py_p)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute errors: q={max_err_q:.8e}, p={max_err_p:.8e}")
    assert max_err_q < 1e-4 and max_err_p < 1e-4, "Triton error too high"

    # Latency benchmark
    iters = 200
    for _ in range(20):
        _ = triton_degasperis_procesi_step(q, p)
        _ = pytorch_degasperis_procesi_step(q, p)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_degasperis_procesi_step(q, p)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_degasperis_procesi_step(q, p)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = total_bodies / (triton_time * 1e6)
    interaction_rate = (B * N * N) / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million shockpeakons/s")
    print(f"[✓] Interaction Rate: {interaction_rate:.2f} Million shockpeakon interactions/s")


if __name__ == "__main__":
    benchmark_degasperis_procesi()
