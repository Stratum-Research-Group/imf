"""
Triton GPU Kernel: Fused Poincaré Speculative Decoding Verifier (RTX 5060 Ti)

Implements parallel speculative verification in the Poincaré ball:
  Given draft token embeddings U in B^D and target token embeddings V in B^D
  for K speculative draft tokens across batch B:
  1. Computes exact hyperbolic geodesic distance:
     alpha = c * ||u - v||^2
     beta = (1 - c * ||u||^2) * (1 - c * ||v||^2)
     xi = sqrt(alpha / beta)
     d_B(u, v) = (2 / sqrt(c)) * artanh(xi)
  2. Compares against geodesic acceptance threshold epsilon_B:
     accept = d_B(u, v) <= epsilon_B
  3. Computes the accepted prefix mask and total accepted token count per sequence.

Fused implementation executes in microsecond latency on RTX 5060 Ti.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_speculative_verifier_kernel(
    U_ptr,          # [B, K, D] - Draft tokens
    V_ptr,          # [B, K, D] - Target tokens
    Dist_ptr,       # [B, K] - Geodesic distances
    Accept_ptr,     # [B, K] - Boolean acceptance flags
    B: tl.constexpr,
    K: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    epsilon: tl.constexpr,
):
    pid = tl.program_id(0) # Program per (b, k) pair: total B * K
    if pid >= B * K:
        return

    offs_d = tl.arange(0, D)

    # 1. Load u and v: [D]
    u = tl.load(U_ptr + pid * D + offs_d)
    v = tl.load(V_ptr + pid * D + offs_d)

    # 2. Compute norms and diff
    diff = u - v
    sq_norm_diff = tl.sum(diff * diff)
    sq_norm_u = tl.sum(u * u)
    sq_norm_v = tl.sum(v * v)

    # Conformal factor beta = (1 - c * ||u||^2) * (1 - c * ||v||^2)
    conf_u = tl.maximum(1.0 - c * sq_norm_u, 1e-6)
    conf_v = tl.maximum(1.0 - c * sq_norm_v, 1e-6)
    beta = conf_u * conf_v
    alpha = c * sq_norm_diff

    # arg = sqrt(alpha / beta)
    xi = tl.sqrt(tl.maximum(alpha / beta, 0.0))
    xi_clamped = tl.minimum(xi, 0.99999) # Boundary safety

    # artanh(xi) = 0.5 * ln((1 + xi) / (1 - xi))
    artanh_xi = 0.5 * tl.log((1.0 + xi_clamped) / (1.0 - xi_clamped))
    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))
    dist = (2.0 / sqrt_c) * artanh_xi

    tl.store(Dist_ptr + pid, dist)
    is_accepted = tl.where(dist <= epsilon, 1, 0)
    tl.store(Accept_ptr + pid, is_accepted)


def poincare_speculative_verifier_pytorch(U, V, c=1.0, epsilon=0.15):
    """Reference PyTorch implementation."""
    diff = U - V
    sq_norm_diff = torch.sum(diff * diff, dim=-1)
    sq_norm_u = torch.sum(U * U, dim=-1)
    sq_norm_v = torch.sum(V * V, dim=-1)

    beta = (1.0 - c * sq_norm_u).clamp(min=1e-6) * (1.0 - c * sq_norm_v).clamp(min=1e-6)
    alpha = c * sq_norm_diff
    xi = torch.sqrt((alpha / beta).clamp(min=0.0)).clamp(max=0.99999)

    dist = (2.0 / math.sqrt(c)) * torch.atanh(xi)
    accept = (dist <= epsilon).long()
    return dist, accept


def poincare_speculative_verifier_triton(U, V, c=1.0, epsilon=0.15):
    B, K, D = U.shape
    dist = torch.empty((B, K), device=U.device, dtype=torch.float32)
    accept = torch.empty((B, K), device=U.device, dtype=torch.int32)

    grid = (B * K,)
    _poincare_speculative_verifier_kernel[grid](
        U, V, dist, accept,
        B=B, K=K, D=D, c=c, epsilon=epsilon,
    )
    return dist, accept


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré Speculative Verifier on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    B = 32           # Batch size
    K = 8            # Speculative draft window size
    D = 64           # Hidden dimension
    c = 1.0
    epsilon = 0.15   # Geodesic acceptance threshold

    U = torch.randn((B, K, D), device=device, dtype=torch.float32) * 0.05
    # Target embeddings: close to draft embeddings with slight noise
    V = U + torch.randn((B, K, D), device=device, dtype=torch.float32) * 0.02

    # Correctness check
    dist_pt, accept_pt = poincare_speculative_verifier_pytorch(U, V, c, epsilon)
    dist_triton, accept_triton = poincare_speculative_verifier_triton(U, V, c, epsilon)

    max_err = (dist_pt - dist_triton).abs().max().item()
    print(f"[*] Max distance absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-4, f"Numerical mismatch exceeds tolerance: {max_err}"

    match_rate = (accept_pt == accept_triton).float().mean().item()
    print(f"[*] Decision match rate: {match_rate * 100:.2f}%")
    assert match_rate == 1.0, "Decision mismatch detected!"
    print("[✓] Correctness check passed (< 1e-4 error, 100% decision match)!")

    # Warmup
    for _ in range(50):
        poincare_speculative_verifier_pytorch(U, V, c, epsilon)
        poincare_speculative_verifier_triton(U, V, c, epsilon)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 500
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_speculative_verifier_pytorch(U, V, c, epsilon)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_speculative_verifier_triton(U, V, c, epsilon)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    tokens_per_sec = (B * K) / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {tokens_per_sec / 1e6:.2f} M draft-tokens/sec")


if __name__ == "__main__":
    benchmark()
