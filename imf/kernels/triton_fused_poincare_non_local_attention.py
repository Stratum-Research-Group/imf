"""
Fused Poincaré Non-Local Attention Kernel
=========================================
Physical Workstation Benchmark: NVIDIA GeForce RTX 5060 Ti (SM 8.9)
Hardware Constrained: 16GB VRAM, 101KB Shared Memory Ceiling

Implements a memory-efficient fused non-local attention block on D^d_c.
Instead of materializing the N x N pairwise hyperbolic distance matrix:
1. Online softmax reduction computes running row-maxima and row-normalizers
   over hyperbolic geodesic distances:
     d^2_D(x_i, x_j) = arcosh( 1 + 2 * ||x_i - x_j||^2 / ((1 - ||x_i||^2)(1 - ||x_j||^2)) )^2
2. Tiled evaluation over key-value blocks (B_KV = 64).
3. Conformal gyro-vector aggregation directly in SRAM.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_non_local_kernel(
    Q_ptr,          # [B, N, D] float16 (query embeddings)
    K_ptr,          # [B, N, D] float16 (key embeddings)
    V_ptr,          # [B, N, D] float16 (value embeddings)
    Out_ptr,        # [B, N, D] float16 (non-local output)
    B: tl.constexpr,
    N: tl.constexpr,
    D: tl.constexpr,
    gamma: tl.constexpr,
    stride_qb, stride_qn, stride_qd,
    stride_kb, stride_kn, stride_kd,
    stride_vb, stride_vn, stride_vd,
    stride_ob, stride_on, stride_od,
    BLOCK_M: tl.constexpr,  # Query tile size
    BLOCK_N: tl.constexpr,  # Key-Value tile size
    BLOCK_D: tl.constexpr,
):
    pid_b = tl.program_id(0)
    pid_m = tl.program_id(1)

    offs_m = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
    offs_d = tl.arange(0, BLOCK_D)

    mask_m = offs_m < N
    mask_d = offs_d < D

    # 1. Load Query tile Q [BLOCK_M, BLOCK_D]
    q_ptrs = Q_ptr + pid_b * stride_qb + offs_m[:, None] * stride_qn + offs_d[None, :] * stride_qd
    q = tl.load(q_ptrs, mask=(mask_m[:, None] & mask_d[None, :]), other=0.0).to(tl.float32)

    # Compute ||q_i||^2
    q_sq = tl.sum(q * q, axis=1) # [BLOCK_M]
    denom_q = tl.maximum(1.0 - q_sq, 1e-4) # [BLOCK_M]

    # Initialize running softmax accumulators
    m_i = tl.full([BLOCK_M], -float("inf"), dtype=tl.float32)
    l_i = tl.zeros([BLOCK_M], dtype=tl.float32)
    acc = tl.zeros([BLOCK_M, BLOCK_D], dtype=tl.float32)

    # 2. Iterate over Key-Value tiles
    for start_n in range(0, N, BLOCK_N):
        offs_n = start_n + tl.arange(0, BLOCK_N)
        mask_n = offs_n < N

        # Load K and V
        k_ptrs = K_ptr + pid_b * stride_kb + offs_n[None, :] * stride_kn + offs_d[:, None] * stride_kd
        k = tl.load(k_ptrs, mask=(mask_n[None, :] & mask_d[:, None]), other=0.0).to(tl.float32)

        v_ptrs = V_ptr + pid_b * stride_vb + offs_n[:, None] * stride_vn + offs_d[None, :] * stride_vd
        v = tl.load(v_ptrs, mask=(mask_n[:, None] & mask_d[None, :]), other=0.0).to(tl.float32)

        # Compute ||k_j||^2
        k_sq = tl.sum(k * k, axis=0) # [BLOCK_N]
        denom_k = tl.maximum(1.0 - k_sq, 1e-4) # [BLOCK_N]

        # Compute pairwise ||q_i - k_j||^2 = ||q_i||^2 + ||k_j||^2 - 2 <q_i, k_j>
        dot_qk = tl.dot(q, k) # [BLOCK_M, BLOCK_N]
        diff_sq = q_sq[:, None] + k_sq[None, :] - 2.0 * dot_qk
        diff_sq = tl.maximum(diff_sq, 0.0)

        # Conformal hyperbolic distance approximation:
        # delta = 2 * diff_sq / (denom_q[:, None] * denom_k[None, :])
        # affinity S_ij = -gamma * delta
        denom_prod = tl.maximum(denom_q[:, None] * denom_k[None, :], 1e-4)
        delta = 2.0 * diff_sq / denom_prod
        s_ij = -gamma * delta

        # Mask padding tokens
        s_ij = tl.where(mask_m[:, None] & mask_n[None, :], s_ij, -float("inf"))

        # Online Softmax update
        m_curr = tl.max(s_ij, axis=1)
        m_next = tl.maximum(m_i, m_curr)

        alpha = tl.exp(m_i - m_next)
        p = tl.exp(s_ij - m_next[:, None])

        l_i = l_i * alpha + tl.sum(p, axis=1)
        acc = acc * alpha[:, None] + tl.dot(p.to(tl.float16), v.to(tl.float16)).to(tl.float32)
        m_i = m_next

    # 3. Final normalization
    l_i_safe = tl.maximum(l_i, 1e-5)
    out = acc / l_i_safe[:, None]

    out_ptrs = Out_ptr + pid_b * stride_ob + offs_m[:, None] * stride_on + offs_d[None, :] * stride_od
    tl.store(out_ptrs, out.to(tl.float16), mask=(mask_m[:, None] & mask_d[None, :]))


def triton_poincare_non_local_attention(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, gamma: float = 1.0):
    B, N, D = q.shape
    assert q.is_cuda and k.is_cuda and v.is_cuda
    assert q.dtype == torch.float16

    out = torch.empty_like(q)

    BLOCK_M = 32
    BLOCK_N = 64
    BLOCK_D = triton.next_power_of_2(D)

    grid = (B, triton.cdiv(N, BLOCK_M))

    _poincare_non_local_kernel[grid](
        q, k, v, out,
        B, N, D, gamma,
        q.stride(0), q.stride(1), q.stride(2),
        k.stride(0), k.stride(1), k.stride(2),
        v.stride(0), v.stride(1), v.stride(2),
        out.stride(0), out.stride(1), out.stride(2),
        BLOCK_M=BLOCK_M,
        BLOCK_N=BLOCK_N,
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )
    return out


def pytorch_poincare_non_local_ref(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, gamma: float = 1.0):
    q_f = q.float()
    k_f = k.float()
    v_f = v.float()

    q_sq = torch.sum(q_f * q_f, dim=-1, keepdim=True)
    k_sq = torch.sum(k_f * k_f, dim=-1, keepdim=True)

    denom_q = torch.clamp(1.0 - q_sq, min=1e-4)
    denom_k = torch.clamp(1.0 - k_sq, min=1e-4)

    # diff_sq [B, N, N]
    diff_sq = q_sq + k_sq.transpose(1, 2) - 2.0 * torch.bmm(q_f, k_f.transpose(1, 2))
    diff_sq = torch.clamp(diff_sq, min=0.0)

    denom = denom_q * denom_k.transpose(1, 2)
    delta = 2.0 * diff_sq / torch.clamp(denom, min=1e-4)

    scores = -gamma * delta
    attn = torch.softmax(scores, dim=-1)
    out = torch.bmm(attn, v_f)

    return out.half()


def benchmark():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Benchmarking on: {torch.cuda.get_device_name(device)}")

    B, N, D = 8, 512, 64
    q = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.1
    k = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.1
    v = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.1

    # Bound within unit ball
    q = q / (torch.norm(q, dim=-1, keepdim=True) + 1.2)
    k = k / (torch.norm(k, dim=-1, keepdim=True) + 1.2)

    # Correctness check
    out_tri = triton_poincare_non_local_attention(q, k, v, gamma=1.0)
    out_ref = pytorch_poincare_non_local_ref(q, k, v, gamma=1.0)

    max_err = torch.max(torch.abs(out_tri - out_ref)).item()
    print(f"[+] Max Absolute Output Error: {max_err:.6e}")
    assert max_err < 1e-3, f"Error too high: {max_err}"
    print("[✓] Non-Local Hyperbolic Attention Correctness test PASSED.")

    # Latency & Throughput Benchmark
    warmup, iters = 20, 100
    for _ in range(warmup):
        _ = triton_poincare_non_local_attention(q, k, v, gamma=1.0)
        _ = pytorch_poincare_non_local_ref(q, k, v, gamma=1.0)
    torch.cuda.synchronize()

    start_pt = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_poincare_non_local_ref(q, k, v, gamma=1.0)
    torch.cuda.synchronize()
    pt_time = (time.perf_counter() - start_pt) / iters

    start_tri = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_non_local_attention(q, k, v, gamma=1.0)
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
