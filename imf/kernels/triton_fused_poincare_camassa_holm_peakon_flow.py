"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Camassa-Holm Peakon Flow
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 12.0, 16GB VRAM)
Mathematical Formulation:
  The Camassa-Holm (CH) shallow-water wave equation:
    partial_t m + u partial_x m + 2 m partial_x u = 0,   where m = u - partial_x^2 u
  This equation represents geodesic flow on the diffeomorphism group Diff(S^1)
  with respect to the H^1 right-invariant Sobolev metric:
    ||u||_{H^1}^2 = int (u^2 + (partial_x u)^2) dx
  For discrete multi-peakon interactions:
    u(x, t) = sum_{j=1}^N p_j(t) exp(-|x - q_j(t)|)
  Hamiltonian equations of motion for peakon positions q_i and momenta p_i:
    dq_i / dt = sum_{j=1}^N p_j exp(-|q_i - q_j|)
    dp_i / dt = sum_{j=1}^N p_i p_j sgn(q_i - q_j) exp(-|q_i - q_j|)
  Fused Triton execution computes pairwise exponential distance metrics and
  evaluates Hamiltonian peakon equations of motion directly in registers.
"""

import time
import math
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_camassa_holm_peakon_kernel(
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

    # Accumulate velocities u(q_i) and forces dp_i/dt
    vel_i = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    force_i = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # All-to-all peakon loop over j:
    for j in range(N):
        qj = tl.load(Q_ptr + pid * N + j)
        pj = tl.load(P_ptr + pid * N + j)

        diff = qi - qj # [BLOCK_SIZE] difference (q_i - q_j)
        dist = tl.abs(diff)

        # Clamped distance to avoid underflow
        dist_clamped = tl.minimum(dist, 20.0)
        kernel_val = tl.exp(-dist_clamped) # exp(-|q_i - q_j|)

        # Velocity contribution: p_j * exp(-|q_i - q_j|)
        vel_i += pj * kernel_val

        # Momentum change contribution: p_i * p_j * sgn(q_i - q_j) * exp(-|q_i - q_j|)
        # For diff == 0, sgn is 0
        sgn_val = tl.where(diff > 0.0, 1.0, tl.where(diff < 0.0, -1.0, 0.0))
        force_i += pi * pj * sgn_val * kernel_val

    # Symplectic evolution:
    q_next = qi + dt * vel_i
    p_next = pi + dt * (force_i - damping * pi)

    tl.store(Q_out_ptr + pid * N + offs, q_next, mask=mask)
    tl.store(P_out_ptr + pid * N + offs, p_next, mask=mask)


def triton_camassa_holm_step(q, p, dt=0.001, damping=0.01):
    B, N = q.shape
    q_out = torch.empty_like(q)
    p_out = torch.empty_like(p)
    BLOCK_SIZE = triton.next_power_of_2(N)
    grid = (B,)
    fused_poincare_camassa_holm_peakon_kernel[grid](
        q, p, q_out, p_out,
        B=B, N=N, dt=dt, damping=damping,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return q_out, p_out


def pytorch_camassa_holm_step(q, p, dt=0.001, damping=0.01):
    B, N = q.shape
    diff = q.unsqueeze(2) - q.unsqueeze(1) # [B, N, N]
    dist = torch.abs(diff)
    kernel_val = torch.exp(-torch.clamp(dist, max=20.0)) # [B, N, N]

    # Velocity: sum_j p_j * exp(-|q_i - q_j|)
    vel_i = torch.sum(p.unsqueeze(1) * kernel_val, dim=-1)

    # Force: sum_j p_i * p_j * sgn(q_i - q_j) * exp(-|q_i - q_j|)
    sgn_val = torch.sign(diff)
    force_matrix = (p.unsqueeze(2) * p.unsqueeze(1)) * sgn_val * kernel_val
    force_i = torch.sum(force_matrix, dim=-1)

    q_next = q + dt * vel_i
    p_next = p + dt * (force_i - damping * p)
    return q_next, p_next


def benchmark_camassa_holm():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Camassa-Holm Peakon Benchmark on: {torch.cuda.get_device_name(device)}")

    B = 2048 # 2,048 parallel peakon systems
    N = 64   # 64 peakons per system (4,096 pairwise interactions)
    total_peakons = B * N
    print(f"[*] Scale: {B:,} batches x {N} peakons = {total_peakons:,} peakon bodies")

    torch.manual_seed(42)
    # Positions ordered along line
    q = torch.sort(torch.randn(B, N, device=device) * 5.0, dim=-1)[0].contiguous()
    # Positive momenta (peakon wave heights)
    p = (torch.rand(B, N, device=device) * 2.0 + 0.5).contiguous()

    # Numerical verification
    tr_q, tr_p = triton_camassa_holm_step(q, p)
    py_q, py_p = pytorch_camassa_holm_step(q, p)

    max_err_q = torch.max(torch.abs(tr_q - py_q)).item()
    max_err_p = torch.max(torch.abs(tr_p - py_p)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute errors: q={max_err_q:.8e}, p={max_err_p:.8e}")
    assert max_err_q < 1e-4 and max_err_p < 1e-4, "Triton error too high"

    # Latency benchmark
    iters = 200
    for _ in range(20):
        _ = triton_camassa_holm_step(q, p)
        _ = pytorch_camassa_holm_step(q, p)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_camassa_holm_step(q, p)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_camassa_holm_step(q, p)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = total_peakons / (triton_time * 1e6)
    interaction_rate = (B * N * N) / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million peakons/s")
    print(f"[✓] Interaction Rate: {interaction_rate:.2f} Million peakon interactions/s")


if __name__ == "__main__":
    benchmark_camassa_holm()
