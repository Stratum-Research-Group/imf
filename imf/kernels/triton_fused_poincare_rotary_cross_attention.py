"""
Triton GPU Kernel: Fused Poincaré Rotary Cross-Attention (RTX 5060 Ti)

Implements multi-modal/cross-sequence hyperbolic attention with origin-tangent RoPE:
  Given queries Q in R^(M_q x D), keys K in R^(M_kv x D), values V in R^(M_kv x D):
  1. Computes cross-rotary phase shifts on Q and K in origin tangent space T_0 B^D:
     Q_rot = RoPE(Q, pos_q),  K_rot = RoPE(K, pos_kv)
  2. Evaluates cross-attention matrix:
     Scores = (Q_rot @ K_rot^T) / sqrt(D)
  3. Softmax row-wise normalization + value projection:
     Attn_out = Softmax(Scores) @ V
  4. Retracts output to Poincare ball B^D via exp_0^c mapping.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_rotary_cross_attention_kernel(
    Q_ptr,          # [M_q, D]
    K_ptr,          # [M_kv, D]
    V_ptr,          # [M_kv, D]
    Out_ptr,        # [M_q, D]
    M_q: tl.constexpr,
    M_kv: tl.constexpr,
    D: tl.constexpr,
    BLOCK_Q: tl.constexpr,
    c: tl.constexpr,
):
    pid = tl.program_id(0)
    offs_q = pid * BLOCK_Q + tl.arange(0, BLOCK_Q)
    mask_q = offs_q < M_q
    offs_d = tl.arange(0, D)

    # 1. Load Query block: [BLOCK_Q, D]
    q = tl.load(Q_ptr + offs_q[:, None] * D + offs_d[None, :], mask=mask_q[:, None], other=0.0)

    # Apply RoPE on Q
    i_idx = offs_d // 2
    inv_freq = tl.exp(- (2.0 * i_idx / D) * 9.210340371976184)
    theta_q = offs_q[:, None] * inv_freq[None, :]
    cos_q = tl.cos(theta_q)
    sin_q = tl.sin(theta_q)

    is_odd = (offs_d % 2) == 1
    partner_offs = tl.where(is_odd, offs_d - 1, offs_d + 1)
    q_partner = tl.load(Q_ptr + offs_q[:, None] * D + partner_offs[None, :], mask=mask_q[:, None], other=0.0)
    q_rot = tl.where(is_odd[None, :], q * cos_q + q_partner * sin_q,
                                     q * cos_q - q_partner * sin_q)

    # Accumulate Attention Output across KV sequence
    offs_kv = tl.arange(0, M_kv)
    k = tl.load(K_ptr + offs_kv[:, None] * D + offs_d[None, :])
    v = tl.load(V_ptr + offs_kv[:, None] * D + offs_d[None, :])

    # Apply RoPE on K
    theta_k = offs_kv[:, None] * inv_freq[None, :]
    cos_k = tl.cos(theta_k)
    sin_k = tl.sin(theta_k)
    k_partner = tl.load(K_ptr + offs_kv[:, None] * D + partner_offs[None, :])
    k_rot = tl.where(is_odd[None, :], k * cos_k + k_partner * sin_k,
                                     k * cos_k - k_partner * sin_k)

    # Scores: [BLOCK_Q, M_kv]
    scale = 1.0 / math.sqrt(D)
    scores = tl.dot(q_rot.to(tl.float16), tl.trans(k_rot.to(tl.float16))) * scale
    max_scores = tl.max(scores, axis=1)
    exp_scores = tl.exp(scores - max_scores[:, None])
    sum_exp = tl.sum(exp_scores, axis=1)
    attn_weights = exp_scores / sum_exp[:, None]

    attn_out = tl.dot(attn_weights.to(tl.float16), v.to(tl.float16)) # [BLOCK_Q, D]

    # Retract attn_out via exp_0^c
    attn_f32 = attn_out.to(tl.float32)
    sq_norm = tl.sum(attn_f32 * attn_f32, axis=1)
    norm = tl.sqrt(sq_norm + 1e-12)
    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))
    u = sqrt_c * norm
    u_clamped = tl.minimum(u, 15.0)
    exp_2u = tl.exp(2.0 * u_clamped)
    tanh_u = (exp_2u - 1.0) / (exp_2u + 1.0)
    scale_retract = tanh_u / (sqrt_c * norm)

    y_out = attn_f32 * scale_retract[:, None]
    tl.store(Out_ptr + offs_q[:, None] * D + offs_d[None, :], y_out.to(tl.float16), mask=mask_q[:, None])


def poincare_rotary_cross_attention_pytorch(Q, K, V, c=1.0):
    """Reference PyTorch implementation."""
    M_q, D = Q.shape
    M_kv, _ = K.shape

    half_d = D // 2
    i_idx = torch.arange(half_d, device=Q.device, dtype=torch.float32)
    inv_freq = torch.exp(- (2.0 * i_idx / D) * math.log(10000.0))

    # RoPE on Q
    pos_q = torch.arange(M_q, device=Q.device, dtype=torch.float32)[:, None]
    theta_q = pos_q * inv_freq[None, :]
    q_even = Q[..., 0::2]
    q_odd = Q[..., 1::2]
    q_rot = torch.empty_like(Q)
    q_rot[..., 0::2] = q_even * torch.cos(theta_q) - q_odd * torch.sin(theta_q)
    q_rot[..., 1::2] = q_odd * torch.cos(theta_q) + q_even * torch.sin(theta_q)

    # RoPE on K
    pos_k = torch.arange(M_kv, device=K.device, dtype=torch.float32)[:, None]
    theta_k = pos_k * inv_freq[None, :]
    k_even = K[..., 0::2]
    k_odd = K[..., 1::2]
    k_rot = torch.empty_like(K)
    k_rot[..., 0::2] = k_even * torch.cos(theta_k) - k_odd * torch.sin(theta_k)
    k_rot[..., 1::2] = k_odd * torch.cos(theta_k) + k_even * torch.sin(theta_k)

    # Scores
    scale = 1.0 / math.sqrt(D)
    scores = torch.matmul(q_rot.float(), k_rot.float().transpose(-1, -2)) * scale
    weights = torch.softmax(scores, dim=-1)
    attn_out = torch.matmul(weights, V.float())

    # Retract
    norm = torch.norm(attn_out, p=2, dim=-1, keepdim=True).clamp(min=1e-8)
    sqrt_c = math.sqrt(c)
    scale_r = torch.tanh(sqrt_c * norm) / (sqrt_c * norm)
    return (attn_out * scale_r).half()


def poincare_rotary_cross_attention_triton(Q, K, V, c=1.0):
    M_q, D = Q.shape
    M_kv, _ = K.shape
    out = torch.empty((M_q, D), device=Q.device, dtype=torch.float16)

    BLOCK_Q = 16
    grid = (triton.cdiv(M_q, BLOCK_Q),)
    _poincare_rotary_cross_attention_kernel[grid](
        Q, K, V, out,
        M_q=M_q, M_kv=M_kv, D=D, BLOCK_Q=BLOCK_Q, c=c,
    )
    return out


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré Rotary Cross-Attention on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    M_q = 512        # Query tokens
    M_kv = 256       # Key/Value context tokens
    D = 64           # Hidden dimension
    c = 1.0

    Q = (torch.randn((M_q, D), device=device, dtype=torch.float32) * 0.05).half()
    K = (torch.randn((M_kv, D), device=device, dtype=torch.float32) * 0.05).half()
    V = (torch.randn((M_kv, D), device=device, dtype=torch.float32) * 0.05).half()

    # Correctness check
    out_pt = poincare_rotary_cross_attention_pytorch(Q, K, V, c)
    out_triton = poincare_rotary_cross_attention_triton(Q, K, V, c)

    max_err = (out_pt.float() - out_triton.float()).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-2, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-2 fp16 error)!")

    # Warmup
    for _ in range(50):
        poincare_rotary_cross_attention_pytorch(Q, K, V, c)
        poincare_rotary_cross_attention_triton(Q, K, V, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 300
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_rotary_cross_attention_pytorch(Q, K, V, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_rotary_cross_attention_triton(Q, K, V, c)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    tokens_per_sec = M_q / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {tokens_per_sec / 1e6:.2f} M query-tokens/sec")


if __name__ == "__main__":
    benchmark()
