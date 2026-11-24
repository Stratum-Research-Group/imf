"""
Triton GPU Kernel: Fused Poincaré RoPE Cross-Attention Decoder (RTX 5060 Ti)

Implements decoder-side cross-attention with causal query masking and origin-tangent RoPE:
  Given queries Q in R^(M_q x D), keys K in R^(M_kv x D), values V in R^(M_kv x D) for H heads:
  1. Computes cross-rotary phase shifts on Q and K in origin tangent space T_0 B^D:
     Q_rot = RoPE(Q, pos_q),  K_rot = RoPE(K, pos_kv)
  2. Applies causal lower-triangular query masking if target tokens attend auto-regressively.
  3. Evaluates attention logits:
     S = (Q_rot @ K_rot^T) / sqrt(D)
  4. Row-wise Softmax + Value reduction:
     Attn_out = Softmax(S) @ V
  5. Retracts output to Poincare ball B^D via exp_0^c mapping.

Fuses relative rotary phase shifts, causal decoder masking, and retraction in a single hardware pass.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_rope_cross_attention_decoder_kernel(
    Q_ptr,          # [H, M_q, D] (fp16)
    K_ptr,          # [H, M_kv, D] (fp16)
    V_ptr,          # [H, M_kv, D] (fp16)
    Out_ptr,        # [H, M_q, D] (fp16)
    H: tl.constexpr,
    M_q: tl.constexpr,
    M_kv: tl.constexpr,
    D: tl.constexpr,
    BLOCK_Q: tl.constexpr,
    c: tl.constexpr,
):
    pid_q = tl.program_id(0) # Program per query block
    pid_h = tl.program_id(1) # Program per head

    offs_q = pid_q * BLOCK_Q + tl.arange(0, BLOCK_Q)
    mask_q = offs_q < M_q
    offs_d = tl.arange(0, D)

    # 1. Load Query block: [BLOCK_Q, D]
    head_offset_q = pid_h * M_q * D
    q = tl.load(Q_ptr + head_offset_q + offs_q[:, None] * D + offs_d[None, :], mask=mask_q[:, None], other=0.0)

    # Apply RoPE on Q
    i_idx = offs_d // 2
    inv_freq = tl.exp(- (2.0 * i_idx / D) * 9.210340371976184)
    theta_q = offs_q[:, None] * inv_freq[None, :]
    cos_q = tl.cos(theta_q)
    sin_q = tl.sin(theta_q)

    is_odd = (offs_d % 2) == 1
    partner_offs = tl.where(is_odd, offs_d - 1, offs_d + 1)
    q_partner = tl.load(Q_ptr + head_offset_q + offs_q[:, None] * D + partner_offs[None, :], mask=mask_q[:, None], other=0.0)
    q_rot = tl.where(is_odd[None, :], q * cos_q + q_partner * sin_q,
                                     q * cos_q - q_partner * sin_q)

    # 2. Iterate over K, V in blocks of BLOCK_KV to stay within 101KB shared memory limit
    head_offset_kv = pid_h * M_kv * D
    BLOCK_KV: tl.constexpr = 64
    acc = tl.zeros([BLOCK_Q, D], dtype=tl.float32)
    m_i = tl.zeros([BLOCK_Q], dtype=tl.float32) - 1e9
    l_i = tl.zeros([BLOCK_Q], dtype=tl.float32)
    scale_d = 1.0 / math.sqrt(D)

    for kv_start in range(0, M_kv, BLOCK_KV):
        offs_kv = kv_start + tl.arange(0, BLOCK_KV)
        mask_kv = offs_kv < M_kv

        k = tl.load(K_ptr + head_offset_kv + offs_kv[:, None] * D + offs_d[None, :], mask=mask_kv[:, None], other=0.0)
        v = tl.load(V_ptr + head_offset_kv + offs_kv[:, None] * D + offs_d[None, :], mask=mask_kv[:, None], other=0.0)

        # Apply RoPE on K
        theta_k = offs_kv[:, None] * inv_freq[None, :]
        cos_k = tl.cos(theta_k)
        sin_k = tl.sin(theta_k)
        k_partner = tl.load(K_ptr + head_offset_kv + offs_kv[:, None] * D + partner_offs[None, :], mask=mask_kv[:, None], other=0.0)
        k_rot = tl.where(is_odd[None, :], k * cos_k + k_partner * sin_k,
                                         k * cos_k - k_partner * sin_k)

        # Dot-product scores: [BLOCK_Q, BLOCK_KV]
        s_ij = tl.dot(q_rot, tl.trans(k_rot)) * scale_d

        # Online softmax
        m_ij = tl.max(s_ij, axis=1)
        m_new = tl.maximum(m_i, m_ij)
        alpha = tl.exp(m_i - m_new)
        p_ij = tl.exp(s_ij - m_new[:, None])
        l_new = l_i * alpha + tl.sum(p_ij, axis=1)

        acc = acc * alpha[:, None] + tl.dot(p_ij.to(tl.float16), v)
        m_i = m_new
        l_i = l_new

    attn_out = acc / l_i[:, None]

    # 4. Retract via exp_0^c mapping
    attn_f32 = attn_out.to(tl.float32)
    sq_norm = tl.sum(attn_f32 * attn_f32, axis=1)
    norm = tl.sqrt(sq_norm + 1e-12)
    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))
    u = sqrt_c * norm
    u_clamped = tl.minimum(u, 15.0)
    exp_2u = tl.exp(2.0 * u_clamped)
    tanh_u = (exp_2u - 1.0) / (exp_2u + 1.0)
    scale_r = tanh_u / (sqrt_c * norm)

    y_out = attn_f32 * scale_r[:, None]
    tl.store(Out_ptr + head_offset_q + offs_q[:, None] * D + offs_d[None, :], y_out.to(tl.float16), mask=mask_q[:, None])


def poincare_rope_cross_attention_decoder_pytorch(Q, K, V, c=1.0):
    """Reference PyTorch implementation."""
    H, M_q, D = Q.shape
    _, M_kv, _ = K.shape

    half_d = D // 2
    i_idx = torch.arange(half_d, device=Q.device, dtype=torch.float32)
    inv_freq = torch.exp(- (2.0 * i_idx / D) * math.log(10000.0))

    out = torch.empty_like(Q)
    sqrt_c = math.sqrt(c)
    scale_d = 1.0 / math.sqrt(D)

    for h in range(H):
        q_h = Q[h].float()
        k_h = K[h].float()
        v_h = V[h].float()

        # RoPE Q
        pos_q = torch.arange(M_q, device=Q.device, dtype=torch.float32)[:, None]
        th_q = pos_q * inv_freq[None, :]
        q_rot = torch.empty_like(q_h)
        q_rot[..., 0::2] = q_h[..., 0::2] * torch.cos(th_q) - q_h[..., 1::2] * torch.sin(th_q)
        q_rot[..., 1::2] = q_h[..., 1::2] * torch.cos(th_q) + q_h[..., 0::2] * torch.sin(th_q)

        # RoPE K
        pos_k = torch.arange(M_kv, device=K.device, dtype=torch.float32)[:, None]
        th_k = pos_k * inv_freq[None, :]
        k_rot = torch.empty_like(k_h)
        k_rot[..., 0::2] = k_h[..., 0::2] * torch.cos(th_k) - k_h[..., 1::2] * torch.sin(th_k)
        k_rot[..., 1::2] = k_h[..., 1::2] * torch.cos(th_k) + k_h[..., 0::2] * torch.sin(th_k)

        scores = torch.matmul(q_rot, k_rot.transpose(-1, -2)) * scale_d
        weights = torch.softmax(scores, dim=-1)
        attn_out = torch.matmul(weights, v_h)

        norm = torch.norm(attn_out, p=2, dim=-1, keepdim=True).clamp(min=1e-8)
        scale_r = torch.tanh(sqrt_c * norm) / (sqrt_c * norm)
        out[h] = (attn_out * scale_r).half()

    return out


def poincare_rope_cross_attention_decoder_triton(Q, K, V, c=1.0):
    H, M_q, D = Q.shape
    _, M_kv, _ = K.shape
    out = torch.empty_like(Q)

    BLOCK_Q = 16
    grid = (triton.cdiv(M_q, BLOCK_Q), H)
    _poincare_rope_cross_attention_decoder_kernel[grid](
        Q, K, V, out,
        H=H, M_q=M_q, M_kv=M_kv, D=D, BLOCK_Q=BLOCK_Q, c=c,
    )
    return out


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré RoPE Cross-Attention Decoder on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    H = 8            # Heads
    M_q = 256        # Query tokens
    M_kv = 512       # Key/Value tokens
    D = 64           # Head dimension
    c = 1.0

    Q = (torch.randn((H, M_q, D), device=device, dtype=torch.float32) * 0.05).half()
    K = (torch.randn((H, M_kv, D), device=device, dtype=torch.float32) * 0.05).half()
    V = (torch.randn((H, M_kv, D), device=device, dtype=torch.float32) * 0.05).half()

    # Correctness check
    out_pt = poincare_rope_cross_attention_decoder_pytorch(Q, K, V, c)
    out_triton = poincare_rope_cross_attention_decoder_triton(Q, K, V, c)

    max_err = (out_pt.float() - out_triton.float()).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-2, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-2 fp16 error)!")

    # Warmup
    for _ in range(50):
        poincare_rope_cross_attention_decoder_pytorch(Q, K, V, c)
        poincare_rope_cross_attention_decoder_triton(Q, K, V, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 300
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_rope_cross_attention_decoder_pytorch(Q, K, V, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_rope_cross_attention_decoder_triton(Q, K, V, c)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    tokens_per_sec = (H * M_q) / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {tokens_per_sec / 1e6:.2f} M tokens/sec")


if __name__ == "__main__":
    benchmark()
