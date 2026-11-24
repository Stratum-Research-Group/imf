"""
Triton GPU Kernel: Fused Poincaré ALiBi (Attention with Linear Biases) (RTX 5060 Ti)

Implements Hyperbolic ALiBi with geodesic distance penalties:
  Given queries Q in R^(M x D), keys K in R^(M x D), values V in R^(M x D) for H heads:
  1. Computes geometric head slope m_h = 2^(-8 * (h + 1) / H).
  2. Modulates dot-product scores with radial-conformal scale:
     bias_ij = - m_h * |i - j| * (1.0 + sqrt(c) * ||Q_i||)
     S_ij = (Q_i @ K_j^T) / sqrt(D) + bias_ij
  3. Row-wise Softmax + Value reduction:
     Attn_out = Softmax(S) @ V
  4. Retracts output to Poincare ball B^D via exp_0^c mapping.

Enables zero-shot context length extrapolation without positional embeddings on hyperbolic manifolds.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_alibi_kernel(
    Q_ptr,          # [H, M, D] (fp16)
    K_ptr,          # [H, M, D] (fp16)
    V_ptr,          # [H, M, D] (fp16)
    Out_ptr,        # [H, M, D] (fp16)
    H: tl.constexpr,
    M: tl.constexpr,
    D: tl.constexpr,
    BLOCK_M: tl.constexpr,
    c: tl.constexpr,
):
    pid_m = tl.program_id(0) # Program per query block
    pid_h = tl.program_id(1) # Program per head

    offs_m = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
    mask_m = offs_m < M
    offs_d = tl.arange(0, D)

    # 1. Head-specific ALiBi slope: m_h = 2^(-8 * (pid_h + 1) / H)
    head_ratio = (pid_h + 1.0) / H
    m_h = tl.exp(- 8.0 * head_ratio * 0.6931471805599453) # ln(2)

    # 2. Load Q block: [BLOCK_M, D]
    head_offset_q = pid_h * M * D
    q = tl.load(Q_ptr + head_offset_q + offs_m[:, None] * D + offs_d[None, :], mask=mask_m[:, None], other=0.0)

    # Norm of Q for radial scaling: [BLOCK_M]
    q_f32 = q.to(tl.float32)
    q_norm = tl.sqrt(tl.sum(q_f32 * q_f32, axis=1) + 1e-12)
    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))
    radial_scale = 1.0 + sqrt_c * q_norm # [BLOCK_M]

    # 3. Load entire K and V across sequence M: [M, D]
    head_offset_kv = pid_h * M * D
    offs_n = tl.arange(0, M)
    k = tl.load(K_ptr + head_offset_kv + offs_n[:, None] * D + offs_d[None, :])
    v = tl.load(V_ptr + head_offset_kv + offs_n[:, None] * D + offs_d[None, :])

    # Dot-product scores: [BLOCK_M, M]
    scale_d = 1.0 / math.sqrt(D)
    scores = tl.dot(q, tl.trans(k)) * scale_d # fp32

    # Linear distance bias: - m_h * |i - j| * radial_scale
    dist_ij = tl.abs(offs_m[:, None] - offs_n[None, :])
    bias_ij = - m_h * dist_ij * radial_scale[:, None]
    scores_biased = scores + bias_ij

    # Row-wise softmax
    max_scores = tl.max(scores_biased, axis=1)
    exp_scores = tl.exp(scores_biased - max_scores[:, None])
    sum_exp = tl.sum(exp_scores, axis=1)
    attn_weights = exp_scores / sum_exp[:, None]

    # Value reduction: [BLOCK_M, D]
    attn_out = tl.dot(attn_weights.to(tl.float16), v)

    # Retraction via exp_0^c mapping
    attn_f32 = attn_out.to(tl.float32)
    sq_norm = tl.sum(attn_f32 * attn_f32, axis=1)
    norm = tl.sqrt(sq_norm + 1e-12)
    u = sqrt_c * norm
    u_clamped = tl.minimum(u, 15.0)
    exp_2u = tl.exp(2.0 * u_clamped)
    tanh_u = (exp_2u - 1.0) / (exp_2u + 1.0)
    scale_r = tanh_u / (sqrt_c * norm)

    y_out = attn_f32 * scale_r[:, None]
    tl.store(Out_ptr + head_offset_q + offs_m[:, None] * D + offs_d[None, :], y_out.to(tl.float16), mask=mask_m[:, None])


def poincare_alibi_pytorch(Q, K, V, c=1.0):
    """Reference PyTorch implementation."""
    H, M, D = Q.shape
    scale_d = 1.0 / math.sqrt(D)

    out = torch.empty_like(Q)
    sqrt_c = math.sqrt(c)

    for h in range(H):
        m_h = 2.0 ** (-8.0 * (h + 1) / H)
        q_h = Q[h].float()
        k_h = K[h].float()
        v_h = V[h].float()

        # Dot-product scores
        scores = torch.matmul(q_h, k_h.transpose(-1, -2)) * scale_d

        # ALiBi bias
        q_norm = torch.norm(q_h, p=2, dim=-1, keepdim=True)
        radial_scale = 1.0 + sqrt_c * q_norm
        dist_ij = torch.abs(torch.arange(M, device=Q.device)[:, None] - torch.arange(M, device=Q.device)[None, :])
        bias = - m_h * dist_ij * radial_scale

        weights = torch.softmax(scores + bias, dim=-1)
        attn_out = torch.matmul(weights, v_h)

        norm = torch.norm(attn_out, p=2, dim=-1, keepdim=True).clamp(min=1e-8)
        scale_r = torch.tanh(sqrt_c * norm) / (sqrt_c * norm)
        out[h] = (attn_out * scale_r).half()

    return out


def poincare_alibi_triton(Q, K, V, c=1.0):
    H, M, D = Q.shape
    out = torch.empty_like(Q)

    BLOCK_M = 16
    grid = (triton.cdiv(M, BLOCK_M), H)
    _poincare_alibi_kernel[grid](
        Q, K, V, out,
        H=H, M=M, D=D, BLOCK_M=BLOCK_M, c=c,
    )
    return out


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré ALiBi Kernel on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    H = 8            # Heads
    M = 512          # Sequence length
    D = 64           # Head dimension
    c = 1.0

    Q = (torch.randn((H, M, D), device=device, dtype=torch.float32) * 0.05).half()
    K = (torch.randn((H, M, D), device=device, dtype=torch.float32) * 0.05).half()
    V = (torch.randn((H, M, D), device=device, dtype=torch.float32) * 0.05).half()

    # Correctness check
    out_pt = poincare_alibi_pytorch(Q, K, V, c)
    out_triton = poincare_alibi_triton(Q, K, V, c)

    max_err = (out_pt.float() - out_triton.float()).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-2, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-2 fp16 error)!")

    # Warmup
    for _ in range(50):
        poincare_alibi_pytorch(Q, K, V, c)
        poincare_alibi_triton(Q, K, V, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 300
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_alibi_pytorch(Q, K, V, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_alibi_triton(Q, K, V, c)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    tokens_per_sec = (H * M) / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {tokens_per_sec / 1e6:.2f} M tokens/sec")


if __name__ == "__main__":
    benchmark()
