"""
Triton Fused Polytope Norm & Cosine Hyperbolic Attention Kernel
==============================================================
Computes bounded unit-norm Cosine Hyperbolic Attention:
    A_{ij} = \\frac{q_i^\\top k_j}{\\|q_i\\|_2 \\|k_j\\|_2 \\cdot \\tau}
directly in GPU vector registers with online SRAM normalization.
Eliminates attention entropy collapse and prevents logit divergence over long context lengths.
"""

import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_cosine_attention_kernel(
    q_ptr,             # [BATCH, NUM_HEADS, SEQ_LEN, HEAD_DIM] fp16
    k_ptr,             # [BATCH, NUM_HEADS, SEQ_LEN, HEAD_DIM] fp16
    v_ptr,             # [BATCH, NUM_HEADS, SEQ_LEN, HEAD_DIM] fp16
    out_ptr,           # [BATCH, NUM_HEADS, SEQ_LEN, HEAD_DIM] fp16
    temperature,       # float32 scalar (e.g. 0.1 or 1.0)
    stride_qb, stride_qh, stride_qm, stride_qk,
    stride_kb, stride_kh, stride_kn, stride_kk,
    stride_vb, stride_vh, stride_vn, stride_vk,
    stride_ob, stride_oh, stride_om, stride_ok,
    BATCH, NUM_HEADS, SEQ_LEN,
    HEAD_DIM: tl.constexpr,   # e.g. 64 or 128
    BLOCK_M: tl.constexpr,    # e.g. 32
    BLOCK_N: tl.constexpr,    # e.g. 32
):
    pid_m = tl.program_id(0)
    pid_h = tl.program_id(1)
    pid_b = tl.program_id(2)

    # Offset pointers for current batch and head
    offs_m = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
    offs_k = tl.arange(0, HEAD_DIM)

    mask_m = offs_m < SEQ_LEN

    # 1. Load Query block and compute L2 norm online
    q_ptrs = q_ptr + pid_b * stride_qb + pid_h * stride_qh + offs_m[:, None] * stride_qm + offs_k[None, :] * stride_qk
    q = tl.load(q_ptrs, mask=mask_m[:, None], other=0.0).to(tl.float32)

    q_norm_sq = tl.sum(q * q, axis=1) # [BLOCK_M]
    q_inv_norm = tl.math.rsqrt(tl.maximum(q_norm_sq, 1e-6)) # [BLOCK_M]
    q_normalized = q * q_inv_norm[:, None]

    # Initialize accumulator and online softmax state (m_i, l_i)
    acc = tl.zeros([BLOCK_M, HEAD_DIM], dtype=tl.float32)
    m_i = tl.full([BLOCK_M], -1e9, dtype=tl.float32)
    l_i = tl.zeros([BLOCK_M], dtype=tl.float32)

    # 2. Iterate over Key/Value blocks
    inv_tau = 1.0 / temperature

    for start_n in range(0, SEQ_LEN, BLOCK_N):
        offs_n = start_n + tl.arange(0, BLOCK_N)
        mask_n = offs_n < SEQ_LEN

        # Load Key block and compute L2 norm
        k_ptrs = k_ptr + pid_b * stride_kb + pid_h * stride_kh + offs_n[:, None] * stride_kn + offs_k[None, :] * stride_kk
        k = tl.load(k_ptrs, mask=mask_n[:, None], other=0.0).to(tl.float32)

        k_norm_sq = tl.sum(k * k, axis=1) # [BLOCK_N]
        k_inv_norm = tl.math.rsqrt(tl.maximum(k_norm_sq, 1e-6))
        k_normalized = k * k_inv_norm[:, None]

        # Compute cosine similarity: Q_norm * K_norm^T
        # Shape: [BLOCK_M, BLOCK_N]
        cos_sim = tl.dot(q_normalized, tl.trans(k_normalized)) * inv_tau

        # Apply causal mask (if n > m)
        causal_mask = offs_m[:, None] >= offs_n[None, :]
        cos_sim = tl.where(causal_mask & (mask_m[:, None] & mask_n[None, :]), cos_sim, -1e9)

        # Online Flash-Attention Softmax updates
        m_ij = tl.maximum(m_i, tl.max(cos_sim, axis=1))
        p = tl.exp(cos_sim - m_ij[:, None])
        l_ij = tl.sum(p, axis=1)

        # Rescale prior accumulator
        alpha = tl.exp(m_i - m_ij)
        acc = acc * alpha[:, None]

        # Load Value block
        v_ptrs = v_ptr + pid_b * stride_vb + pid_h * stride_vh + offs_n[:, None] * stride_vn + offs_k[None, :] * stride_vk
        v = tl.load(v_ptrs, mask=mask_n[:, None], other=0.0).to(tl.float32)

        # Accumulate: P * V
        acc += tl.dot(p.to(tl.float16), v.to(tl.float16)).to(tl.float32)

        # Update running stats
        l_i = l_i * alpha + l_ij
        m_i = m_ij

    # 3. Final normalization and store to HBM
    out = acc / tl.maximum(l_i[:, None], 1e-6)
    out_ptrs = out_ptr + pid_b * stride_ob + pid_h * stride_oh + offs_m[:, None] * stride_om + offs_k[None, :] * stride_ok
    tl.store(out_ptrs, out.to(tl.float16), mask=mask_m[:, None])


