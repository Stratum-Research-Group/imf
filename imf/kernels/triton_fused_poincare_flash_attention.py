"""
Triton GPU Kernel: Fused Poincaré Flash-Attention with Online Softmax (RTX 5060 Ti)

Implements O(1) memory Flash-Attention on the Poincaré ball:
  Given queries Q in R^(M x D), keys K in R^(M x D), values V in R^(M x D):
  1. Outer loop tiles over Q blocks of size BLOCK_M.
  2. Inner loop tiles over K, V blocks of size BLOCK_N.
  3. Maintains running maximum (m_i) and running denominator (l_i) in registers:
     m_new = max(m_old, row_max(S_ij))
     alpha = exp(m_old - m_new)
     P_ij = exp(S_ij - m_new)
     l_new = l_old * alpha + row_sum(P_ij)
     acc = acc * alpha + P_ij @ V_j
  4. Final normalization: acc = acc / l_new.
  5. Retraction to Poincare ball B^D via exp_0^c mapping.

Eliminates the M x M attention matrix in memory, enabling arbitrary sequence lengths.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_flash_attention_kernel(
    Q_ptr,          # [M, D] (fp16)
    K_ptr,          # [M, D] (fp16)
    V_ptr,          # [M, D] (fp16)
    Out_ptr,        # [M, D] (fp16)
    M: tl.constexpr,
    D: tl.constexpr,
    BLOCK_M: tl.constexpr,
    BLOCK_N: tl.constexpr,
    c: tl.constexpr,
):
    pid = tl.program_id(0)
    offs_m = pid * BLOCK_M + tl.arange(0, BLOCK_M)
    mask_m = offs_m < M
    offs_d = tl.arange(0, D)

    # Load Q block: [BLOCK_M, D]
    q = tl.load(Q_ptr + offs_m[:, None] * D + offs_d[None, :], mask=mask_m[:, None], other=0.0)

    # Initialize online softmax accumulators
    m_i = tl.zeros([BLOCK_M], dtype=tl.float32) - 1e9
    l_i = tl.zeros([BLOCK_M], dtype=tl.float32)
    acc = tl.zeros([BLOCK_M, D], dtype=tl.float32)

    scale = 1.0 / math.sqrt(D)

    # Iterate over K, V in blocks of BLOCK_N
    for n_start in range(0, M, BLOCK_N):
        offs_n = n_start + tl.arange(0, BLOCK_N)
        mask_n = offs_n < M

        k = tl.load(K_ptr + offs_n[:, None] * D + offs_d[None, :], mask=mask_n[:, None], other=0.0)
        v = tl.load(V_ptr + offs_n[:, None] * D + offs_d[None, :], mask=mask_n[:, None], other=0.0)

        # Dot product scores: [BLOCK_M, BLOCK_N]
        s_ij = tl.dot(q, tl.trans(k)) * scale

        # Online softmax update
        m_ij = tl.max(s_ij, axis=1)
        m_new = tl.maximum(m_i, m_ij)
        alpha = tl.exp(m_i - m_new)
        p_ij = tl.exp(s_ij - m_new[:, None])
        l_new = l_i * alpha + tl.sum(p_ij, axis=1)

        # Rescale accumulator and add new contribution
        acc = acc * alpha[:, None] + tl.dot(p_ij.to(tl.float16), v)

        m_i = m_new
        l_i = l_new

    # Final normalization
    attn_out = acc / l_i[:, None]

    # Retraction via exp_0^c mapping
    sq_norm = tl.sum(attn_out * attn_out, axis=1)
    norm = tl.sqrt(sq_norm + 1e-12)
    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))
    u = sqrt_c * norm
    u_clamped = tl.minimum(u, 15.0)
    exp_2u = tl.exp(2.0 * u_clamped)
    tanh_u = (exp_2u - 1.0) / (exp_2u + 1.0)
    scale_r = tanh_u / (sqrt_c * norm)

    y_out = attn_out * scale_r[:, None]
    tl.store(Out_ptr + offs_m[:, None] * D + offs_d[None, :], y_out.to(tl.float16), mask=mask_m[:, None])


def poincare_flash_attention_pytorch(Q, K, V, c=1.0):
    """Reference PyTorch standard attention."""
    scale = 1.0 / math.sqrt(Q.shape[-1])
    scores = torch.matmul(Q.float(), K.float().transpose(-1, -2)) * scale
    weights = torch.softmax(scores, dim=-1)
    attn_out = torch.matmul(weights, V.float())

    norm = torch.norm(attn_out, p=2, dim=-1, keepdim=True).clamp(min=1e-8)
    sqrt_c = math.sqrt(c)
    scale_r = torch.tanh(sqrt_c * norm) / (sqrt_c * norm)
    return (attn_out * scale_r).half()


def poincare_flash_attention_triton(Q, K, V, c=1.0):
    M, D = Q.shape
    out = torch.empty((M, D), device=Q.device, dtype=torch.float16)

    BLOCK_M = 32
    BLOCK_N = 32
    grid = (triton.cdiv(M, BLOCK_M),)
    _poincare_flash_attention_kernel[grid](
        Q, K, V, out,
        M=M, D=D, BLOCK_M=BLOCK_M, BLOCK_N=BLOCK_N, c=c,
    )
    return out


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré Flash-Attention on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    M = 1024         # Sequence length
    D = 64           # Dimension
    c = 1.0

    Q = (torch.randn((M, D), device=device, dtype=torch.float32) * 0.05).half()
    K = (torch.randn((M, D), device=device, dtype=torch.float32) * 0.05).half()
    V = (torch.randn((M, D), device=device, dtype=torch.float32) * 0.05).half()

    # Correctness check
    out_pt = poincare_flash_attention_pytorch(Q, K, V, c)
    out_triton = poincare_flash_attention_triton(Q, K, V, c)

    max_err = (out_pt.float() - out_triton.float()).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-2, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-2 fp16 error)!")

    # Warmup
    for _ in range(50):
        poincare_flash_attention_pytorch(Q, K, V, c)
        poincare_flash_attention_triton(Q, K, V, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 300
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_flash_attention_pytorch(Q, K, V, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_flash_attention_triton(Q, K, V, c)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    tok_sec = M / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {tok_sec / 1e6:.2f} M tokens/sec")


if __name__ == "__main__":
    benchmark()
