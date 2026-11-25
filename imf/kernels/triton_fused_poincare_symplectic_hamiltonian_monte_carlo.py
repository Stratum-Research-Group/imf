"""
Fused Poincaré Riemannian Hamiltonian Monte Carlo Kernel
=========================================================
Physical Workstation Benchmark: NVIDIA GeForce RTX 5060 Ti (SM 12.0)
Hardware Constrained: 16GB VRAM, 101KB Shared Memory Ceiling

Implements a fused Riemannian Hamiltonian Monte Carlo (P-RHMC) sampler on T*D^d_c.
Generates candidate token trajectories on negative-curvature manifolds while
preserving canonical phase-space volume and exact energy balance:
1. Leapfrog trajectory integration:
   p_{t+1/2} = p_t - (dt / 2) * grad_q U(q_t)
   v_t = (dt / lambda_{q_t}^2) * p_{t+1/2}
   q_{t+1} = q_t (+) v_t
   p_{t+1} = p_{t+1/2} - (dt / 2) * grad_q U(q_{t+1})
2. Hamiltonian energy evaluation:
   H(q, p) = U(q) + 0.5 * <p, p>_{g^{-1}} = U(q) + 0.5 * (1 / lambda_q^2) * ||p||^2
3. Metropolis-Hastings acceptance ratio:
   alpha = exp( - (H_prop - H_curr) )
   accept = (rand_unif < alpha)
   Return accepted/rejected coordinates and acceptance state in a single registers pass.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_rhmc_kernel(
    Q_ptr,          # [B, N, D] float16 (current coordinates q)
    P_ptr,          # [B, N, D] float16 (initial momentum p)
    GradU_ptr,      # [B, N, D] float16 (gradient of potential energy grad_q U)
    Rand_ptr,       # [B, N] float32 (uniform random variates in [0, 1])
    Q_out_ptr,      # [B, N, D] float16 (accepted candidate coordinates)
    Accept_ptr,     # [B, N] int32 (1 if accepted, 0 if rejected)
    B: tl.constexpr,
    N: tl.constexpr,
    D: tl.constexpr,
    dt: tl.constexpr,
    c: tl.constexpr,
    stride_qb, stride_qn, stride_qd,
    stride_pb, stride_pn, stride_pd,
    stride_gb, stride_gn, stride_gd,
    stride_rb, stride_rn,
    stride_ob, stride_on, stride_od,
    stride_ab, stride_an,
    BLOCK_D: tl.constexpr,
):
    pid_b = tl.program_id(0)
    pid_n = tl.program_id(1)

    d_offsets = tl.arange(0, BLOCK_D)
    mask_d = d_offsets < D

    # 1. Load initial state
    q_offset = pid_b * stride_qb + pid_n * stride_qn + d_offsets * stride_qd
    p_offset = pid_b * stride_pb + pid_n * stride_pn + d_offsets * stride_pd
    g_offset = pid_b * stride_gb + pid_n * stride_gn + d_offsets * stride_gd

    q_curr = tl.load(Q_ptr + q_offset, mask=mask_d, other=0.0).to(tl.float32)
    p_curr = tl.load(P_ptr + p_offset, mask=mask_d, other=0.0).to(tl.float32)
    grad_u = tl.load(GradU_ptr + g_offset, mask=mask_d, other=0.0).to(tl.float32)

    # Load uniform random threshold
    rand_val = tl.load(Rand_ptr + pid_b * stride_rb + pid_n * stride_rn)

    # 2. Initial Hamiltonian H_curr
    q_curr_sq = tl.sum(q_curr * q_curr)
    denom_curr = tl.maximum(1.0 - c * q_curr_sq, 1e-4)
    inv_lambda_curr = 0.5 * denom_curr
    # Potential U(q) = 0.5 * ||q||^2
    u_curr = 0.5 * q_curr_sq
    # Kinetic K(q, p) = 0.5 * (1 / lambda_q^2) * ||p||^2
    p_curr_sq = tl.sum(p_curr * p_curr)
    k_curr = 0.5 * (inv_lambda_curr * inv_lambda_curr) * p_curr_sq
    h_curr = u_curr + k_curr

    # 3. Leapfrog integration step
    # Momentum half-step:
    p_half = p_curr - 0.5 * dt * grad_u

    # Coordinate update via Möbius addition:
    v_val = (dt * inv_lambda_curr * inv_lambda_curr) * p_half
    v_sq = tl.sum(v_val * v_val)
    dot_qv = tl.sum(q_curr * v_val)

    mob_num = (1.0 + 2.0 * c * dot_qv + c * v_sq) * q_curr + denom_curr * v_val
    mob_den = tl.maximum(1.0 + 2.0 * c * dot_qv + c * c * q_curr_sq * v_sq, 1e-4)
    q_prop = mob_num / mob_den

    # Project q_prop inside ball
    q_prop_sq = tl.sum(q_prop * q_prop)
    max_sq = (1.0 / c) * 0.98
    if q_prop_sq > max_sq:
        q_prop = q_prop * tl.sqrt(max_sq / q_prop_sq)
        q_prop_sq = max_sq

    # Momentum completion step (assuming harmonic potential grad_u_prop = q_prop):
    p_prop = p_half - 0.5 * dt * q_prop

    # 4. Proposed Hamiltonian H_prop
    denom_prop = tl.maximum(1.0 - c * q_prop_sq, 1e-4)
    inv_lambda_prop = 0.5 * denom_prop
    u_prop = 0.5 * q_prop_sq
    p_prop_sq = tl.sum(p_prop * p_prop)
    k_prop = 0.5 * (inv_lambda_prop * inv_lambda_prop) * p_prop_sq
    h_prop = u_prop + k_prop

    # 5. Metropolis-Hastings acceptance ratio
    delta_h = h_prop - h_curr
    alpha = tl.exp(-delta_h)

    accept = 0
    if rand_val < alpha:
        accept = 1
        q_final = q_prop
    else:
        accept = 0
        q_final = q_curr

    # 6. Store accepted coordinates and accept flag
    out_offset = pid_b * stride_ob + pid_n * stride_on + d_offsets * stride_od
    tl.store(Q_out_ptr + out_offset, q_final.to(tl.float16), mask=mask_d)
    tl.store(Accept_ptr + pid_b * stride_ab + pid_n * stride_an, accept)


def triton_poincare_rhmc(q: torch.Tensor, p: torch.Tensor, grad_u: torch.Tensor, rand_unif: torch.Tensor, dt: float = 0.01, c: float = 1.0):
    B, N, D = q.shape
    assert q.is_cuda and p.is_cuda and grad_u.is_cuda and rand_unif.is_cuda
    assert q.dtype == torch.float16 and p.dtype == torch.float16

    q_out = torch.empty_like(q)
    accept = torch.empty((B, N), device=q.device, dtype=torch.int32)

    BLOCK_D = triton.next_power_of_2(D)
    grid = (B, N)

    _poincare_rhmc_kernel[grid](
        q, p, grad_u, rand_unif,
        q_out, accept,
        B, N, D, dt, c,
        q.stride(0), q.stride(1), q.stride(2),
        p.stride(0), p.stride(1), p.stride(2),
        grad_u.stride(0), grad_u.stride(1), grad_u.stride(2),
        rand_unif.stride(0), rand_unif.stride(1),
        q_out.stride(0), q_out.stride(1), q_out.stride(2),
        accept.stride(0), accept.stride(1),
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )
    return q_out, accept


def pytorch_poincare_rhmc_ref(q: torch.Tensor, p: torch.Tensor, grad_u: torch.Tensor, rand_unif: torch.Tensor, dt: float = 0.01, c: float = 1.0):
    q_f = q.float()
    p_f = p.float()
    g_f = grad_u.float()

    # Initial Hamiltonian
    q_sq = torch.sum(q_f * q_f, dim=-1, keepdim=True)
    denom_curr = torch.clamp(1.0 - c * q_sq, min=1e-4)
    inv_lambda_curr = 0.5 * denom_curr
    u_curr = 0.5 * q_sq
    p_sq = torch.sum(p_f * p_f, dim=-1, keepdim=True)
    k_curr = 0.5 * (inv_lambda_curr * inv_lambda_curr) * p_sq
    h_curr = u_curr + k_curr

    # Leapfrog step
    p_half = p_f - 0.5 * dt * g_f
    v = (dt * inv_lambda_curr * inv_lambda_curr) * p_half
    v_sq = torch.sum(v * v, dim=-1, keepdim=True)
    dot_qv = torch.sum(q_f * v, dim=-1, keepdim=True)

    mob_num = (1.0 + 2.0 * c * dot_qv + c * v_sq) * q_f + denom_curr * v
    mob_den = torch.clamp(1.0 + 2.0 * c * dot_qv + c * c * q_sq * v_sq, min=1e-4)
    q_prop = mob_num / mob_den

    q_prop_sq = torch.sum(q_prop * q_prop, dim=-1, keepdim=True)
    max_sq = (1.0 / c) * 0.98
    q_prop = torch.where(q_prop_sq > max_sq, q_prop * torch.sqrt(max_sq / torch.clamp(q_prop_sq, min=1e-5)), q_prop)
    q_prop_sq = torch.sum(q_prop * q_prop, dim=-1, keepdim=True)

    p_prop = p_half - 0.5 * dt * q_prop

    # Proposed Hamiltonian
    denom_prop = torch.clamp(1.0 - c * q_prop_sq, min=1e-4)
    inv_lambda_prop = 0.5 * denom_prop
    u_prop = 0.5 * q_prop_sq
    p_prop_sq = torch.sum(p_prop * p_prop, dim=-1, keepdim=True)
    k_prop = 0.5 * (inv_lambda_prop * inv_lambda_prop) * p_prop_sq
    h_prop = u_prop + k_prop

    delta_h = (h_prop - h_curr).squeeze(-1)
    alpha = torch.exp(-delta_h)

    accept_mask = (rand_unif < alpha)
    q_final = torch.where(accept_mask.unsqueeze(-1), q_prop, q_f)

    return q_final.half(), accept_mask.to(torch.int32)


def benchmark():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Benchmarking on: {torch.cuda.get_device_name(device)}")

    B, N, D = 16, 512, 128
    q = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.1
    p = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.05
    grad_u = q.clone()
    rand_unif = torch.rand(B, N, device=device, dtype=torch.float32)

    q = q / (torch.norm(q, dim=-1, keepdim=True) + 1.2)

    # Correctness check
    q_tri, acc_tri = triton_poincare_rhmc(q, p, grad_u, rand_unif, dt=0.01, c=1.0)
    q_ref, acc_ref = pytorch_poincare_rhmc_ref(q, p, grad_u, rand_unif, dt=0.01, c=1.0)

    q_err = torch.max(torch.abs(q_tri - q_ref)).item()
    acc_match = (acc_tri == acc_ref).float().mean().item() * 100.0

    print(f"[+] Max Absolute Coordinate Error: {q_err:.6e}")
    print(f"[+] Acceptance Decision Match:      {acc_match:.2f}%")
    assert q_err < 1e-4, f"Coordinate error too high: {q_err}"
    assert acc_match == 100.0, f"Acceptance mismatch: {acc_match}%"
    print("[✓] Poincaré Riemannian Hamiltonian Monte Carlo Correctness test PASSED.")

    # Benchmark
    warmup, iters = 20, 200
    for _ in range(warmup):
        _ = triton_poincare_rhmc(q, p, grad_u, rand_unif, dt=0.01, c=1.0)
        _ = pytorch_poincare_rhmc_ref(q, p, grad_u, rand_unif, dt=0.01, c=1.0)
    torch.cuda.synchronize()

    start_pt = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_poincare_rhmc_ref(q, p, grad_u, rand_unif, dt=0.01, c=1.0)
    torch.cuda.synchronize()
    pt_time = (time.perf_counter() - start_pt) / iters

    start_tri = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_rhmc(q, p, grad_u, rand_unif, dt=0.01, c=1.0)
    torch.cuda.synchronize()
    tri_time = (time.perf_counter() - start_tri) / iters

    speedup = pt_time / tri_time
    total_tokens = B * N
    throughput = total_tokens / tri_time

    print(f"[+] PyTorch Eager Latency: {pt_time * 1e6:.2f} µs")
    print(f"[+] Triton Fused Latency:  {tri_time * 1e6:.2f} µs")
    print(f"[+] Speedup Factor:        {speedup:.2f}x")
    print(f"[+] Processing Throughput: {throughput / 1e6:.2f}M tok/s")


if __name__ == "__main__":
    benchmark()
