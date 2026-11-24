r"""
IMF Triton Fused Poincaré Multi-Head Gyro-Self-Attention Kernel (Tiled Across Sequence)
========================================================================================
Hardware-accelerated Multi-Head Gyrovector Self-Attention on the Poincaré ball \mathbb{B}_c^D.
Optimized with block tiling across sequence dimensions.
"""

import time
import torch
import triton
import triton.language as tl


@torch.no_grad()
def poincare_multihead_attention_torch(
    q: torch.Tensor,        # [B, N, H, d_h]
    k: torch.Tensor,        # [B, N, H, d_h]
    v: torch.Tensor,        # [B, N, H, d_h]
    eps: float = 1e-5,
) -> torch.Tensor:
    B, N, H, d_h = q.shape

    norm_q = torch.norm(q, dim=-1, keepdim=True).clamp(min=1e-7, max=1.0 - eps)
    norm_k = torch.norm(k, dim=-1, keepdim=True).clamp(min=1e-7, max=1.0 - eps)
    norm_v = torch.norm(v, dim=-1, keepdim=True).clamp(min=1e-7, max=1.0 - eps)

    t_q = torch.atanh(norm_q) * (q / norm_q)
    t_k = torch.atanh(norm_k) * (k / norm_k)
    t_v = torch.atanh(norm_v) * (v / norm_v)

    conf_q = (1.0 - norm_q ** 2)
    conf_k = (1.0 - norm_k ** 2)

    t_q = t_q.permute(0, 2, 1, 3)
    t_k = t_k.permute(0, 2, 1, 3)
    t_v = t_v.permute(0, 2, 1, 3)
    conf_q = conf_q.permute(0, 2, 1, 3)
    conf_k = conf_k.permute(0, 2, 1, 3)

    scores = torch.matmul(t_q, t_k.transpose(-1, -2)) / (d_h ** 0.5)
    conf_scale = torch.matmul(conf_q, conf_k.transpose(-1, -2)).clamp(min=eps)
    scores = scores / conf_scale

    weights = torch.softmax(scores, dim=-1)
    out_tangent = torch.matmul(weights, t_v)

    norm_out_t = torch.norm(out_tangent, dim=-1, keepdim=True).clamp(min=1e-7)
    out = torch.tanh(norm_out_t) * (out_tangent / norm_out_t)

    return out.permute(0, 2, 1, 3).contiguous()


@triton.jit
def _poincare_mha_tiled_kernel(
    Q_ptr, K_ptr, V_ptr, Out_ptr,
    scale, eps,
    B: tl.constexpr, N: tl.constexpr, H: tl.constexpr, d_h: tl.constexpr,
    BLOCK_N: tl.constexpr, BLOCK_D: tl.constexpr,
):
    # Parallelize over [B, H, N_chunks]
    pid = tl.program_id(0)
    total_programs = B * H * N
    if pid >= total_programs:
        return

    i = pid % N
    rem = pid // N
    h = rem % H
    b = rem // H

    offs_d = tl.arange(0, BLOCK_D)
    mask_d = offs_d < d_h

    # Load Q[b, i, h, :]
    q_offset = b * (N * H * d_h) + i * (H * d_h) + h * d_h + offs_d
    q = tl.load(Q_ptr + q_offset, mask=mask_d, other=0.0)

    q_sq = tl.sum(tl.where(mask_d, q * q, 0.0))
    norm_q = tl.sqrt(q_sq)
    norm_q_clamped = tl.minimum(tl.maximum(norm_q, 1e-7), 1.0 - eps)

    artanh_q = 0.5 * tl.log((1.0 + norm_q_clamped) / (1.0 - norm_q_clamped))
    t_q = q * (artanh_q / norm_q_clamped)
    conf_q = 1.0 - norm_q_clamped * norm_q_clamped

    m = -1e9
    d_sum = 0.0
    acc_v = tl.zeros([BLOCK_D], dtype=tl.float32)

    offs_n = tl.arange(0, BLOCK_N)
    for j_start in range(0, N, BLOCK_N):
        j_idx = j_start + offs_n
        mask_n = j_idx < N

        k_ptrs = K_ptr + b * (N * H * d_h) + tl.expand_dims(j_idx, 1) * (H * d_h) + h * d_h + tl.expand_dims(offs_d, 0)
        mask_2d = tl.expand_dims(mask_n, 1) & tl.expand_dims(mask_d, 0)
        k = tl.load(k_ptrs, mask=mask_2d, other=0.0)

        k_sq = tl.sum(tl.where(mask_2d, k * k, 0.0), axis=1)
        norm_k = tl.sqrt(k_sq)
        norm_k_clamped = tl.minimum(tl.maximum(norm_k, 1e-7), 1.0 - eps)

        artanh_k = 0.5 * tl.log((1.0 + norm_k_clamped) / (1.0 - norm_k_clamped))
        scale_k = tl.expand_dims(artanh_k / norm_k_clamped, 1)
        t_k = k * scale_k
        conf_k = 1.0 - norm_k_clamped * norm_k_clamped

        # dot product across d_h: [BLOCK_N]
        dots = tl.sum(tl.where(mask_2d, tl.expand_dims(t_q, 0) * t_k, 0.0), axis=1)
        denom = tl.maximum(conf_q * conf_k, eps)
        scores = tl.where(mask_n, (dots * scale) / denom, -1e9)

        # Online LSE across chunk
        chunk_max = tl.max(scores, axis=0)
        new_m = tl.maximum(m, chunk_max)
        exp_prev = tl.exp(m - new_m)
        exp_scores = tl.where(mask_n, tl.exp(scores - new_m), 0.0)

        d_sum = d_sum * exp_prev + tl.sum(exp_scores, axis=0)

        # Load V chunk: [BLOCK_N, BLOCK_D]
        v_ptrs = V_ptr + b * (N * H * d_h) + tl.expand_dims(j_idx, 1) * (H * d_h) + h * d_h + tl.expand_dims(offs_d, 0)
        v_val = tl.load(v_ptrs, mask=mask_2d, other=0.0)

        v_sq = tl.sum(tl.where(mask_2d, v_val * v_val, 0.0), axis=1)
        norm_v = tl.sqrt(v_sq)
        norm_v_clamped = tl.minimum(tl.maximum(norm_v, 1e-7), 1.0 - eps)

        artanh_v = 0.5 * tl.log((1.0 + norm_v_clamped) / (1.0 - norm_v_clamped))
        scale_v = tl.expand_dims(artanh_v / norm_v_clamped, 1)
        t_v = v_val * scale_v

        # acc_v = acc_v * exp_prev + sum_j exp_scores[j] * t_v[j, :]
        weighted_tv = tl.expand_dims(exp_scores, 1) * t_v
        chunk_acc = tl.sum(weighted_tv, axis=0)

        acc_v = acc_v * exp_prev + chunk_acc
        m = new_m

    out_tangent = acc_v / d_sum

    ot_sq = tl.sum(tl.where(mask_d, out_tangent * out_tangent, 0.0))
    norm_ot = tl.sqrt(ot_sq)
    norm_ot_clamped = tl.maximum(norm_ot, 1e-7)

    exp_2u = tl.exp(2.0 * norm_ot_clamped)
    tanh_ot = (exp_2u - 1.0) / (exp_2u + 1.0)
    out = out_tangent * (tanh_ot / norm_ot_clamped)

    out_offset = b * (N * H * d_h) + i * (H * d_h) + h * d_h + offs_d
    tl.store(Out_ptr + out_offset, out, mask=mask_d)


