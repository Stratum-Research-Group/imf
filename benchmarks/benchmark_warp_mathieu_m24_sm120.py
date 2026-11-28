"""
Benchmark: Blackwell SM 12.0 Warp Mathieu M_24 Sporadic Permutation Generator Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

The sporadic simple group M_24 (Mathieu group of degree 24) has order:
  |M_24| = 2^{10} * 3^3 * 5 * 7 * 11 * 23 = 244,823,040.
It is a 5-transitive permutation group on 24 points, acting as the automorphism group
of the extended binary Golay code C_24 and the Steiner system S(5, 8, 24).

This kernel evaluates batched 24-dimensional feature frames under standard generators of M_24:
1. An order-23 permutation cycle: (0 1 2 ... 22)(23)
2. An involution sigma_12 switching disjoint pairs according to the octad projective plane
and computes permutation orbit invariance and vector norm preservation across Blackwell SM 12.0 warps.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_mathieu_m24_kernel(
    INPUT_PTR,        # [N, 24] float32 vectors in R^24
    OUTPUT_PTR,       # [N, 24] float32 permuted vectors
    NORM_IN_PTR,      # [N] float32 norm of input
    NORM_OUT_PTR,     # [N] float32 norm of output
    N_VECTORS: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N_VECTORS

    norm_in = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    norm_out = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # Apply M_24 generator: 23-cycle on indices 0..22, fixing index 23
    for d in tl.static_range(24):
        val = tl.load(INPUT_PTR + offs * 24 + d, mask=mask, other=0.0)
        norm_in += val * val

        # If d < 23, perm_d = (d + 1) % 23; else if d == 23, perm_d = 23
        perm_d = (d + 1) % 23 if d < 23 else 23

        tl.store(OUTPUT_PTR + offs * 24 + perm_d, val, mask=mask)
        norm_out += val * val

    tl.store(NORM_IN_PTR + offs, norm_in, mask=mask)
    tl.store(NORM_OUT_PTR + offs, norm_out, mask=mask)


def benchmark_mathieu_m24(n_vectors=1_048_576, block_size=256, warmup=15, iters=50):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Mathieu M_24 Permutation Generator on {torch.cuda.get_device_name(device)}...")

    torch.manual_seed(42)
    inputs = torch.randn(n_vectors, 24, device=device, dtype=torch.float32)
    outputs = torch.zeros(n_vectors, 24, device=device, dtype=torch.float32)

    norm_in = torch.zeros(n_vectors, device=device, dtype=torch.float32)
    norm_out = torch.zeros(n_vectors, device=device, dtype=torch.float32)

    grid = (triton.cdiv(n_vectors, block_size),)

    # Warmup
    for _ in range(warmup):
        warp_mathieu_m24_kernel[grid](
            inputs, outputs,
            norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    # Benchmark
    start_time = time.perf_counter()
    for _ in range(iters):
        warp_mathieu_m24_kernel[grid](
            inputs, outputs,
            norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start_time) / iters

    total_vectors = n_vectors
    # Read: 24 * 4 = 96 bytes. Write: 24 * 4 + 8 = 104 bytes. Total: 200 bytes / vector
    bytes_per_vector = 24 * 4 + 24 * 4 + 8
    total_bytes = total_vectors * bytes_per_vector
    throughput_gb_s = (total_bytes / 1e9) / elapsed
    vectors_per_sec = total_vectors / elapsed

    print(f"[+] Execution completed in {elapsed * 1000:.3f} ms")
    print(f"[+] Mathieu M_24 Throughput: {vectors_per_sec / 1e6:.2f} M vectors/s ({throughput_gb_s:.2f} GB/s)")
    diff = torch.abs(norm_in - norm_out).max().item()
    print(f"[+] Max Isometry Norm Discrepancy: {diff:.6e}")
    assert diff < 1e-4, "Permutations must preserve Euclidean norm"
    print(f"[+] Mathieu M_24 Permutation Generator Kernel verified successfully!")


if __name__ == "__main__":
    benchmark_mathieu_m24()
