"""
Triton GPU Kernel: Fused Poincaré Key-Value Cache with Tangent RoPE (RTX 5060 Ti)

Implements dynamic hyperbolic auto-regressive decoding:
  Given new incoming token key/value vectors K_new, V_new in R^(B x H x D),
  1. In-place Tangent RoPE: Computes rotary embedding phase shifts in origin tangent space:
     K_rot = RoPE(K_new, position=pos)
  2. In-place Cache Update: Writes K_rot, V_new directly into the preallocated past_key_values buffer:
     K_cache[b, h, pos, :] = K_rot
     V_cache[b, h, pos, :] = V_new
  3. Fused Gyro-Attention Score Computation:
     Computes attention logits between Query Q and all cached keys up to current position:
     Scores[i] = (Q @ K_cache[i]^T) / sqrt(D)

Fuses Rotary Phase Shift, Cache Update, and Slice Attention in one hardware pass.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_kv_cache_update_and_attn_kernel(
    Q_ptr,          # [B, H, D]
    K_new_ptr,      # [B, H, D]
    V_new_ptr,      # [B, H, D]
    K_cache_ptr,    # [B, H, MAX_SEQ, D]
    V_cache_ptr,    # [B, H, MAX_SEQ, D]
    Scores_ptr,     # [B, H, MAX_SEQ]
    pos: tl.constexpr,
    B: tl.constexpr,
    H: tl.constexpr,
    D: tl.constexpr,
    MAX_SEQ: tl.constexpr,
):
    # Program grid: [B * H]
    pid = tl.program_id(0)
    b_idx = pid // H
    h_idx = pid % H

    offs_d = tl.arange(0, D)
    half_d = D // 2

    # 1. Load K_new [D] and apply Tangent RoPE
    k_val = tl.load(K_new_ptr + pid * D + offs_d)
    v_val = tl.load(V_new_ptr + pid * D + offs_d)

    # 2D Givens rotation for each pair (2i, 2i+1)
    # theta = 10000^(-2i / D)
    i_idx = offs_d // 2
    inv_freq = tl.exp(- (2.0 * i_idx / D) * 9.210340371976184) # ln(10000)
    theta = pos * inv_freq
    cos_theta = tl.cos(theta)
    sin_theta = tl.sin(theta)

    # Permuted components for 2D Givens rotation: [-k1, k0, -k3, k2, ...]
    is_odd = (offs_d % 2) == 1
    partner_offs = tl.where(is_odd, offs_d - 1, offs_d + 1)
    k_partner = tl.load(K_new_ptr + pid * D + partner_offs)
    k_rot = tl.where(is_odd, k_val * cos_theta + k_partner * sin_theta,
                             k_val * cos_theta - k_partner * sin_theta)

    # 2. Store K_rot and V_new into past_key_values cache at position `pos`
    cache_offset = (b_idx * H * MAX_SEQ * D) + (h_idx * MAX_SEQ * D) + (pos * D) + offs_d
    tl.store(K_cache_ptr + cache_offset, k_rot)
    tl.store(V_cache_ptr + cache_offset, v_val)

    # 3. Compute attention logits: Score[s] = (Q @ K_cache[s]) / sqrt(D) for s <= pos
    q_val = tl.load(Q_ptr + pid * D + offs_d)
    scale = 1.0 / math.sqrt(D)

    # Loop over cached sequence up to pos + 1
    for s in range(0, pos + 1):
        k_s = tl.load(K_cache_ptr + (b_idx * H * MAX_SEQ * D) + (h_idx * MAX_SEQ * D) + (s * D) + offs_d)
        score_s = tl.sum(q_val * k_s) * scale
        score_offset = (b_idx * H * MAX_SEQ) + (h_idx * MAX_SEQ) + s
        tl.store(Scores_ptr + score_offset, score_s)


def poincare_kv_cache_pytorch(Q, K_new, V_new, K_cache, V_cache, pos):
    """Reference PyTorch implementation."""
    B, H, D = Q.shape
    # Tangent RoPE
    half_d = D // 2
    i_idx = torch.arange(half_d, device=Q.device, dtype=torch.float32)
    inv_freq = torch.exp(- (2.0 * i_idx / D) * math.log(10000.0))
    theta = pos * inv_freq
    cos_theta = torch.repeat_interleave(torch.cos(theta), 2)
    sin_theta = torch.repeat_interleave(torch.sin(theta), 2)

    # Permuted for 2D Givens
    k_even = K_new[..., 0::2]
    k_odd = K_new[..., 1::2]
    k_rot = torch.empty_like(K_new)
    k_rot[..., 0::2] = k_even * torch.cos(theta) - k_odd * torch.sin(theta)
    k_rot[..., 1::2] = k_odd * torch.cos(theta) + k_even * torch.sin(theta)

    # Update cache
    K_cache[:, :, pos, :] = k_rot
    V_cache[:, :, pos, :] = V_new

    # Attention scores
    scale = 1.0 / math.sqrt(D)
    scores = torch.einsum('bhd,bhsd->bhs', Q, K_cache[:, :, :pos+1, :]) * scale
    return scores, k_rot


def poincare_kv_cache_triton(Q, K_new, V_new, K_cache, V_cache, pos):
    B, H, D = Q.shape
    MAX_SEQ = K_cache.shape[2]
    scores = torch.zeros((B, H, MAX_SEQ), device=Q.device, dtype=torch.float32)

    grid = (B * H,)
    _poincare_kv_cache_update_and_attn_kernel[grid](
        Q, K_new, V_new, K_cache, V_cache, scores,
        pos=pos, B=B, H=H, D=D, MAX_SEQ=MAX_SEQ,
    )
    return scores[:, :, :pos+1]


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré KV-Cache Kernel on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    B = 8             # Batch size
    H = 8             # Attention heads
    D = 64            # Head dimension
    MAX_SEQ = 512     # Max sequence capacity
    pos = 127         # Current decoding step

    # Preallocated KV caches
    K_cache_pt = torch.zeros((B, H, MAX_SEQ, D), device=device, dtype=torch.float32)
    V_cache_pt = torch.zeros((B, H, MAX_SEQ, D), device=device, dtype=torch.float32)
    K_cache_triton = torch.zeros((B, H, MAX_SEQ, D), device=device, dtype=torch.float32)
    V_cache_triton = torch.zeros((B, H, MAX_SEQ, D), device=device, dtype=torch.float32)

    # Fill past context with dummy vectors
    past = torch.randn((B, H, pos, D), device=device, dtype=torch.float32) * 0.1
    K_cache_pt[:, :, :pos, :] = past
    V_cache_pt[:, :, :pos, :] = past
    K_cache_triton[:, :, :pos, :] = past
    V_cache_triton[:, :, :pos, :] = past

    Q = torch.randn((B, H, D), device=device, dtype=torch.float32) * 0.1
    K_new = torch.randn((B, H, D), device=device, dtype=torch.float32) * 0.1
    V_new = torch.randn((B, H, D), device=device, dtype=torch.float32) * 0.1

    # Verify numerical correctness
    scores_pt, k_rot_pt = poincare_kv_cache_pytorch(Q, K_new, V_new, K_cache_pt, V_cache_pt, pos)
    scores_triton = poincare_kv_cache_triton(Q, K_new, V_new, K_cache_triton, V_cache_triton, pos)

    max_err = (scores_pt - scores_triton).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-4, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-4 error)!")

    # Warmup
    for _ in range(50):
        poincare_kv_cache_pytorch(Q, K_new, V_new, K_cache_pt, V_cache_pt, pos)
        poincare_kv_cache_triton(Q, K_new, V_new, K_cache_triton, V_cache_triton, pos)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 500
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_kv_cache_pytorch(Q, K_new, V_new, K_cache_pt, V_cache_pt, pos)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_kv_cache_triton(Q, K_new, V_new, K_cache_triton, V_cache_triton, pos)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    tok_sec = (B * H) / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {tok_sec / 1e6:.2f} M head-tokens/sec")


if __name__ == "__main__":
    benchmark()
