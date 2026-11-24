"""
IMF Triton Fused Poincaré-Ball Hyperbolic Geodesic Distance Matrix Kernel
========================================================================
Computes pair-wise hyperbolic distance matrix in the Poincaré ball model:
    d_D(u, v) = arcosh(1 + 2 * ||u - v||^2 / ((1 - ||u||^2) * (1 - ||v||^2)))

Numerical Invariants:
1. Conformal factor stabilization: clamp (1 - ||x||^2) >= eps to prevent
   infinite curvature blowup at boundary horizon.
2. Direct arcosh computation: arcosh(z) = ln(z + sqrt(z^2 - 1)), with z >= 1.
3. Zero DRAM spills: Tile computation across SRAM blocks to compute M x N
   distance matrix entirely in registers.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_poincare_distance_kernel(
    U_ptr,          # [M, D] queries in Poincare ball
    V_ptr,          # [N, D] keys/centroids in Poincare ball
    Dist_ptr,       # [M, N] output geodesic distance matrix
    M, N, D,
    stride_um, stride_ud,
    stride_vn, stride_vd,
    stride_dm, stride_dn,
    eps: tl.constexpr,
    BLOCK_M: tl.constexpr,
    BLOCK_N: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    pid_m = tl.program_id(0)
    pid_n = tl.program_id(1)

    offs_m = pid_m * BLOCK_M + tl.arange(0, BLOCK_M)
    offs_n = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
    offs_d = tl.arange(0, BLOCK_D)

    mask_m = offs_m < M
    mask_n = offs_n < N

    # Accumulators for norms: ||u||^2, ||v||^2, and distance components
    # We do a reduction over D dimension
    norm_u_sq = tl.zeros([BLOCK_M], dtype=tl.float32)
    norm_v_sq = tl.zeros([BLOCK_N], dtype=tl.float32)
    diff_sq = tl.zeros([BLOCK_M, BLOCK_N], dtype=tl.float32)

    # Compute ||u||^2 and ||v||^2 and ||u - v||^2 over D chunks
    for d_idx in range(0, tl.cdiv(D, BLOCK_D)):
        curr_d = d_idx * BLOCK_D + offs_d
        mask_d = curr_d < D

        # Load U [BLOCK_M, BLOCK_D]
        u_ptrs = U_ptr + (offs_m[:, None] * stride_um + curr_d[None, :] * stride_ud)
        u_val = tl.load(u_ptrs, mask=mask_m[:, None] & mask_d[None, :], other=0.0).to(tl.float32)

        # Load V [BLOCK_N, BLOCK_D]
        v_ptrs = V_ptr + (offs_n[:, None] * stride_vn + curr_d[None, :] * stride_vd)
        v_val = tl.load(v_ptrs, mask=mask_n[:, None] & mask_d[None, :], other=0.0).to(tl.float32)

        # Accumulate norm_u_sq: sum over D
        norm_u_sq += tl.sum(u_val * u_val, axis=1)
        # Accumulate norm_v_sq: sum over D
        norm_v_sq += tl.sum(v_val * v_val, axis=1)

        # Compute pair-wise diff: (u - v)^2 = u^2 - 2uv + v^2
        # Directly broadcast diff
        u_bcast = u_val[:, None, :]  # [BLOCK_M, 1, BLOCK_D]
        v_bcast = v_val[None, :, :]  # [1, BLOCK_N, BLOCK_D]
        delta = u_bcast - v_bcast
        diff_sq += tl.sum(delta * delta, axis=2)

    # Apply conformal factors: alpha_u = 1 - ||u||^2, alpha_v = 1 - ||v||^2
    alpha_u = 1.0 - norm_u_sq
    alpha_u = tl.maximum(alpha_u, eps)

    alpha_v = 1.0 - norm_v_sq
    alpha_v = tl.maximum(alpha_v, eps)

    denom = alpha_u[:, None] * alpha_v[None, :]
    denom = tl.maximum(denom, eps * eps)

    # Argument to arcosh: z = 1 + 2 * ||u - v||^2 / denom
    arg_z = 1.0 + 2.0 * diff_sq / denom
    arg_z = tl.maximum(arg_z, 1.0)

    # arcosh(z) = ln(z + sqrt(z^2 - 1))
    sqrt_term = tl.sqrt(arg_z * arg_z - 1.0)
    dist = tl.log(arg_z + sqrt_term)

    # Store output [BLOCK_M, BLOCK_N]
    out_ptrs = Dist_ptr + (offs_m[:, None] * stride_dm + offs_n[None, :] * stride_dn)
    tl.store(out_ptrs, dist.to(tl.float16), mask=mask_m[:, None] & mask_n[None, :])


def triton_poincare_distance(U: torch.Tensor, V: torch.Tensor, eps: float = 1e-5) -> torch.Tensor:
    """
    U: [M, D] query vectors inside Poincare ball (||u|| < 1)
    V: [N, D] reference vectors inside Poincare ball (||v|| < 1)
    Returns: [M, N] geodesic distance matrix
    """
    assert U.is_cuda and V.is_cuda
    assert U.shape[1] == V.shape[1]
    M, D = U.shape
    N = V.shape[0]

    Dist = torch.empty((M, N), device=U.device, dtype=torch.float16)

    BLOCK_M = 32
    BLOCK_N = 32
    BLOCK_D = min(64, triton.next_power_of_2(D))

    grid = (triton.cdiv(M, BLOCK_M), triton.cdiv(N, BLOCK_N))

    _fused_poincare_distance_kernel[grid](
        U, V, Dist,
        M, N, D,
        U.stride(0), U.stride(1),
        V.stride(0), V.stride(1),
        Dist.stride(0), Dist.stride(1),
        eps=eps,
        BLOCK_M=BLOCK_M,
        BLOCK_N=BLOCK_N,
        BLOCK_D=BLOCK_D,
    )
    return Dist


def benchmark_poincare_distance():
    print("=" * 80)
    print("  IMF TRITON FUSED POINCARÉ GEODESIC DISTANCE MATRIX BENCHMARK")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    # Benchmark config: M = 2048 query tokens, N = 1024 polytope centroids, D = 128
    M, N, D = 2048, 1024, 128
    print(f"[*] Workload: Queries M={M}, Centroids N={N}, Dim D={D}")

    # Generate random points inside the Poincare ball: ||x|| < 0.95
    torch.manual_seed(42)
    U = torch.randn((M, D), device=device, dtype=torch.float16)
    U = U / (U.norm(dim=-1, keepdim=True) + 1e-4) * 0.85

    V = torch.randn((N, D), device=device, dtype=torch.float16)
    V = V / (V.norm(dim=-1, keepdim=True) + 1e-4) * 0.85

    # Warmup
    for _ in range(10):
        _ = triton_poincare_distance(U, V)
    torch.cuda.synchronize()

    # PyTorch reference implementation (FP32 precision)
    def torch_poincare_ref(u, v, eps=1e-5):
        u_f32 = u.float()
        v_f32 = v.float()
        u_sq = torch.sum(u_f32 * u_f32, dim=-1, keepdim=True)  # [M, 1]
        v_sq = torch.sum(v_f32 * v_f32, dim=-1, keepdim=True).t()  # [1, N]
        diff_sq = torch.cdist(u_f32, v_f32, p=2) ** 2  # [M, N]
        alpha_u = torch.clamp(1.0 - u_sq, min=eps)
        alpha_v = torch.clamp(1.0 - v_sq, min=eps)
        arg_z = 1.0 + 2.0 * diff_sq / (alpha_u * alpha_v)
        arg_z = torch.clamp(arg_z, min=1.0)
        return torch.acosh(arg_z).half()

    ref_dist = torch_poincare_ref(U, V)
    tri_dist = triton_poincare_distance(U, V)

    max_err = torch.max(torch.abs(ref_dist - tri_dist)).item()
    mean_err = torch.mean(torch.abs(ref_dist - tri_dist)).item()
    print(f"[*] Numerical Fidelity: Max Diff = {max_err:.4e}, Mean Diff = {mean_err:.4e}")
    assert max_err < 0.05, f"Numerical error too high: {max_err}"

    # Timing
    iters = 100
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_distance(U, V)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start) / iters

    total_pairs = M * N
    throughput_pairs = total_pairs / elapsed / 1e6
    print(f"[✓] Execution Time: {elapsed * 1000:.3f} ms per distance matrix")
    print(f"[✓] Throughput: {throughput_pairs:.2f} Million pair-distances/sec")
    print("=" * 80)


if __name__ == "__main__":
    benchmark_poincare_distance()
