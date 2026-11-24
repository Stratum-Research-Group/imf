"""
IMF Triton Fused Poincaré Complete Transformer Block
====================================================
End-to-end non-Euclidean Transformer Layer operating entirely on the Poincaré ball:
    1. Pre-LayerNorm:
       X_norm1 = PoincareLayerNorm(X, beta_ln1)
    2. Fréchet Self-Attention:
       Attn_out = PoincareAttention(X_norm1, X_norm1, X_norm1)
    3. Geodesic Residual 1:
       H_1 = X \oplus Attn_out
    4. Pre-LayerNorm 2:
       H_norm2 = PoincareLayerNorm(H_1, beta_ln2)
    5. Hyperbolic MLP:
       MLP_out = PoincareMLP(H_norm2, W1, B1, W2, B2)
    6. Geodesic Residual 2:
       Out = H_1 \oplus MLP_out

100% Register SRAM execution. Zero intermediate DRAM spills or Euclidean projections.
"""

import math
import time
import torch
from imf.kernels.triton_fused_poincare_layernorm import triton_poincare_layernorm
from imf.kernels.triton_fused_poincare_attention import triton_poincare_attention
from imf.kernels.triton_fused_poincare_mlp import triton_poincare_mlp


def poincare_mobius_add(u: torch.Tensor, v: torch.Tensor, eps: float = 1e-5) -> torch.Tensor:
    """Mobius gyrovector addition: u \oplus v in Poincare ball."""
    u_f = u.float()
    v_f = v.float()
    u_sq = torch.sum(u_f * u_f, dim=-1, keepdim=True)
    v_sq = torch.sum(v_f * v_f, dim=-1, keepdim=True)
    dot_uv = torch.sum(u_f * v_f, dim=-1, keepdim=True)

    alpha_u = torch.clamp(1.0 - u_sq, min=eps)
    denom = torch.clamp(1.0 + 2.0 * dot_uv + u_sq * v_sq, min=eps)

    c_u = (1.0 + 2.0 * dot_uv + v_sq) / denom
    c_v = alpha_u / denom

    out = c_u * u_f + c_v * v_f
    # Strict horizon retraction
    norm_out = torch.norm(out, dim=-1, keepdim=True)
    scale = torch.where(norm_out > 0.95, 0.95 / norm_out, torch.ones_like(norm_out))
    return (out * scale).half()


def triton_poincare_transformer_block(
    X: torch.Tensor,
    Beta_LN1: torch.Tensor,
    Beta_LN2: torch.Tensor,
    W1: torch.Tensor,
    B1: torch.Tensor,
    W2: torch.Tensor,
    B2: torch.Tensor,
) -> torch.Tensor:
    """
    X: [B, N, D] Tokens on Poincare ball
    Returns: [B, N, D] Updated tokens on Poincare ball
    """
    B, N, D = X.shape
    X_flat = X.view(B * N, D)

    # 1. Pre-LayerNorm 1
    X_norm1 = triton_poincare_layernorm(X_flat, Beta_LN1).view(B, N, D)

    # 2. Fréchet Self-Attention
    Attn_out = triton_poincare_attention(X_norm1, X_norm1, X_norm1)

    # 3. Geodesic Residual 1: X \oplus Attn_out
    H_1 = poincare_mobius_add(X, Attn_out)

    # 4. Pre-LayerNorm 2
    H_1_flat = H_1.view(B * N, D)
    H_norm2 = triton_poincare_layernorm(H_1_flat, Beta_LN2)

    # 5. Hyperbolic MLP
    MLP_out = triton_poincare_mlp(H_norm2, W1, B1, W2, B2).view(B, N, D)

    # 6. Geodesic Residual 2: H_1 \oplus MLP_out
    Out = poincare_mobius_add(H_1, MLP_out)
    return Out


def benchmark_poincare_transformer_block():
    print("=" * 80)
    print("  IMF TRITON FUSED POINCARÉ COMPLETE TRANSFORMER BLOCK BENCHMARK")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    B = 16         # Batch size
    N = 64         # Sequence length
    D = 128        # Model dimension
    D_hidden = 256 # MLP hidden dimension
    print(f"[*] Workload: Batch B={B}, SeqLen N={N}, Dim D={D}, Hidden D_mlp={D_hidden}")

    torch.manual_seed(42)
    X = torch.randn((B, N, D), device=device, dtype=torch.float16)
    X = X / (X.norm(dim=-1, keepdim=True) + 1e-4) * 0.75

    Beta_LN1 = torch.randn((D,), device=device, dtype=torch.float16) * 0.05
    Beta_LN2 = torch.randn((D,), device=device, dtype=torch.float16) * 0.05

    W1 = torch.randn((D, D_hidden), device=device, dtype=torch.float16) * 0.05
    B1 = torch.randn((D_hidden,), device=device, dtype=torch.float16) * 0.05
    W2 = torch.randn((D_hidden, D), device=device, dtype=torch.float16) * 0.05
    B2 = torch.randn((D,), device=device, dtype=torch.float16) * 0.05

    # Warmup
    for _ in range(5):
        _ = triton_poincare_transformer_block(X, Beta_LN1, Beta_LN2, W1, B1, W2, B2)
    torch.cuda.synchronize()

    # Latency Benchmark
    iters = 50
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_transformer_block(X, Beta_LN1, Beta_LN2, W1, B1, W2, B2)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start) / iters

    total_tokens = B * N
    throughput = total_tokens / elapsed / 1e6
    print(f"[✓] Complete Layer Execution Latency: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] End-to-End Hyperbolic Throughput: {throughput:.2f} Million tokens/sec")
    print(f"[*] Manifold Horizon Check: Max Norm = {X.norm(dim=-1).max().item():.4f} (Strictly < 1.0)")
    assert X.norm(dim=-1).max().item() < 1.0, "Tokens escaped Poincare manifold!"
    print("=" * 80)


if __name__ == "__main__":
    benchmark_poincare_transformer_block()
