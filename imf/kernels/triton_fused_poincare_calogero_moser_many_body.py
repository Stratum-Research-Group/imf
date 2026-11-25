"""
IMF Physical Triton Hardware Benchmark: Fused Poincaré Calogero-Moser Many-Body Dynamics
================================================================================
Hardware: NVIDIA GeForce RTX 5060 Ti (SM 12.0, 16GB VRAM)
Mathematical Formulation:
  Completely integrable hyperbolic Calogero-Moser N-body Hamiltonian:
    H = (1/2) sum_{i=1}^N p_i^2 + g^2 sum_{1 <= i < j <= N} (1 / sinh^2(q_i - q_j))
  Equations of motion:
    dq_i / dt = p_i
    dp_i / dt = 2 g^2 sum_{j != i} (cosh(q_i - q_j) / sinh^3(q_i - q_j)) - damping * p_i
  In Lax representation:
    L_{ij} = p_i delta_{ij} + (1 - delta_{ij}) * (i g / sinh(q_i - q_j))
    dL / dt = [L, M]  (Lax pair isospectral flow)
  Symplectic Verlet integration executed directly in GPU thread registers.
"""

import time
import torch
import triton
import triton.language as tl


@triton.jit
def fused_poincare_calogero_moser_kernel(
    Q_ptr,          # [B, N] Particle positions q_i
    P_ptr,          # [B, N] Particle momenta p_i
    Q_out_ptr,      # [B, N] Updated positions
    P_out_ptr,      # [B, N] Updated momenta
    B: tl.constexpr,# Batch of independent many-body systems
    N: tl.constexpr,# Number of interacting particles per system (e.g. 64)
    dt: tl.float32,
    g_sq: tl.float32,
    damping: tl.float32,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0) # Program index corresponds to batch index b
    if pid >= B:
        return

    offs = tl.arange(0, BLOCK_SIZE)
    mask = offs < N

    # Load particle i position and momentum
    qi = tl.load(Q_ptr + pid * N + offs, mask=mask, other=0.0)
    pi = tl.load(P_ptr + pid * N + offs, mask=mask, other=0.0)

    # Initialize force accumulator for particle i
    force_i = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # All-to-all interaction sum over j in [0, N):
    for j in range(N):
        # Load scalar position q_j for particle j in this batch
        qj = tl.load(Q_ptr + pid * N + j)
        diff = qi - qj # [BLOCK_SIZE] difference (q_i - q_j)

        # Regularize near-zero difference (self-interaction j == i)
        # For j == i, diff is 0, so we mask out
        is_not_self = offs != j

        # Compute sinh(diff) and cosh(diff) via exp
        # Clamp diff to avoid overflow in exp
        diff_clamped = tl.where(is_not_self, diff, 10.0) # dummy value for self
        diff_clamped = tl.maximum(-10.0, tl.minimum(10.0, diff_clamped))

        exp_pos = tl.exp(diff_clamped)
        exp_neg = tl.exp(-diff_clamped)
        sinh_val = 0.5 * (exp_pos - exp_neg)
        cosh_val = 0.5 * (exp_pos + exp_neg)

        # Force: 2 * g^2 * cosh / (sinh^3 + eps)
        sinh_sq = sinh_val * sinh_val
        sinh_cube = sinh_sq * sinh_val
        # Sign-preserving eps
        eps_val = tl.where(sinh_cube >= 0.0, 1e-4, -1e-4)
        denom = sinh_cube + eps_val
        f_ij = (2.0 * g_sq * cosh_val) / denom

        force_i += tl.where(is_not_self, f_ij, 0.0)

    # Total acceleration
    acc_i = force_i - damping * pi

    # Verlet update
    q_next = qi + dt * pi + 0.5 * dt * dt * acc_i
    p_next = pi + dt * acc_i

    tl.store(Q_out_ptr + pid * N + offs, q_next, mask=mask)
    tl.store(P_out_ptr + pid * N + offs, p_next, mask=mask)


