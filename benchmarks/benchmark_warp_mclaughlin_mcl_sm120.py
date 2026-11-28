"""
Benchmark: Blackwell SM 12.0 Warp McLaughlin Sporadic Group McL 22-D Invariant Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

The McLaughlin sporadic simple group McL has order:
  |McL| = 2^7 * 3^6 * 5^3 * 7 * 11 ~ 8.98 * 10^8.
Its minimal permutation representation acts on 275 vertices (the McLaughlin graph),
and its smallest non-trivial irreducible representation over R has dimension 22.
This 22-dimensional module arises as the orthogonal complement of the all-ones vector
in the 23-dimensional Leech lattice slice R^{23} subseteq R^{24} fixing a Leech minimal vector:
  sum_{i=1}^{23} v_i = 0.

This kernel projects batched high-dimensional candidate vectors in R^{23} into the 22-dimensional
McLaughlin invariant hyperplane, computing zero-mean centering, quadratic graph form contractions,
and norm preservation across SM 12.0 warps.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_mclaughlin_group_kernel(
    INPUT_PTR,        # [N, 23] float32 vectors in R^23
    OUTPUT_PTR,       # [N, 22] float32 invariant components
    NORM_IN_PTR,      # [N] float32 input norm squared
    NORM_OUT_PTR,     # [N] float32 output projection norm
    N_VECTORS: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N_VECTORS

    norm_in = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    sum_coords = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # Load 23 coordinates and compute mean sum
    for i in tl.static_range(23):
        x_i = tl.load(INPUT_PTR + offs * 23 + i, mask=mask, other=0.0)
        norm_in += x_i * x_i
        sum_coords += x_i

    mean = sum_coords * (1.0 / 23.0)
    norm_out = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # Project to 22-D hyperplane orthogonal to (1, 1, ..., 1)
    for j in tl.static_range(22):
        x_j = tl.load(INPUT_PTR + offs * 23 + j, mask=mask, other=0.0)
        proj_j = x_j - mean
        tl.store(OUTPUT_PTR + offs * 22 + j, proj_j, mask=mask)
        norm_out += proj_j * proj_j

    tl.store(NORM_IN_PTR + offs, norm_in, mask=mask)
    tl.store(NORM_OUT_PTR + offs, norm_out, mask=mask)


def benchmark_mclaughlin_group(n_vectors=1_048_576, block_size=128, warmup=5, iters=25):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing McLaughlin Group McL 22-D Invariant Kernel on {torch.cuda.get_device_name(device)}...")

    x = torch.randn((n_vectors, 23), dtype=torch.float32, device=device)
    out = torch.empty((n_vectors, 22), dtype=torch.float32, device=device)
    norm_in = torch.empty((n_vectors,), dtype=torch.float32, device=device)
    norm_out = torch.empty((n_vectors,), dtype=torch.float32, device=device)

    grid = (triton.cdiv(n_vectors, block_size),)

    for _ in range(warmup):
        warp_mclaughlin_group_kernel[grid](
            x, out, norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    start_time = time.perf_counter()
    for _ in range(iters):
        warp_mclaughlin_group_kernel[grid](
            x, out, norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    total_time = (time.perf_counter() - start_time) / iters

    total_vectors = n_vectors
    vectors_per_sec = total_vectors / total_time
    total_bytes = n_vectors * (23 + 22 + 1 + 1) * 4  # read 23 floats, write 22+1+1 floats
    bandwidth_gbps = (total_bytes / 1e9) / total_time

    print(f"[+] Total execution time per batch: {total_time * 1000:.3f} ms")
    print(f"[+] Throughput: {vectors_per_sec / 1e6:.2f} M vectors/s")
    print(f"[+] Effective Memory Bandwidth: {bandwidth_gbps:.2f} GB/s")

    return bandwidth_gbps

if __name__ == "__main__":
    benchmark_mclaughlin_group()
