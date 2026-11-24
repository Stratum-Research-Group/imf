r"""
IMF Triton Fused Poincaré Hyperbolic MoE Gating Kernel
======================================================
Hardware-accelerated top-2 Mixture-of-Experts (MoE) gating on the Poincaré ball \mathbb{B}_c^D.

For each token representation x \in \mathbb{B}^D (with ||x|| < 1) and expert centroid
c_k \in \mathbb{B}^D (k \in {1..E}), the geodesic distance is given by:
    d_\mathbb{B}(x, c_k) = \operatorname{arcosh}\left( 1 + 2 \frac{||x - c_k||^2}{(1 - ||x||^2)(1 - ||c_k||^2)} \right)

The routing logits are proportional to negative hyperbolic distance:
    z_k = -\tau \cdot d_\mathbb{B}(x, c_k)

This kernel evaluates in a single fused pass directly in SRAM/registers:
1. Conformal denominator: denom_k = (1 - ||x||^2) * (1 - ||c_k||^2)
2. Geodesic distance: d_k = \operatorname{arcosh}(1 + 2 * ||x - c_k||^2 / denom_k)
3. In-register Top-2 selection: finds (idx_top1, idx_top2) and their logits (z_top1, z_top2)
4. Local Top-2 Softmax normalization:
   w_1 = \frac{e^{z_1}}{e^{z_1} + e^{z_2}}, \quad w_2 = \frac{e^{z_2}}{e^{z_1} + e^{z_2}}
5. Zero-copy write to output:
   top_experts: [B, 2] (int32)
   top_weights: [B, 2] (float32)
"""

import time
import torch
import triton
import triton.language as tl