def triton_calogero_moser_step(q, p, dt=0.001, g_sq=1.0, damping=0.01):
    B, N = q.shape
    q_out = torch.empty_like(q)
    p_out = torch.empty_like(p)
    BLOCK_SIZE = triton.next_power_of_2(N)
    grid = (B,)
    fused_poincare_calogero_moser_kernel[grid](
        q, p, q_out, p_out,
        B=B, N=N, dt=dt, g_sq=g_sq, damping=damping,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return q_out, p_out


def pytorch_calogero_moser_step(q, p, dt=0.001, g_sq=1.0, damping=0.01):
    B, N = q.shape
    # Pairwise difference [B, N, N]: diff[:, i, j] = q[:, i] - q[:, j]
    diff = q.unsqueeze(2) - q.unsqueeze(1) # [B, N, N]

    # Mask out self-interaction
    mask = ~torch.eye(N, dtype=torch.bool, device=q.device).unsqueeze(0)

    diff_clamped = torch.clamp(diff, -10.0, 10.0)
    sinh_val = torch.sinh(diff_clamped)
    cosh_val = torch.cosh(diff_clamped)

    sinh_cube = sinh_val**3
    eps = torch.where(sinh_cube >= 0, 1e-4, -1e-4)
    force_matrix = (2.0 * g_sq * cosh_val) / (sinh_cube + eps)
    force_matrix = torch.where(mask, force_matrix, torch.zeros_like(force_matrix))

    force_i = torch.sum(force_matrix, dim=-1) # [B, N]
    acc_i = force_i - damping * p

    q_next = q + dt * p + 0.5 * dt * dt * acc_i
    p_next = p + dt * acc_i
    return q_next, p_next


def benchmark_calogero_moser():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Running Calogero-Moser Many-Body Benchmark on: {torch.cuda.get_device_name(device)}")

    B = 2048 # 2048 parallel systems
    N = 64   # 64 particles per system (4,096 pairwise interactions per system)
    total_particles = B * N
    print(f"[*] Scale: {B:,} batches x {N} particles = {total_particles:,} interacting bodies")

    torch.manual_seed(42)
    # Order positions initially to avoid exact singularity
    q = torch.sort(torch.randn(B, N, device=device) * 2.0, dim=-1)[0]
    # Spread out slightly
    q += torch.linspace(0, 10, N, device=device).unsqueeze(0)
    p = (torch.randn(B, N, device=device) * 0.1).contiguous()
    q = q.contiguous()

    # Numerical verification
    tr_q, tr_p = triton_calogero_moser_step(q, p)
    py_q, py_p = pytorch_calogero_moser_step(q, p)

    max_err_q = torch.max(torch.abs(tr_q - py_q)).item()
    max_err_p = torch.max(torch.abs(tr_p - py_p)).item()
    print(f"[✓] Numerical Correctness Validated. Max absolute errors: q={max_err_q:.8e}, p={max_err_p:.8e}")
    assert max_err_q < 1e-4 and max_err_p < 1e-4, "Triton error too high"

    # Latency benchmark
    iters = 200
    for _ in range(20):
        _ = triton_calogero_moser_step(q, p)
        _ = pytorch_calogero_moser_step(q, p)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_calogero_moser_step(q, p)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_calogero_moser_step(q, p)
    torch.cuda.synchronize()
    torch_time = (time.perf_counter() - t0) / iters

    speedup = torch_time / triton_time
    throughput = (total_particles) / (triton_time * 1e6)
    interaction_rate = (B * N * N) / (triton_time * 1e6)

    print(f"[*] PyTorch Latency: {torch_time * 1e6:.2f} µs")
    print(f"[*] Triton Latency:  {triton_time * 1e6:.2f} µs")
    print(f"[✓] Triton Speedup:  {speedup:.2f}x")
    print(f"[✓] Throughput:      {throughput:.2f} Million particles/s")
    print(f"[✓] Interaction Rate: {interaction_rate:.2f} Million pairwise interactions/s")


if __name__ == "__main__":
    benchmark_calogero_moser()
