"""
IMF Triton Fused Poincaré Top-K Nearest-Neighbor (k-NN) Polytope Routing Kernel
================================================================================
Computes online top-k centroid retrieval in the Poincaré hyperbolic ball:
    d_D(u, c_i) = arcosh(1 + 2 * ||u - c_i||^2 / ((1 - ||u||^2) * (1 - ||c_i||^2)))

Performs online register-level sorting/selection of top-k expert polytope centroids
without writing full M x N distance matrices to DRAM.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_poincare_knn_kernel(
    U_ptr,          # [M, D] Query vectors in Poincare ball
    C_ptr,          # [K_centroids, D] Polytope centroids in Poincare ball
    Topk_Idx_ptr,   # [M, TOP_K] Output indices of top-k nearest centroids
    Topk_Dist_ptr,  # [M, TOP_K] Output distances of top-k nearest centroids
    M, K_centroids, D,
    stride_um, stride_ud,
    stride_ck, stride_cd,
    stride_om, stride_ok,
    stride_dm, stride_dk,
    eps: tl.constexpr,
    BLOCK_M: tl.constexpr,
    BLOCK_D: tl.constexpr,
    TOP_K: tl.constexpr,
):
    pid_m = tl.program_id(0)
    offs_m = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
    mask_m = offs_m < M

    # Pre-calculate norm_u_sq for each query in the block
    norm_u_sq = tl.zeros([BLOCK_M], dtype=tl.float32)
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + tl.arange(0, BLOCK_D)
        mask_d = curr_d < D
        u_ptrs = U_ptr + (offs_m[:, None] * stride_um + curr_d[None, :] * stride_ud)
        u_val = tl.load(u_ptrs, mask=mask_m[:, None] & mask_d[None, :], other=0.0).to(tl.float32)
        norm_u_sq += tl.sum(u_val * u_val, axis=1)

    alpha_u = tl.maximum(1.0 - norm_u_sq, eps)

    # Maintain running top-k in registers for each query in BLOCK_M
    # For small TOP_K (e.g. 2 or 4), we track explicit register arrays
    best_dist_0 = tl.full([BLOCK_M], 1e9, dtype=tl.float32)
    best_idx_0 = tl.full([BLOCK_M], -1, dtype=tl.int32)
    best_dist_1 = tl.full([BLOCK_M], 1e9, dtype=tl.float32)
    best_idx_1 = tl.full([BLOCK_M], -1, dtype=tl.int32)

    # Iterate sequentially over all centroids K_centroids
    for c_i in range(K_centroids):
        # Load centroid vector c_i [D]
        norm_c_sq = 0.0
        diff_sq = tl.zeros([BLOCK_M], dtype=tl.float32)

        for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
            curr_d = d_idx * BLOCK_D + tl.arange(0, BLOCK_D)
            mask_d = curr_d < D

            c_ptrs = C_ptr + (c_i * stride_ck + curr_d * stride_cd)
            c_val = tl.load(c_ptrs, mask=mask_d, other=0.0).to(tl.float32)
            norm_c_sq += tl.sum(c_val * c_val)

            # Accumulate (u - c)^2
            u_ptrs = U_ptr + (offs_m[:, None] * stride_um + curr_d[None, :] * stride_ud)
            u_val = tl.load(u_ptrs, mask=mask_m[:, None] & mask_d[None, :], other=0.0).to(tl.float32)
            delta = u_val - c_val[None, :]
            diff_sq += tl.sum(delta * delta, axis=1)

        alpha_c = tl.maximum(1.0 - norm_c_sq, eps)
        denom = tl.maximum(alpha_u * alpha_c, eps * eps)

        arg_z = tl.maximum(1.0 + 2.0 * diff_sq / denom, 1.0)
        sqrt_term = tl.sqrt(arg_z * arg_z - 1.0)
        dist = tl.log(arg_z + sqrt_term)

        # Update Top-2 running selection
        is_smaller_0 = dist < best_dist_0
        is_smaller_1 = (dist < best_dist_1) & (~is_smaller_0)

        # Shift down
        best_dist_1 = tl.where(is_smaller_0, best_dist_0, tl.where(is_smaller_1, dist, best_dist_1))
        best_idx_1 = tl.where(is_smaller_0, best_idx_0, tl.where(is_smaller_1, c_i, best_idx_1))

        best_dist_0 = tl.where(is_smaller_0, dist, best_dist_0)
        best_idx_0 = tl.where(is_smaller_0, c_i, best_idx_0)

    # Store top-2 results
    out_idx_ptr_0 = Topk_Idx_ptr + (offs_m * stride_om + 0 * stride_ok)
    out_idx_ptr_1 = Topk_Idx_ptr + (offs_m * stride_om + 1 * stride_ok)
    tl.store(out_idx_ptr_0, best_idx_0, mask=mask_m)
    tl.store(out_idx_ptr_1, best_idx_1, mask=mask_m)

    out_dst_ptr_0 = Topk_Dist_ptr + (offs_m * stride_dm + 0 * stride_dk)
    out_dst_ptr_1 = Topk_Dist_ptr + (offs_m * stride_dm + 1 * stride_dk)
    tl.store(out_dst_ptr_0, best_dist_0.to(tl.float16), mask=mask_m)
    tl.store(out_dst_ptr_1, best_dist_1.to(tl.float16), mask=mask_m)


def triton_poincare_knn(U: torch.Tensor, C: torch.Tensor, top_k: int = 2, eps: float = 1e-5):
    """
    U: [M, D] Query vectors
    C: [K_centroids, D] Polytope centroids
    Returns: (topk_indices [M, top_k], topk_distances [M, top_k])
    """
    assert U.is_cuda and C.is_cuda
    assert top_k == 2, "Current kernel optimized for Top-2 MoE routing"
    M, D = U.shape
    K_centroids = C.shape[0]

    Topk_Idx = torch.empty((M, top_k), device=U.device, dtype=torch.int32)
    Topk_Dist = torch.empty((M, top_k), device=U.device, dtype=torch.float16)

    BLOCK_M = 64
    BLOCK_D = min(128, triton.next_power_of_2(D))
    grid = (triton.cdiv(M, BLOCK_M),)

    _fused_poincare_knn_kernel[grid](
        U, C, Topk_Idx, Topk_Dist,
        M, K_centroids, D,
        U.stride(0), U.stride(1),
        C.stride(0), C.stride(1),
        Topk_Idx.stride(0), Topk_Idx.stride(1),
        Topk_Dist.stride(0), Topk_Dist.stride(1),
        eps=eps,
        BLOCK_M=BLOCK_M,
        BLOCK_D=BLOCK_D,
        TOP_K=top_k,
    )
    return Topk_Idx, Topk_Dist


def benchmark_poincare_knn():
    print("=" * 80)
    print("  IMF TRITON FUSED POINCARÉ TOP-K k-NN ROUTING BENCHMARK")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    M = 4096       # Batch tokens
    K_cent = 64    # Expert centroids (e.g. 64-way MoPE)
    D = 128        # Embedding dimension
    print(f"[*] Workload: Query Tokens M={M}, Expert Centroids K={K_cent}, Dim D={D}")

    torch.manual_seed(42)
    U = torch.randn((M, D), device=device, dtype=torch.float16)
    U = U / (U.norm(dim=-1, keepdim=True) + 1e-4) * 0.85

    C = torch.randn((K_cent, D), device=device, dtype=torch.float16)
    C = C / (C.norm(dim=-1, keepdim=True) + 1e-4) * 0.85

    # Warmup
    for _ in range(10):
        _ = triton_poincare_knn(U, C, top_k=2)
    torch.cuda.synchronize()

    # PyTorch Reference Verification
    def torch_knn_ref(u, c, eps=1e-5):
        u_f32 = u.float()
        c_f32 = c.float()
        u_sq = torch.sum(u_f32 * u_f32, dim=-1, keepdim=True)
        c_sq = torch.sum(c_f32 * c_f32, dim=-1, keepdim=True).t()
        diff_sq = torch.cdist(u_f32, c_f32, p=2) ** 2
        alpha_u = torch.clamp(1.0 - u_sq, min=eps)
        alpha_c = torch.clamp(1.0 - c_sq, min=eps)
        arg_z = torch.clamp(1.0 + 2.0 * diff_sq / (alpha_u * alpha_c), min=1.0)
        dists = torch.acosh(arg_z)
        topk_dists, topk_indices = torch.topk(dists, k=2, dim=-1, largest=False)
        return topk_indices.int(), topk_dists.half()

    ref_idx, ref_dst = torch_knn_ref(U, C)
    tri_idx, tri_dst = triton_poincare_knn(U, C, top_k=2)

    match_rate = (ref_idx == tri_idx).float().mean().item() * 100.0
    print(f"[*] Top-K Accuracy Match: {match_rate:.2f}% (Top-1 exact match)")
    assert match_rate > 95.0, f"Match rate too low: {match_rate}%"

    # Latency Benchmark
    iters = 100
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_knn(U, C, top_k=2)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start) / iters

    throughput = M / elapsed / 1e6
    print(f"[✓] Execution Latency: {elapsed * 1000:.3f} ms ({elapsed * 1e6:.1f} µs)")
    print(f"[✓] Routing Throughput: {throughput:.2f} Million tokens/sec")
    print("=" * 80)


if __name__ == "__main__":
    benchmark_poincare_knn()
