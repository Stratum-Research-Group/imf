"""
IMF Triton Fused Poincaré Weighted Fréchet Attention Kernel
===========================================================
Computes hyperbolic attention directly on the Poincaré manifold:
    1. Distance matrix: D_{i, j} = d_D(Q_i, K_j)^2
    2. Attention weights: alpha_{i, j} = softmax(-D_{i, j} / tau)
    3. Weighted Fréchet Aggregation via tangent-space retraction:
       Attn(Q)_i = exp_{K_i}( sum_j alpha_{i, j} * log_{K_i}(V_j) )

Performs closed-loop Riemannian attention in register SRAM with zero DRAM spills.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_poincare_attention_kernel(
    Q_ptr, K_ptr, V_ptr, Out_ptr,
    B, N, D,
    stride_qb, stride_qn, stride_qd,
    stride_kb, stride_kn, stride_kd,
    stride_vb, stride_vn, stride_vd,
    stride_ob, stride_on, stride_od,
    tau: tl.constexpr,
    eps: tl.constexpr,
    BLOCK_N: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    pid_b = tl.program_id(0)
    pid_q = tl.program_id(1)

    offs_d = tl.arange(0, BLOCK_D)
    mask_d = offs_d < D

    # Load Query Q [D]
    q_ptrs = Q_ptr + (pid_b * stride_qb + pid_q * stride_qn + offs_d * stride_qd)
    q_val = tl.load(q_ptrs, mask=mask_d, other=0.0).to(tl.float32)
    norm_q_sq = tl.sum(q_val * q_val)
    alpha_q = tl.maximum(1.0 - norm_q_sq, eps)

    # First pass: compute distance to each Key and online Softmax
    # We maintain max_neg_dist and sum_exp for online softmax
    max_score = -1e9
    sum_exp = 0.0

    # Running accumulator for tangent vector sum: sum_j alpha_{i,j} * log_Q(V_j)
    # We use Q as the tangent base point
    lambda_q = 2.0 / alpha_q
    tangent_acc = tl.zeros([BLOCK_D], dtype=tl.float32)

    # Iterate over Key/Value sequence length N
    for j in range(N):
        k_ptrs = K_ptr + (pid_b * stride_kb + j * stride_kn + offs_d * stride_kd)
        k_val = tl.load(k_ptrs, mask=mask_d, other=0.0).to(tl.float32)
        norm_k_sq = tl.sum(k_val * k_val)
        alpha_k = tl.maximum(1.0 - norm_k_sq, eps)

        diff = q_val - k_val
        diff_sq = tl.sum(diff * diff)
        denom = tl.maximum(alpha_q * alpha_k, eps * eps)

        arg_z = tl.maximum(1.0 + 2.0 * diff_sq / denom, 1.0)
        sqrt_term = tl.sqrt(arg_z * arg_z - 1.0)
        dist = tl.log(arg_z + sqrt_term)
        dist_sq = dist * dist

        score = -dist_sq / tau

        # Online softmax update
        new_max = tl.maximum(max_score, score)
        exp_shift = tl.exp(max_score - new_max)
        exp_curr = tl.exp(score - new_max)
        sum_exp = sum_exp * exp_shift + exp_curr
        max_score = new_max

        # Load Value V [D] and compute log_Q(V_j)
        v_ptrs = V_ptr + (pid_b * stride_vb + j * stride_vn + offs_d * stride_vd)
        v_val = tl.load(v_ptrs, mask=mask_d, other=0.0).to(tl.float32)
        norm_v_sq = tl.sum(v_val * v_val)
        dot_qv = tl.sum(q_val * v_val)

        denom_add = tl.maximum(1.0 + 2.0 * dot_qv + norm_q_sq * norm_v_sq, eps)
        c_q = (1.0 + 2.0 * dot_qv + norm_v_sq) / denom_add
        c_v = alpha_q / denom_add

        delta_v = -c_q * q_val + c_v * v_val
        norm_delta = tl.sqrt(tl.maximum(tl.sum(delta_v * delta_v), 0.0))
        safe_norm = tl.minimum(norm_delta, 1.0 - eps)
        artanh_v = 0.5 * tl.log((1.0 + safe_norm) / tl.maximum(1.0 - safe_norm, eps))
        scale_v = tl.where(norm_delta > eps, alpha_q * artanh_v / norm_delta, alpha_q)
        log_v = scale_v * delta_v

        # Update tangent accumulator with unnormalized weight exp_curr
        tangent_acc = tangent_acc * exp_shift + exp_curr * log_v

    # Final normalized tangent vector
    inv_sum = 1.0 / tl.maximum(sum_exp, eps)
    v_tangent = tangent_acc * inv_sum

    # Project tangent vector back to Poincare ball via exp_Q(v_tangent)
    norm_vt = tl.sqrt(tl.maximum(tl.sum(v_tangent * v_tangent), 0.0))
    arg_exp = (lambda_q * norm_vt) / 2.0
    tanh_exp = (1.0 - tl.exp(-2.0 * arg_exp)) / tl.maximum(1.0 + tl.exp(-2.0 * arg_exp), eps)
    tanh_exp = tl.minimum(tanh_exp, 1.0 - eps)

    scale_w = tl.where(norm_vt > eps, tanh_exp / norm_vt, 0.0)
    w = scale_w * v_tangent
    norm_w_sq = tanh_exp * tanh_exp
    dot_qw = tl.sum(q_val * w)

    denom_out = tl.maximum(1.0 + 2.0 * dot_qw + norm_q_sq * norm_w_sq, eps)
    c_q_out = (1.0 + 2.0 * dot_qw + norm_w_sq) / denom_out
    c_w_out = alpha_q / denom_out

    out_val = c_q_out * q_val + c_w_out * w

    out_ptrs = Out_ptr + (pid_b * stride_ob + pid_q * stride_on + offs_d * stride_od)
    tl.store(out_ptrs, out_val.to(tl.float16), mask=mask_d)


def triton_poincare_attention(Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor, tau: float = 1.0, eps: float = 1e-5) -> torch.Tensor:
    """
    Q: [B, N_q, D]
    K: [B, N_k, D]
    V: [B, N_k, D]
    Returns: [B, N_q, D] Hyperbolic attended representations
    """
    assert Q.is_cuda and K.is_cuda and V.is_cuda
    B, N_q, D = Q.shape
    N_k = K.shape[1]

    Out = torch.empty_like(Q)
    BLOCK_D = min(128, triton.next_power_of_2(D))
    BLOCK_N = 64

    grid = (B, N_q)

    _fused_poincare_attention_kernel[grid](
        Q, K, V, Out,
        B, N_k, D,
        Q.stride(0), Q.stride(1), Q.stride(2),
        K.stride(0), K.stride(1), K.stride(2),
        V.stride(0), V.stride(1), V.stride(2),
        Out.stride(0), Out.stride(1), Out.stride(2),
        tau=tau, eps=eps,
        BLOCK_N=BLOCK_N,
        BLOCK_D=BLOCK_D,
    )
    return Out


def benchmark_poincare_attention():
    print("=" * 80)
    print("  IMF TRITON FUSED POINCARÉ WEIGHTED FRÉCHET ATTENTION BENCHMARK")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    B = 16         # Batch size
    N_q = 64       # Query tokens
    N_k = 64       # Key/Value tokens
    D = 128        # Embedding dimension
    print(f"[*] Workload: Batch B={B}, SeqLen N={N_q}, Dim D={D}")

    torch.manual_seed(42)
    Q = torch.randn((B, N_q, D), device=device, dtype=torch.float16)
    Q = Q / (Q.norm(dim=-1, keepdim=True) + 1e-4) * 0.80

    K = torch.randn((B, N_k, D), device=device, dtype=torch.float16)
    K = K / (K.norm(dim=-1, keepdim=True) + 1e-4) * 0.80

    V = torch.randn((B, N_k, D), device=device, dtype=torch.float16)
    V = V / (V.norm(dim=-1, keepdim=True) + 1e-4) * 0.80

    # Warmup
    for _ in range(10):
        _ = triton_poincare_attention(Q, K, V)
    torch.cuda.synchronize()

    # Latency Benchmark
    iters = 100
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_attention(Q, K, V)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start) / iters

    total_tokens = B * N_q
    throughput = total_tokens / elapsed / 1e6
    print(f"[✓] Execution Latency: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] Hyperbolic Attention Throughput: {throughput:.2f} Million tokens/sec")
    print("=" * 80)


if __name__ == "__main__":
    benchmark_poincare_attention()
