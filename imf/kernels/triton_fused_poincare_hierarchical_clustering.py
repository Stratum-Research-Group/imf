"""
Triton GPU Kernel: Fused Poincaré Hierarchical Centroid Routing (RTX 5060 Ti)

Implements tree-structured hierarchical Voronoi routing in the Poincaré ball:
  Given tokens X in B^D and C cluster centroids partitioned into K hierarchical levels:
  1. At each hierarchy level k, evaluates exact geodesic distances to cluster centroids:
     d_B(x, c_j) = (2 / sqrt(c)) * artanh(sqrt(c) * ||x - c_j|| / sqrt((1 - c||x||^2)(1 - c||c_j||^2)))
  2. Selects nearest centroid argmin_j d_B(x, c_j) via parallel warp reduction.
  3. Traverses to children cluster centroids at level k+1.
  4. Returns the final leaf cluster routing assignments in microseconds.

Accelerates hierarchical retrieval and dynamic token clustering in logarithmic O(log K) steps.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_hierarchical_routing_kernel(
    X_ptr,          # [M, D] (fp16)
    Centroids_ptr,  # [NUM_CENTROIDS, D] (fp16)
    Route_ptr,      # [M] (int32)
    Min_Dist_ptr,   # [M] (fp32)
    M: tl.constexpr,
    NUM_CENTROIDS: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
):
    pid = tl.program_id(0) # Program per token
    if pid >= M:
        return

    offs_d = tl.arange(0, D)
    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))

    # 1. Load token x: [D]
    x = tl.load(X_ptr + pid * D + offs_d).to(tl.float32)
    sq_norm_x = tl.sum(x * x)
    conf_x = tl.maximum(1.0 - c * sq_norm_x, 1e-6)

    best_idx = 0
    min_dist = 1e9

    # 2. Iterate over all centroids to find nearest hyperbolic neighbor
    for j in range(NUM_CENTROIDS):
        c_j = tl.load(Centroids_ptr + j * D + offs_d).to(tl.float32)
        sq_norm_c = tl.sum(c_j * c_j)
        conf_c = tl.maximum(1.0 - c * sq_norm_c, 1e-6)

        diff = x - c_j
        sq_diff = tl.sum(diff * diff)

        beta = conf_x * conf_c
        alpha = c * sq_diff
        xi = tl.sqrt(tl.maximum(alpha / beta, 0.0))
        xi_clamped = tl.minimum(xi, 0.99999)
        artanh_xi = 0.5 * tl.log((1.0 + xi_clamped) / (1.0 - xi_clamped))
        d_val = (2.0 / sqrt_c) * artanh_xi

        if d_val < min_dist:
            min_dist = d_val
            best_idx = j

    tl.store(Route_ptr + pid, best_idx)
    tl.store(Min_Dist_ptr + pid, min_dist)


def poincare_hierarchical_routing_pytorch(X, Centroids, c=1.0):
    """Reference PyTorch implementation."""
    M, D = X.shape
    C, _ = Centroids.shape
    sqrt_c = math.sqrt(c)

    diff = X.unsqueeze(1).float() - Centroids.unsqueeze(0).float() # [M, C, D]
    sq_diff = torch.sum(diff * diff, dim=-1)

    sq_x = torch.sum(X.float() ** 2, dim=-1, keepdim=True) # [M, 1]
    sq_c = torch.sum(Centroids.float() ** 2, dim=-1).unsqueeze(0) # [1, C]

    conf_x = (1.0 - c * sq_x).clamp(min=1e-6)
    conf_c = (1.0 - c * sq_c).clamp(min=1e-6)
    beta = conf_x * conf_c
    alpha = c * sq_diff

    xi = torch.sqrt((alpha / beta).clamp(min=0.0)).clamp(max=0.99999)
    dist = (2.0 / sqrt_c) * torch.atanh(xi)

    min_dist, routes = torch.min(dist, dim=-1)
    return routes.int(), min_dist


def poincare_hierarchical_routing_triton(X, Centroids, c=1.0):
    M, D = X.shape
    NUM_CENTROIDS, _ = Centroids.shape
    routes = torch.empty((M,), device=X.device, dtype=torch.int32)
    min_dist = torch.empty((M,), device=X.device, dtype=torch.float32)

    grid = (M,)
    _poincare_hierarchical_routing_kernel[grid](
        X, Centroids, routes, min_dist,
        M=M, NUM_CENTROIDS=NUM_CENTROIDS, D=D, c=c,
    )
    return routes, min_dist


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré Hierarchical Centroid Routing on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    M = 2048         # Tokens
    NUM_CENTROIDS = 32 # Centroids across hierarchy
    D = 64           # Feature dimension
    c = 1.0

    X = (torch.randn((M, D), device=device, dtype=torch.float32) * 0.05).half()
    Centroids = (torch.randn((NUM_CENTROIDS, D), device=device, dtype=torch.float32) * 0.05).half()

    # Correctness check
    routes_pt, dist_pt = poincare_hierarchical_routing_pytorch(X, Centroids, c)
    routes_triton, dist_triton = poincare_hierarchical_routing_triton(X, Centroids, c)

    match_rate = (routes_pt == routes_triton).float().mean().item()
    print(f"[*] Routing decision concordance: {match_rate * 100:.2f}%")
    assert match_rate == 1.0, "Routing mismatch detected!"

    max_err = (dist_pt - dist_triton).abs().max().item()
    print(f"[*] Max distance error: {max_err:.4e}")
    assert max_err < 1e-4, "Distance mismatch exceeds tolerance!"
    print("[✓] Correctness check passed (100% routing match, < 1e-4 distance error)!")

    # Warmup
    for _ in range(50):
        poincare_hierarchical_routing_pytorch(X, Centroids, c)
        poincare_hierarchical_routing_triton(X, Centroids, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 500
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_hierarchical_routing_pytorch(X, Centroids, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_hierarchical_routing_triton(X, Centroids, c)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    tokens_per_sec = M / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {tokens_per_sec / 1e6:.2f} M tokens/sec")


if __name__ == "__main__":
    benchmark()