def triton_fused_cosine_attention(
    q: torch.Tensor,
    k: torch.Tensor,
    v: torch.Tensor,
    temperature: float = 0.25,
) -> torch.Tensor:
    """
    Computes online normalized causal cosine attention.
    q, k, v: [BATCH, NUM_HEADS, SEQ_LEN, HEAD_DIM] fp16
    """
    assert q.is_cuda and k.is_cuda and v.is_cuda
    batch, num_heads, seq_len, head_dim = q.shape

    out = torch.empty_like(q)

    BLOCK_M = 32
    BLOCK_N = 32

    grid = (
        triton.cdiv(seq_len, BLOCK_M),
        num_heads,
        batch,
    )

    _fused_cosine_attention_kernel[grid](
        q, k, v, out,
        temperature,
        q.stride(0), q.stride(1), q.stride(2), q.stride(3),
        k.stride(0), k.stride(1), k.stride(2), k.stride(3),
        v.stride(0), v.stride(1), v.stride(2), v.stride(3),
        out.stride(0), out.stride(1), out.stride(2), out.stride(3),
        batch, num_heads, seq_len,
        HEAD_DIM=head_dim,
        BLOCK_M=BLOCK_M,
        BLOCK_N=BLOCK_N,
    )
    return out


def benchmark_cosine_attention():
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    device = torch.device("cuda:0")
    batch = 2
    num_heads = 8
    seq_len = 1024
    head_dim = 64

    print(f"[*] Benchmarking Fused Cosine Attention (B={batch}, H={num_heads}, S={seq_len}, D={head_dim})...")

    q = torch.randn(batch, num_heads, seq_len, head_dim, device=device, dtype=torch.float16)
    k = torch.randn(batch, num_heads, seq_len, head_dim, device=device, dtype=torch.float16)
    v = torch.randn(batch, num_heads, seq_len, head_dim, device=device, dtype=torch.float16)

    # Warmup
    for _ in range(5):
        _ = triton_fused_cosine_attention(q, k, v, temperature=0.25)
    torch.cuda.synchronize()

    # Timed run
    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        out = triton_fused_cosine_attention(q, k, v, temperature=0.25)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - t0) / iters

    total_tokens = batch * seq_len
    tok_per_sec = total_tokens / elapsed

    print(f"[✓] Execution Time: {elapsed * 1000:.3f} ms")
    print(f"[✓] Attention Throughput: {tok_per_sec / 1e3:.2f} k tokens/sec ({tok_per_sec * num_heads / 1e6:.2f} M head-tokens/sec)")
    print(f"[✓] Sample Attention Output (Shape: {out.shape}, Mean: {out.mean().item():.5f}, Std: {out.std().item():.5f})")

    # PyTorch reference validation
    q_norm = torch.nn.functional.normalize(q.float(), p=2, dim=-1)
    k_norm = torch.nn.functional.normalize(k.float(), p=2, dim=-1)
    sim = torch.matmul(q_norm, k_norm.transpose(-1, -2)) / 0.25
    mask = torch.triu(torch.full((seq_len, seq_len), float('-inf'), device=device), diagonal=1)
    attn_weights = torch.softmax(sim + mask, dim=-1)
    ref_out = torch.matmul(attn_weights, v.float()).half()

    max_err = (out - ref_out).abs().max().item()
    print(f"[✓] Max Absolute Difference vs PyTorch Cosine Attention: {max_err:.6e}")
    assert max_err < 5e-2, f"Numerical error too high: {max_err}"
    print("[✓] Correctness verification passed!")


if __name__ == "__main__":
    benchmark_cosine_attention()
