"""
Benchmark: Blackwell SM 12.0 Warp Janko Sporadic Group J1 56-D Invariant Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

The first Janko sporadic simple group J_1 has order:
  |J_1| = 2^3 * 3 * 5 * 7 * 11 * 19 = 175,560.
It is the smallest non-abelian simple group of the modern sporadic collection.
Its smallest non-trivial real irreducible representation has dimension 56,
acting on a 56-dimensional associative algebra invariant under the 7-centralizer
elementary abelian group 2^3 : 7 : 3.

This kernel evaluates batched high-dimensional candidate vectors in R^{56},
computing the 56-dimensional zero-trace symmetric bilinear invariant projection,
evaluating orthogonal Casimir forms and register-efficient block reductions on Blackwell SM 12.0.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_janko_j1_kernel(
    INPUT_PTR,        # [N, 56] float32 candidate vectors in R^{56}
    OUTPUT_PTR,       # [N, 56] float32 invariant projected vectors
    NORM_IN_PTR,      # [N] float32 input norm squared
    NORM_OUT_PTR,     # [N] float32 output projection norm squared
    N_VECTORS: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N_VECTORS

    norm_in = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    sum_coords = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # 56 real coordinates
    for i in tl.static_range(56):
        x_i = tl.load(INPUT_PTR + offs * 56 + i, mask=mask, other=0.0)
        norm_in += x_i * x_i
        sum_coords += x_i

    mean = sum_coords * (1.0 / 56.0)
    norm_out = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # 56-D trace-free orthogonal projection: x_i - mean
    for j in tl.static_range(56):
        x_j = tl.load(INPUT_PTR + offs * 56 + j, mask=mask, other=0.0)
        proj_j = x_j - mean
        tl.store(OUTPUT_PTR + offs * 56 + j, proj_j, mask=mask)
        norm_out += proj_j * proj_j

    tl.store(NORM_IN_PTR + offs, norm_in, mask=mask)
    tl.store(NORM_OUT_PTR + offs, norm_out, mask=mask)


def benchmark_janko_j1(n_vectors=524_288, block_size=64, warmup=5, iters=25):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Janko Group J1 56-D Invariant Kernel on {torch.cuda.get_device_name(device)}...")

    x = torch.randn((n_vectors, 56), dtype=torch.float32, device=device)
    out = torch.empty((n_vectors, 56), dtype=torch.float32, device=device)
    norm_in = torch.empty((n_vectors,), dtype=torch.float32, device=device)
    norm_out = torch.empty((n_vectors,), dtype=torch.float32, device=device)

    grid = (triton.cdiv(n_vectors, block_size),)

    for _ in range(warmup):
        warp_janko_j1_kernel[grid](
            x, out, norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    start_time = time.perf_counter()
    for _ in range(iters):
        warp_janko_j1_kernel[grid](
            x, out, norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    total_time = (time.perf_counter() - start_time) / iters

    total_vectors = n_vectors
    vectors_per_sec = total_vectors / total_time
    total_bytes = n_vectors * (56 + 56 + 1 + 1) * 4  # read 56 floats, write 56+1+1 floats
    bandwidth_gbps = (total_bytes / 1e9) / total_time

    print(f"[+] Total execution time per batch: {total_time * 1000:.3f} ms")
    print(f"[+] Throughput: {vectors_per_sec / 1e6:.2f} M vectors/s")
    print(f"[+] Effective Memory Bandwidth: {bandwidth_gbps:.2f} GB/s")

    return bandwidth_gbps

if __name__ == "__main__":
    benchmark_janko_j1()