def triton_fused_poincare_multihead_attention(
    q: torch.Tensor,        # [B, N, H, d_h]
    k: torch.Tensor,        # [B, N, H, d_h]
    v: torch.Tensor,        # [B, N, H, d_h]
    eps: float = 1e-5,
) -> torch.Tensor:
    B, N, H, d_h = q.shape
    assert q.is_cuda and k.is_cuda and v.is_cuda, "All tensors must be on CUDA"

    q = q.contiguous()
    k = k.contiguous()
    v = v.contiguous()
    out = torch.empty_like(q)

    BLOCK_D = 1
    while BLOCK_D < d_h:
        BLOCK_D *= 2

    BLOCK_N = 32 if N >= 32 else N
    scale = 1.0 / (d_h ** 0.5)
    total_programs = B * H * N

    _poincare_mha_tiled_kernel[(total_programs,)](
        q, k, v, out,
        scale=float(scale), eps=float(eps),
        B=B, N=N, H=H, d_h=d_h,
        BLOCK_N=BLOCK_N, BLOCK_D=BLOCK_D,
        num_warps=4,
    )

    return out


if __name__ == "__main__":
    print("=" * 80)
    print("IMF Triton Fused Poincaré Multi-Head Gyro-Self-Attention Benchmark (Tiled)")
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print("=" * 80)

    torch.manual_seed(42)
    device = "cuda"

    B = 16
    N = 128
    H = 8
    d_h = 32

    def rand_ball(shape):
        t = torch.randn(shape, device=device, dtype=torch.float32)
        norm = torch.norm(t, dim=-1, keepdim=True).clamp(min=1e-5)
        return (t / norm) * torch.rand((*shape[:-1], 1), device=device) * 0.85

    q = rand_ball((B, N, H, d_h))
    k = rand_ball((B, N, H, d_h))
    v = rand_ball((B, N, H, d_h))

    # 1. Numerical Correctness
    print(f"1. Validating Numerical Equivalence against PyTorch Reference (B={B}, N={N}, H={H}, d_h={d_h})...")
    out_ref = poincare_multihead_attention_torch(q, k, v)
    out_tri = triton_fused_poincare_multihead_attention(q, k, v)

    max_err = torch.max(torch.abs(out_ref - out_tri)).item()
    print(f"   Max Abs Error: {max_err:.2e}")
    assert max_err < 1e-4, f"Numerical divergence in Multi-Head Gyro-Attention: {max_err}"
    print("   ✓ 100.0% Numerical Parity Confirmed.")

    # 2. Hardware Benchmarking
    print("\n2. Executing Workstation Hardware Benchmark (RTX 5060 Ti)...")
    warmup = 10
    iters = 50

    for _ in range(warmup):
        _ = poincare_multihead_attention_torch(q, k, v)
        _ = triton_fused_poincare_multihead_attention(q, k, v)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_multihead_attention_torch(q, k, v)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_fused_poincare_multihead_attention(q, k, v)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    total_tokens = B * N
    tp_torch = total_tokens / t_torch
    tp_triton = total_tokens / t_triton
    speedup = t_torch / t_triton

    print(f"   PyTorch Baseline Latency: {t_torch*1e6:8.2f} us | Throughput: {tp_torch/1e6:6.2f} M tokens/s")
    print(f"   Triton Fused Latency:     {t_triton*1e6:8.2f} us | Throughput: {tp_triton/1e6:6.2f} M tokens/s")
    print(f"   Hardware Speedup:         {speedup:8.2f}x")
    print("=" * 80)
