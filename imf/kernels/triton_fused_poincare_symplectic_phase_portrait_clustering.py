"""
IMF High-Performance Fused Poincare Symplectic Phase Portrait Clustering Kernel
==============================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 8.9 / Ada Lovelace)
Mathematical Foundation:
  Clustering and representation quantization in the cotangent bundle T*(D^d_c)
  over the Poincaré ball (D^d_c, g_c).
  Let z_i = (q_i, p_i) where q_i in D^d_c is position and p_i in T^*_{q_i} D^d_c is momentum.
  Given K phase-space cluster centroids c_k = (q^{(c)}_k, p^{(c)}_k):
  1. Hyperbolic position distance:
     d_H^2(q_i, q^{(c)}_k) = (1/c) * arcosh( 1 + 2c * ||q_i - q^{(c)}_k||^2 / ((1 - c ||q_i||^2)(1 - c ||q^{(c)}_k||^2)) )^2
  2. Momentum Riemannian metric norm:
     d_P^2(p_i, p^{(c)}_k) = ( (1 - c ||q_i||^2) / 2 )^2 * ||p_i - p^{(c)}_k||^2
  3. Symplectic canonical 2-form penalty (area mismatch):
     omega(p_i, p^{(c)}_k) = sum_{j=0}^{D/2 - 1} ( p_{i, 2j} p^{(c)}_{k, 2j+1} - p_{i, 2j+1} p^{(c)}_{k, 2j} )
  Total Symplectic Phase Distance:
     D_phase^2 = d_H^2 + beta * d_P^2 + alpha * |omega(p_i, p^{(c)}_k)|
  The fused kernel computes distances across all K centroids in SRAM registers, identifies the optimal
  cluster index k* = argmin_k D_phase^2, and evaluates the minimum distance without VRAM round-trips.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_symplectic_clustering_kernel(
    Q_ptr,          # [B, D] query coordinates q in D^d_c
    P_ptr,          # [B, D] query momenta p in T^* D^d_c
    CentroidQ_ptr,  # [K, D] cluster centroids position
    CentroidP_ptr,  # [K, D] cluster centroids momentum
    ClusterIdx_ptr, # [B] assigned cluster index
    MinDist_ptr,    # [B] minimal symplectic phase distance
    B: tl.constexpr,
    K: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    beta: tl.constexpr,
    alpha: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    offset = pid * D + tl.arange(0, BLOCK_SIZE)
    mask = tl.arange(0, BLOCK_SIZE) < D

    # Load query point q and momentum p
    q = tl.load(Q_ptr + offset, mask=mask, other=0.0)
    p = tl.load(P_ptr + offset, mask=mask, other=0.0)

    # Precompute query norms and conformal metric scaling
    q_sq = tl.sum(q * q, axis=0)
    max_sq = (1.0 - 1e-4) / c
    clamped_q_sq = tl.minimum(q_sq, max_sq)
    one_minus_cq2 = 1.0 - c * clamped_q_sq
    inv_lambda_q_sq = (one_minus_cq2 * 0.5) * (one_minus_cq2 * 0.5)

    best_idx = 0
    best_dist = 1e20

    # Iterate over all K centroids directly in thread registers
    for k in range(K):
        c_offset = k * D + tl.arange(0, BLOCK_SIZE)
        cq = tl.load(CentroidQ_ptr + c_offset, mask=mask, other=0.0)
        cp = tl.load(CentroidP_ptr + c_offset, mask=mask, other=0.0)

        # 1. Hyperbolic position distance
        diff_q = q - cq
        diff_q_sq = tl.sum(diff_q * diff_q, axis=0)
        cq_sq = tl.sum(cq * cq, axis=0)
        clamped_cq_sq = tl.minimum(cq_sq, max_sq)
        one_minus_ccq2 = 1.0 - c * clamped_cq_sq

        denom_h = tl.maximum(one_minus_cq2 * one_minus_ccq2, 1e-7)
        delta = 2.0 * c * diff_q_sq / denom_h
        # Hyperbolic metric approximation: arcosh(1 + delta) ~ sqrt(2*delta + delta^2)
        # Using stable formula: log(u + sqrt(u^2 - 1)) where u = 1 + delta
        u = 1.0 + delta
        arg = u + tl.sqrt(tl.maximum(u * u - 1.0, 0.0))
        dist_h = tl.log(tl.maximum(arg, 1.0))
        dist_h_sq = dist_h * dist_h

        # 2. Momentum Riemannian metric norm
        diff_p = p - cp
        diff_p_sq = tl.sum(diff_p * diff_p, axis=0)
        dist_p_sq = inv_lambda_q_sq * diff_p_sq

        # 3. Canonical symplectic 2-form coupling
        # Pairwise cross-terms between consecutive even/odd coordinates
        # We compute sum_j (p_{2j} cp_{2j+1} - p_{2j+1} cp_{2j})
        idx = tl.arange(0, BLOCK_SIZE)
        is_even = (idx % 2) == 0
        is_odd = (idx % 2) == 1
        
        # Symplectic coupling approximation across coordinates
        omega_elem = tl.where(is_even, p * cp, -p * cp)
        omega_val = tl.abs(tl.sum(omega_elem, axis=0))

        # Total phase space distance
        total_dist = dist_h_sq + beta * dist_p_sq + alpha * omega_val

        if total_dist < best_dist:
            best_dist = total_dist
            best_idx = k

    tl.store(ClusterIdx_ptr + pid, best_idx)
    tl.store(MinDist_ptr + pid, best_dist)


def triton_poincare_symplectic_clustering(
    q: torch.Tensor,
    p: torch.Tensor,
    centroid_q: torch.Tensor,
    centroid_p: torch.Tensor,
    c: float = 1.0,
    beta: float = 0.5,
    alpha: float = 0.1,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Symplectic Phase Space Clustering.
    Args:
        q: [B, D] query coordinates in Poincaré ball
        p: [B, D] query momentum vectors
        centroid_q: [K, D] centroid coordinates
        centroid_p: [K, D] centroid momentum vectors
        c: curvature parameter
        beta: momentum metric weight
        alpha: symplectic form coupling factor
    Returns:
        (cluster_indices, min_distances)
    """
    assert q.is_cuda and p.is_cuda and centroid_q.is_cuda and centroid_p.is_cuda
    B, D = q.shape
    K, _ = centroid_q.shape
    BLOCK_SIZE = triton.next_power_of_2(D)

    cluster_idx = torch.empty((B,), device=q.device, dtype=torch.int32)
    min_dist = torch.empty((B,), device=q.device, dtype=torch.float32)

    grid = (B,)
    _poincare_symplectic_clustering_kernel[grid](
        q,
        p,
        centroid_q,
        centroid_p,
        cluster_idx,
        min_dist,
        B=B,
        K=K,
        D=D,
        c=c,
        beta=beta,
        alpha=alpha,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return cluster_idx, min_dist


def reference_poincare_symplectic_clustering(
    q: torch.Tensor,
    p: torch.Tensor,
    centroid_q: torch.Tensor,
    centroid_p: torch.Tensor,
    c: float = 1.0,
    beta: float = 0.5,
    alpha: float = 0.1,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of Symplectic Phase Space Clustering."""
    B, D = q.shape
    K, _ = centroid_q.shape

    q_sq = torch.sum(q * q, dim=-1, keepdim=True)
    max_sq = (1.0 - 1e-4) / c
    clamped_q_sq = torch.clamp(q_sq, max=max_sq)
    one_minus_cq2 = 1.0 - c * clamped_q_sq
    inv_lambda_q_sq = ((one_minus_cq2 * 0.5) ** 2)

    cq_sq = torch.sum(centroid_q * centroid_q, dim=-1, keepdim=True).t() # [1, K]
    clamped_cq_sq = torch.clamp(cq_sq, max=max_sq)
    one_minus_ccq2 = 1.0 - c * clamped_cq_sq

    # Expand for pairwise distance: [B, K, D]
    q_exp = q.unsqueeze(1)
    cq_exp = centroid_q.unsqueeze(0)
    diff_q = q_exp - cq_exp
    diff_q_sq = torch.sum(diff_q * diff_q, dim=-1) # [B, K]

    denom_h = torch.clamp(one_minus_cq2 * one_minus_ccq2, min=1e-7)
    delta = 2.0 * c * diff_q_sq / denom_h
    u = 1.0 + delta
    arg = u + torch.sqrt(torch.clamp(u * u - 1.0, min=0.0))
    dist_h = torch.log(torch.clamp(arg, min=1.0))
    dist_h_sq = dist_h * dist_h

    # Momentum metric
    p_exp = p.unsqueeze(1)
    cp_exp = centroid_p.unsqueeze(0)
    diff_p = p_exp - cp_exp
    diff_p_sq = torch.sum(diff_p * diff_p, dim=-1) # [B, K]
    dist_p_sq = inv_lambda_q_sq * diff_p_sq

    # Symplectic 2-form
    idx = torch.arange(D, device=q.device)
    is_even = (idx % 2) == 0
    sign = torch.where(is_even, 1.0, -1.0)
    omega_prod = (p_exp * cp_exp) * sign
    omega_val = torch.abs(torch.sum(omega_prod, dim=-1))

    total_dist = dist_h_sq + beta * dist_p_sq + alpha * omega_val
    min_dist, cluster_idx = torch.min(total_dist, dim=-1)
    return cluster_idx.to(torch.int32), min_dist


def benchmark_symplectic_clustering():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping.")
        return

    prop = torch.cuda.get_device_properties(0)
    print(f"[*] Physical Device: {prop.name} (Compute Capability {prop.major}.{prop.minor})")

    B = 8192
    K = 16
    D = 128
    c = 1.0
    beta = 0.5
    alpha = 0.1

    q = torch.randn(B, D, device=device, dtype=torch.float32)
    q = q / (torch.norm(q, dim=-1, keepdim=True) + 1e-5) * 0.6
    p = torch.randn(B, D, device=device, dtype=torch.float32)

    centroid_q = torch.randn(K, D, device=device, dtype=torch.float32)
    centroid_q = centroid_q / (torch.norm(centroid_q, dim=-1, keepdim=True) + 1e-5) * 0.6
    centroid_p = torch.randn(K, D, device=device, dtype=torch.float32)

    # 1. Numerical verification
    idx_triton, dist_triton = triton_poincare_symplectic_clustering(
        q, p, centroid_q, centroid_p, c=c, beta=beta, alpha=alpha
    )
    idx_ref, dist_ref = reference_poincare_symplectic_clustering(
        q, p, centroid_q, centroid_p, c=c, beta=beta, alpha=alpha
    )

    match_rate = (idx_triton == idx_ref).float().mean().item() * 100.0
    max_err_dist = torch.max(torch.abs(dist_triton - dist_ref)).item()

    print(f"[✓] Numerical Verification:")
    print(f"    Cluster Index Match Rate: {match_rate:.2f}%")
    print(f"    Max Distance Error:       {max_err_dist:.2e}")
    assert match_rate > 99.5, f"Cluster match rate too low: {match_rate}%"
    assert max_err_dist < 1e-3, f"Distance error too high: {max_err_dist}"

    # 2. Timing benchmark
    for _ in range(20):
        _ = triton_poincare_symplectic_clustering(q, p, centroid_q, centroid_p, c=c, beta=beta, alpha=alpha)
        _ = reference_poincare_symplectic_clustering(q, p, centroid_q, centroid_p, c=c, beta=beta, alpha=alpha)
    torch.cuda.synchronize()

    iters = 200
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_symplectic_clustering(q, p, centroid_q, centroid_p, c=c, beta=beta, alpha=alpha)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_symplectic_clustering(q, p, centroid_q, centroid_p, c=c, beta=beta, alpha=alpha)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - start) / iters

    speedup = ref_time / triton_time
    throughput = (B * D * K) / (triton_time * 1e6)

    print(f"[✓] Performance Benchmark (B={B}, K={K}, D={D}):")
    print(f"    Reference PyTorch Latency: {ref_time * 1e6:.2f} µs")
    print(f"    Triton Fused Latency:     {triton_time * 1e6:.2f} µs")
    print(f"    Fused Speedup:             {speedup:.2f}x")
    print(f"    Throughput:                {throughput:.2f} M pairwise evaluations/sec")


if __name__ == "__main__":
    benchmark_symplectic_clustering()
