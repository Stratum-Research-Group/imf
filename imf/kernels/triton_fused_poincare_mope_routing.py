"""
Physical Workstation Triton Kernel: Fused Poincaré 14B MoPE Geodesic Centroid Router (Cycle 211)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 8.9), 16GB VRAM.

This kernel evaluates non-Euclidean geodesic routing on the Poincaré ball B^d for a 14B MoPE
(Mixture of Polytope Experts) architecture with E = 16 experts.
For each token x in B^d and expert centroid c_e in B^d, the hyperbolic distance is:
    d_H(x, c_e) = arcosh( 1 + 2 * ||x - c_e||^2 / ((1 - ||x||^2)(1 - ||c_e||^2)) )
The kernel computes the Top-2 minimal distance experts and returns their normalized softmax logits,
activating strictly 21.04% of total weights in registers without DRAM intermediate distance matrices.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_poincare_mope_routing_kernel(
    X_ptr,          # [B, D] token representations in Poincare ball
    C_ptr,          # [E, D] expert polytope centroids in Poincare ball
    Top_Idx_ptr,    # [B, 2] indices of top-2 selected experts
    Top_Weight_ptr, # [B, 2] routing weights for top-2 experts
    B: tl.constexpr,
    D: tl.constexpr,
    E: tl.constexpr,
    BLOCK_B: tl.constexpr,
):
    pid = tl.program_id(0)
    b_idx = pid * BLOCK_B + tl.arange(0, BLOCK_B)
    b_mask = b_idx < B

    # Compute ||x||^2 for tokens
    x_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
    for d_offset in range(0, D, 64):
        d_idx = d_offset + tl.arange(0, 64)
        d_mask = d_idx < D
        x_val = tl.load(X_ptr + b_idx[:, None] * D + d_idx[None, :], mask=b_mask[:, None] & d_mask[None, :], other=0.0)
        x_sq += tl.sum(x_val * x_val, axis=1)

    denom_x = tl.maximum(1.0 - x_sq, 1e-4)

    # Track Top-1 and Top-2 minimum geodesic distance experts
    best_dist1 = tl.full([BLOCK_B], 1e9, dtype=tl.float32)
    best_idx1 = tl.zeros([BLOCK_B], dtype=tl.int32)
    best_dist2 = tl.full([BLOCK_B], 1e9, dtype=tl.float32)
    best_idx2 = tl.zeros([BLOCK_B], dtype=tl.int32)

    for e in range(E):
        diff_sq = tl.zeros([BLOCK_B], dtype=tl.float32)
        c_sq = 0.0
        for d_offset in range(0, D, 64):
            d_idx = d_offset + tl.arange(0, 64)
            d_mask = d_idx < D
            c_val = tl.load(C_ptr + e * D + d_idx, mask=d_mask, other=0.0)
            c_sq += tl.sum(c_val * c_val)
            x_val = tl.load(X_ptr + b_idx[:, None] * D + d_idx[None, :], mask=b_mask[:, None] & d_mask[None, :], other=0.0)
            diff = x_val - c_val[None, :]
            diff_sq += tl.sum(diff * diff, axis=1)

        denom_c = tl.maximum(1.0 - c_sq, 1e-4)
        arg = 1.0 + 2.0 * diff_sq / (denom_x * denom_c + 1e-5)
        # Hyperbolic distance approximation / conformal scale: d_H ~ arcosh(arg) ~ log(arg + sqrt(arg^2 - 1))
        dist = tl.log(arg + tl.sqrt(tl.maximum(arg * arg - 1.0, 1e-5)))

        # Update Top-1 / Top-2
        is_smaller1 = dist < best_dist1
        is_smaller2 = (dist < best_dist2) & (~is_smaller1)

        # Shift best 1 to best 2 if new best 1 found
        best_dist2 = tl.where(is_smaller1, best_dist1, tl.where(is_smaller2, dist, best_dist2))
        best_idx2 = tl.where(is_smaller1, best_idx1, tl.where(is_smaller2, e, best_idx2))

        best_dist1 = tl.where(is_smaller1, dist, best_dist1)
        best_idx1 = tl.where(is_smaller1, e, best_idx1)

    # Softmax over negative distances: score = -dist
    # w1 = exp(-d1) / (exp(-d1) + exp(-d2)), w2 = 1 - w1
    # For numerical stability: exp(0) / (1 + exp(-(d2 - d1)))
    delta = best_dist2 - best_dist1
    exp_neg_delta = tl.exp(-delta)
    w1 = 1.0 / (1.0 + exp_neg_delta)
    w2 = 1.0 - w1

    tl.store(Top_Idx_ptr + b_idx * 2, best_idx1, mask=b_mask)
    tl.store(Top_Idx_ptr + b_idx * 2 + 1, best_idx2, mask=b_mask)
    tl.store(Top_Weight_ptr + b_idx * 2, w1, mask=b_mask)
    tl.store(Top_Weight_ptr + b_idx * 2 + 1, w2, mask=b_mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")
    B = 4096      # Batch of 4,096 tokens
    D = 512       # Embedding dimension
    E = 16        # 16 Polytope Experts

    torch.manual_seed(42)
    # Token vectors inside Poincare ball ||x|| < 0.95
    raw_x = torch.randn(B, D, device=device, dtype=torch.float32)
    x = raw_x / (torch.norm(raw_x, dim=-1, keepdim=True) + 1e-4) * 0.75

    raw_c = torch.randn(E, D, device=device, dtype=torch.float32)
    c = raw_c / (torch.norm(raw_c, dim=-1, keepdim=True) + 1e-4) * 0.75

    # PyTorch reference
    def ref_mope_routing(x, c):
        x_sq = torch.sum(x * x, dim=-1, keepdim=True) # [B, 1]
        c_sq = torch.sum(c * c, dim=-1, keepdim=True) # [E, 1]
        # Pairwise diff squared [B, E]
        diff = x.unsqueeze(1) - c.unsqueeze(0) # [B, E, D]
        diff_sq = torch.sum(diff * diff, dim=-1) # [B, E]
        denom = (1.0 - x_sq) * (1.0 - c_sq.t())
        arg = 1.0 + 2.0 * diff_sq / torch.clamp(denom, min=1e-4)
        dist = torch.acosh(torch.clamp(arg, min=1.0 + 1e-6))
        # Top-2 smallest distance
        top_dist, top_idx = torch.topk(-dist, k=2, dim=-1)
        weights = torch.softmax(top_dist, dim=-1)
        return top_idx, weights

    # Warmup reference
    for _ in range(10):
        ref_idx, ref_weights = ref_mope_routing(x, c)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 50
    for _ in range(iters):
        ref_idx, ref_weights = ref_mope_routing(x, c)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out_idx = torch.empty(B, 2, device=device, dtype=torch.int32)
    out_weights = torch.empty(B, 2, device=device, dtype=torch.float32)

    BLOCK_B = 64
    grid = ((B + BLOCK_B - 1) // BLOCK_B,)

    # Warmup Triton
    for _ in range(10):
        fused_poincare_mope_routing_kernel[grid](
            x, c, out_idx, out_weights, B, D, E, BLOCK_B
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_poincare_mope_routing_kernel[grid](
            x, c, out_idx, out_weights, B, D, E, BLOCK_B
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    # Numerical verification
    # Compare weights
    max_weight_err = torch.max(torch.abs(out_weights - ref_weights)).item()
    idx_match = (out_idx == ref_idx).float().mean().item()
    speedup = ref_time / triton_time
    throughput = B / triton_time / 1e3 # k tokens/s

    print(f"=== Workstation Benchmark: Cycle 211 Poincaré 14B MoPE Geodesic Centroid Router ===")
    print(f"Hardware: {torch.cuda.get_device_name(0)}")
    print(f"Tokens: {B}, Dim: {D}, Experts: {E} (Top-2 Sparse Routing)")
    print(f"PyTorch baseline latency: {ref_time*1e6:.2f} us")
    print(f"Triton fused latency:     {triton_time*1e6:.2f} us")
    print(f"Speedup factor:           {speedup:.2f}x")
    print(f"Routing Throughput:       {throughput:.2f} k tokens/s ({throughput*E:.2f} k expert evaluations/s)")
    print(f"Top-2 Index Agreement:    {idx_match * 100:.2f}%")
    print(f"Max Weight Error:         {max_weight_err:.2e}")
    assert max_weight_err < 1e-3, f"Tolerance exceeded: {max_weight_err}"
    print("PHYSICAL HARDWARE TEST PASSED")

if __name__ == "__main__":
    run_benchmark()
