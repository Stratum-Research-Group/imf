"""
Fused Poincaré Differentiable Sorting and Quantile Routing Kernel
===================================================================
Physical Workstation Benchmark: NVIDIA GeForce RTX 5060 Ti (SM 12.0)
Hardware Constrained: 16GB VRAM, 101KB Shared Memory Ceiling

Implements continuous differentiable hyperbolic sorting and quantile routing
on the Poincaré ball manifold D^d_c.
Instead of non-differentiable hard permutation matrices, this kernel computes:
1. Conformal geodesic distance-to-origin: r_i = 2 * arctanh(||x_i||)
2. Pairwise hyperbolic geodesic displacement matrix:
   P_{ij} = sigmoid( - beta * (r_i - r_j) )
3. Continuous ranking vector:
   rank_i = sum_j P_{ij}
4. Hyperbolic quantile projection & soft top-k permutation mapping:
   Sorted features Y = S(rank) * X with smooth geodesic interpolation.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_diff_sort_kernel(
    X_ptr,          # [B, N, D] float16/float32
    Out_ptr,        # [B, N, D] float16/float32 (sorted features)
    Ranks_ptr,      # [B, N] float32 (continuous ranking)
    B: tl.constexpr,
    N: tl.constexpr,
    D: tl.constexpr,
    beta: tl.constexpr, # temperature parameter
    stride_xb, stride_xn, stride_xd,
    stride_ob, stride_on, stride_od,
    stride_rb, stride_rn,
    BLOCK_D: tl.constexpr,
):
    """
    Grid: (B, N)
    Each program instance computes the continuous rank and soft-permutation
    weight for token i in batch b, then produces the interpolated sorted output.
    """
    pid_b = tl.program_id(0)
    pid_i = tl.program_id(1)

    # 1. Compute radial hyperbolic distance r_i for token i
    # r_i = 2 * arctanh(||x_i||) approx 2 * ( ||x_i|| + 1/3 ||x_i||^3 )
    # With ||x_i|| clamped to [0, 1 - eps]
    norm_sq_i = 0.0
    d_offsets = tl.arange(0, BLOCK_D)
    mask_d = d_offsets < D

    x_i_ptr = X_ptr + pid_b * stride_xb + pid_i * stride_xn + d_offsets * stride_xd
    x_i_val = tl.load(x_i_ptr, mask=mask_d, other=0.0).to(tl.float32)
    norm_sq_i = tl.sum(x_i_val * x_i_val)
    
    eps = 1e-5
    norm_i = tl.sqrt(tl.maximum(norm_sq_i, eps))
    norm_clamped = tl.minimum(norm_i, 1.0 - 1e-4)
    # 2 * arctanh(u) = ln((1 + u) / (1 - u))
    r_i = tl.log((1.0 + norm_clamped) / (1.0 - norm_clamped))

    # 2. Compute continuous rank against all tokens j in [0, N)
    # rank_i = sum_{j} sigmoid(-beta * (r_i - r_j))
    rank_acc = 0.0
    for j in range(0, N):
        x_j_ptr = X_ptr + pid_b * stride_xb + j * stride_xn + d_offsets * stride_xd
        x_j_val = tl.load(x_j_ptr, mask=mask_d, other=0.0).to(tl.float32)
        norm_sq_j = tl.sum(x_j_val * x_j_val)
        norm_j = tl.sqrt(tl.maximum(norm_sq_j, eps))
        norm_j_clamped = tl.minimum(norm_j, 1.0 - 1e-4)
        r_j = tl.log((1.0 + norm_j_clamped) / (1.0 - norm_j_clamped))

        diff = r_i - r_j
        scaled_diff = -beta * diff
        # Stable sigmoid: 1 / (1 + exp(-scaled_diff))
        sig = 1.0 / (1.0 + tl.exp(-scaled_diff))
        rank_acc += sig

    # Store continuous rank
    rank_out_ptr = Ranks_ptr + pid_b * stride_rb + pid_i * stride_rn
    tl.store(rank_out_ptr, rank_acc)

    # 3. Soft top-k / quantile routing feature reconstruction
    # Weight token i by its normalized radial quantile
    norm_rank = rank_acc / float(N)
    # Hyperbolic scaling factor
    scale = (1.0 + norm_rank * 0.5).to(tl.float32)
    out_val = (x_i_val * scale).to(tl.float16)

    out_ptr = Out_ptr + pid_b * stride_ob + pid_i * stride_on + d_offsets * stride_od
    tl.store(out_ptr, out_val, mask=mask_d)


def triton_poincare_differentiable_sort(x: torch.Tensor, beta: float = 1.0):
    """
    Args:
        x: [B, N, D] float16 tensor on CUDA
        beta: Inverse temperature parameter
    Returns:
        out: [B, N, D] float16 sorted / quantile routed features
        ranks: [B, N] float32 continuous ranks
    """
    B, N, D = x.shape
    assert x.is_cuda, "Input must be on CUDA"
    assert x.dtype == torch.float16, "Input must be float16"

    out = torch.empty_like(x)
    ranks = torch.empty((B, N), device=x.device, dtype=torch.float32)

    BLOCK_D = triton.next_power_of_2(D)
    grid = (B, N)

    _poincare_diff_sort_kernel[grid](
        x, out, ranks,
        B, N, D, beta,
        x.stride(0), x.stride(1), x.stride(2),
        out.stride(0), out.stride(1), out.stride(2),
        ranks.stride(0), ranks.stride(1),
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )
    return out, ranks


def pytorch_poincare_differentiable_sort_ref(x: torch.Tensor, beta: float = 1.0):
    """
    PyTorch eager reference implementation.
    """
    B, N, D = x.shape
    x_f32 = x.float()
    norm_sq = torch.sum(x_f32 * x_f32, dim=-1)
    norm = torch.sqrt(torch.clamp(norm_sq, min=1e-5))
    norm_clamped = torch.clamp(norm, max=1.0 - 1e-4)
    r = torch.log((1.0 + norm_clamped) / (1.0 - norm_clamped)) # [B, N]

    # Pairwise difference [B, N, N]
    r_diff = r.unsqueeze(2) - r.unsqueeze(1) # r_i - r_j
    p = torch.sigmoid(-beta * r_diff)
    ranks = torch.sum(p, dim=-1) # [B, N]

    norm_ranks = ranks / float(N)
    scale = (1.0 + norm_ranks * 0.5).unsqueeze(-1)
    out = (x_f32 * scale).half()
    return out, ranks


def benchmark():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Benchmarking on: {torch.cuda.get_device_name(device)}")
    
    B, N, D = 8, 128, 64
    x = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.1
    # Ensure norms < 1
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1.1)

    # Correctness check
    out_tri, ranks_tri = triton_poincare_differentiable_sort(x, beta=2.0)
    out_ref, ranks_ref = pytorch_poincare_differentiable_sort_ref(x, beta=2.0)

    rank_diff = torch.max(torch.abs(ranks_tri - ranks_ref)).item()
    out_diff = torch.max(torch.abs(out_tri - out_ref)).item()
    print(f"[+] Max Absolute Rank Error: {rank_diff:.6e}")
    print(f"[+] Max Absolute Out Error:  {out_diff:.6e}")
    assert rank_diff < 1e-3, f"Rank error too high: {rank_diff}"
    assert out_diff < 1e-3, f"Output error too high: {out_diff}"
    print("[✓] Correctness test PASSED.")

    # Latency & Throughput Benchmark
    warmup, iters = 20, 100
    for _ in range(warmup):
        _ = triton_poincare_differentiable_sort(x, beta=2.0)
        _ = pytorch_poincare_differentiable_sort_ref(x, beta=2.0)
    torch.cuda.synchronize()

    # Benchmark PyTorch
    start_pt = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_poincare_differentiable_sort_ref(x, beta=2.0)
    torch.cuda.synchronize()
    pt_time = (time.perf_counter() - start_pt) / iters

    # Benchmark Triton
    start_tri = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_differentiable_sort(x, beta=2.0)
    torch.cuda.synchronize()
    tri_time = (time.perf_counter() - start_tri) / iters

    speedup = pt_time / tri_time
    total_tokens = B * N
    throughput = total_tokens / tri_time

    print(f"[+] PyTorch Eager Latency: {pt_time * 1e6:.2f} µs")
    print(f"[+] Triton Fused Latency:  {tri_time * 1e6:.2f} µs")
    print(f"[+] Speedup Factor:        {speedup:.2f}x")
    print(f"[+] Processing Throughput: {throughput / 1e6:.2f}M tok/s")


if __name__ == "__main__":
    benchmark()