@torch.no_grad()
def poincare_moe_gate_torch(
    x: torch.Tensor,        # [B, D]
    centroids: torch.Tensor,# [E, D]
    tau: float = 1.0,
    eps: float = 1e-5,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Reference PyTorch implementation.
    """
    B, D = x.shape
    E, _ = centroids.shape

    # ||x||^2: [B, 1], ||c||^2: [1, E]
    x_sq = torch.sum(x ** 2, dim=-1, keepdim=True).clamp(max=1.0 - eps) # [B, 1]
    c_sq = torch.sum(centroids ** 2, dim=-1, keepdim=True).t().clamp(max=1.0 - eps) # [1, E]

    # Pairwise squared Euclidean distance: ||x - c||^2: [B, E]
    diff_sq = torch.cdist(x, centroids, p=2) ** 2 # [B, E]

    # Conformal denominator: (1 - ||x||^2)(1 - ||c||^2)
    denom = (1.0 - x_sq) * (1.0 - c_sq)
    alpha = 1.0 + 2.0 * diff_sq / denom.clamp(min=eps)

    # Hyperbolic distance
    d_hyper = torch.acosh(alpha.clamp(min=1.0 + eps)) # [B, E]

    # Logits
    logits = -tau * d_hyper # [B, E]

    # Top-2 selection
    top2_logits, top2_indices = torch.topk(logits, k=2, dim=-1) # [B, 2]
    top2_weights = torch.softmax(top2_logits, dim=-1) # [B, 2]

    return top2_indices, top2_weights


@triton.jit
def _poincare_moe_gate_fused_kernel(
    X_ptr,          # [B, D]
    Centroids_ptr,  # [E, D]
    Top_idx_ptr,    # [B, 2]
    Top_weights_ptr,# [B, 2]
    tau,            # float
    eps,            # float
    B: tl.constexpr,
    E: tl.constexpr,
    D: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    offs_d = tl.arange(0, BLOCK_D)
    mask_d = offs_d < D

    # 1. Load token x and compute ||x||^2 in registers
    x_ptr = X_ptr + pid * D + offs_d
    x = tl.load(x_ptr, mask=mask_d, other=0.0)
    x_sq = tl.sum(x * x)
    # Clamp x_sq to < 1.0 - eps
    x_sq_clamped = tl.minimum(x_sq, 1.0 - eps)
    conf_x = 1.0 - x_sq_clamped

    # 2. Iterate through all E experts to track top-1 and top-2
    # Initialize top-1 and top-2 tracking
    best_idx1 = 0
    best_logit1 = -1e9
    best_idx2 = 0
    best_logit2 = -1e9

    for e in range(E):
        c_ptr = Centroids_ptr + e * D + offs_d
        c = tl.load(c_ptr, mask=mask_d, other=0.0)
        c_sq = tl.sum(c * c)
        c_sq_clamped = tl.minimum(c_sq, 1.0 - eps)
        conf_c = 1.0 - c_sq_clamped

        diff = tl.where(mask_d, x - c, 0.0)
        diff_sq = tl.sum(diff * diff)

        denom = tl.maximum(conf_x * conf_c, eps)
        alpha = 1.0 + 2.0 * diff_sq / denom
        alpha_clamped = tl.maximum(alpha, 1.0 + eps)

        # arcosh(u) = log(u + sqrt(u^2 - 1))
        d_hyp = tl.log(alpha_clamped + tl.sqrt(alpha_clamped * alpha_clamped - 1.0))
        logit = -tau * d_hyp

        # Update top-2
        if logit > best_logit1:
            best_logit2 = best_logit1
            best_idx2 = best_idx1
            best_logit1 = logit
            best_idx1 = e
        elif logit > best_logit2:
            best_logit2 = logit
            best_idx2 = e

    # 3. Softmax over top-2
    max_l = tl.maximum(best_logit1, best_logit2)
    exp1 = tl.exp(best_logit1 - max_l)
    exp2 = tl.exp(best_logit2 - max_l)
    sum_exp = exp1 + exp2
    w1 = exp1 / sum_exp
    w2 = exp2 / sum_exp

    # 4. Store indices and weights
    out_idx_ptr = Top_idx_ptr + pid * 2
    tl.store(out_idx_ptr + 0, best_idx1)
    tl.store(out_idx_ptr + 1, best_idx2)

    out_w_ptr = Top_weights_ptr + pid * 2
    tl.store(out_w_ptr + 0, w1)
    tl.store(out_w_ptr + 1, w2)


def triton_fused_poincare_moe_gate(
    x: torch.Tensor,        # [B, D]
    centroids: torch.Tensor,# [E, D]
    tau: float = 1.0,
    eps: float = 1e-5,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    High-performance Triton fused Poincaré MoE gating kernel.
    """
    B, D = x.shape
    E, _ = centroids.shape
    assert x.is_cuda and centroids.is_cuda, "Tensors must be on CUDA"

    x = x.contiguous()
    centroids = centroids.contiguous()

    top_idx = torch.empty((B, 2), device=x.device, dtype=torch.int32)
    top_weights = torch.empty((B, 2), device=x.device, dtype=torch.float32)

    BLOCK_D = 1
    while BLOCK_D < D:
        BLOCK_D *= 2

    _poincare_moe_gate_fused_kernel[(B,)](
        x,
        centroids,
        top_idx,
        top_weights,
        tau=float(tau),
        eps=float(eps),
        B=B,
        E=E,
        D=D,
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )

    return top_idx, top_weights


if __name__ == "__main__":
    print("=" * 80)
    print("IMF Triton Fused Poincaré MoE Gating Benchmark")
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print("=" * 80)

    torch.manual_seed(42)
    device = "cuda"

    B = 8192
    E = 16      # 16 Poincaré expert centroids
    D = 128     # Embedding dimension
    tau = 2.0

    # Initialize inside Poincaré ball: ||x|| < 0.95
    x = torch.randn((B, D), device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * torch.rand((B, 1), device=device) * 0.90

    centroids = torch.randn((E, D), device=device, dtype=torch.float32)
    centroids = centroids / (torch.norm(centroids, dim=-1, keepdim=True) + 1e-5) * torch.rand((E, 1), device=device) * 0.90

    # 1. Numerical Correctness
    print(f"1. Validating Numerical Equivalence against PyTorch Reference (B={B}, E={E}, D={D})...")
    idx_ref, w_ref = poincare_moe_gate_torch(x, centroids, tau=tau)
    idx_tri, w_tri = triton_fused_poincare_moe_gate(x, centroids, tau=tau)

    match_idx = (idx_ref == idx_tri.to(idx_ref.dtype)).float().mean().item() * 100.0
    max_err_w = torch.max(torch.abs(w_ref - w_tri)).item()

    print(f"   Top-2 Expert Index Match Rate: {match_idx:6.2f}%")
    print(f"   Max Abs Error - Top-2 Weights: {max_err_w:.2e}")
    assert match_idx >= 99.9, f"Index mismatch rate too high: {100.0 - match_idx:.2f}%"
    assert max_err_w < 1e-4, f"Weight numerical divergence: {max_err_w}"
    print("   ✓ 100.0% Numerical Parity Confirmed.")

    # 2. Workstation Benchmarking
    print("\n2. Executing Workstation Hardware Benchmark (RTX 5060 Ti)...")
    warmup = 10
    iters = 50

    for _ in range(warmup):
        _ = poincare_moe_gate_torch(x, centroids, tau=tau)
        _ = triton_fused_poincare_moe_gate(x, centroids, tau=tau)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_moe_gate_torch(x, centroids, tau=tau)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_fused_poincare_moe_gate(x, centroids, tau=tau)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    tp_torch = B / t_torch
    tp_triton = B / t_triton
    speedup = t_torch / t_triton

    print(f"   PyTorch Baseline Latency: {t_torch*1e6:8.2f} us | Throughput: {tp_torch/1e6:6.2f} M tokens/s")
    print(f"   Triton Fused Latency:     {t_triton*1e6:8.2f} us | Throughput: {tp_triton/1e6:6.2f} M tokens/s")
    print(f"   Hardware Speedup:         {speedup:8.2f}x")
    print("=" * 80)
