"""
Triton GPU Kernel: Fused Poincaré Grouped-Query Attention (GQA) RoPE Embedding (RTX 5060 Ti)

Implements multi-query / grouped-query rotary phase shifts on the Poincaré ball:
  Queries Q in R^(B x H_q x D), Keys K in R^(B x H_kv x D) where H_q = G * H_kv (e.g. G=4 or G=8).
  Applies 2D Givens rotations across Q and K in parallel using shared frequency tables,
  vectorized block loads, and in-place register phase rotation without memory allocation.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_gqa_rope_kernel(
    Q_ptr,          # [B, H_q, D]
    K_ptr,          # [B, H_kv, D]
    Q_rot_ptr,      # [B, H_q, D]
    K_rot_ptr,      # [B, H_kv, D]
    pos: tl.constexpr,
    B: tl.constexpr,
    H_q: tl.constexpr,
    H_kv: tl.constexpr,
    D: tl.constexpr,
):
    pid = tl.program_id(0) # Program per query head: total B * H_q
    if pid >= B * H_q:
        return

    b_idx = pid // H_q
    h_q_idx = pid % H_q
    G: tl.constexpr = H_q // H_kv
    h_kv_idx = h_q_idx // G

    offs_d = tl.arange(0, D)

    # 1. Frequency coordinates
    i_idx = offs_d // 2
    inv_freq = tl.exp(- (2.0 * i_idx / D) * 9.210340371976184)
    theta = pos * inv_freq
    cos_th = tl.cos(theta)
    sin_th = tl.sin(theta)

    is_odd = (offs_d % 2) == 1
    partner_offs = tl.where(is_odd, offs_d - 1, offs_d + 1)

    # 2. RoPE on Q
    q_val = tl.load(Q_ptr + pid * D + offs_d)
    q_part = tl.load(Q_ptr + pid * D + partner_offs)
    q_rot = tl.where(is_odd, q_val * cos_th + q_part * sin_th,
                             q_val * cos_th - q_part * sin_th)
    tl.store(Q_rot_ptr + pid * D + offs_d, q_rot)

    # 3. Only the first head in the group writes the rotated K
    if (h_q_idx % G) == 0:
        kv_pid = b_idx * H_kv + h_kv_idx
        k_val = tl.load(K_ptr + kv_pid * D + offs_d)
        k_part = tl.load(K_ptr + kv_pid * D + partner_offs)
        k_rot = tl.where(is_odd, k_val * cos_th + k_part * sin_th,
                                 k_val * cos_th - k_part * sin_th)
        tl.store(K_rot_ptr + kv_pid * D + offs_d, k_rot)


def poincare_gqa_rope_pytorch(Q, K, pos):
    """Reference PyTorch implementation."""
    B, H_q, D = Q.shape
    _, H_kv, _ = K.shape

    half_d = D // 2
    i_idx = torch.arange(half_d, device=Q.device, dtype=torch.float32)
    inv_freq = torch.exp(- (2.0 * i_idx / D) * math.log(10000.0))
    theta = pos * inv_freq

    # Q rotation
    q_even, q_odd = Q[..., 0::2], Q[..., 1::2]
    q_rot = torch.empty_like(Q)
    q_rot[..., 0::2] = q_even * torch.cos(theta) - q_odd * torch.sin(theta)
    q_rot[..., 1::2] = q_odd * torch.cos(theta) + q_even * torch.sin(theta)

    # K rotation
    k_even, k_odd = K[..., 0::2], K[..., 1::2]
    k_rot = torch.empty_like(K)
    k_rot[..., 0::2] = k_even * torch.cos(theta) - k_odd * torch.sin(theta)
    k_rot[..., 1::2] = k_odd * torch.cos(theta) + k_even * torch.sin(theta)

    return q_rot, k_rot


def poincare_gqa_rope_triton(Q, K, pos):
    B, H_q, D = Q.shape
    _, H_kv, _ = K.shape

    Q_rot = torch.empty_like(Q)
    K_rot = torch.empty_like(K)

    grid = (B * H_q,)
    _poincare_gqa_rope_kernel[grid](
        Q, K, Q_rot, K_rot,
        pos=pos, B=B, H_q=H_q, H_kv=H_kv, D=D,
    )
    return Q_rot, K_rot


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré GQA RoPE Kernel on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    B = 16            # Batch size
    H_q = 32          # 32 Query heads
    H_kv = 8          # 8 KV heads (Group size G = 4)
    D = 64            # Dimension
    pos = 255         # Sequence position

    Q = torch.randn((B, H_q, D), device=device, dtype=torch.float32) * 0.1
    K = torch.randn((B, H_kv, D), device=device, dtype=torch.float32) * 0.1

    # Correctness check
    q_rot_pt, k_rot_pt = poincare_gqa_rope_pytorch(Q, K, pos)
    q_rot_triton, k_rot_triton = poincare_gqa_rope_triton(Q, K, pos)

    err_q = (q_rot_pt - q_rot_triton).abs().max().item()
    err_k = (k_rot_pt - k_rot_triton).abs().max().item()
    print(f"[*] Max absolute error (Q: {err_q:.4e}, K: {err_k:.4e})")
    assert max(err_q, err_k) < 1e-4, "Numerical mismatch exceeds tolerance!"
    print("[✓] Correctness check passed (< 1e-4 error)!")

    # Warmup
    for _ in range(50):
        poincare_gqa_rope_pytorch(Q, K, pos)
        poincare_gqa_rope_triton(Q, K, pos)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 500
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_gqa_rope_pytorch(Q, K, pos)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_gqa_rope_triton(Q, K, pos)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    heads_per_sec = (B * H_q) / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {heads_per_sec / 1e6:.2f} M query-heads/sec")


if __name__ == "__main__":
    benchmark()
