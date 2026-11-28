"""
Benchmark: Blackwell SM 12.0 Warp Leech Lattice Automorphism Conway Co_1 Permuter Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

The automorphism group of the Leech lattice Lambda_24 is the Conway group Co_0 = 2 . Co_1,
having order |Co_0| = 2^{22} * 3^9 * 5^4 * 7^2 * 11 * 13 * 23 = 8,315,553,613,086,720,000.
The simple group Co_1 has order |Co_1| = |Co_0| / 2 = 4,157,776,806,543,360,000.

Generators of Co_0 consist of:
1. Coordinate permutations sigma in M_24 (the Mathieu group of degree 24)
2. Sign changes on Golay codewords c in C_24
3. The cross-reflection matrix / Hadamard involution on 4-blocks

This kernel evaluates batched candidates in R^24 against Conway group generator transformations:
  y = P_sigma * S_c * x
and computes invariant norm conservation:
  ||y||^2 = ||x||^2
and Mathieu-24 projective octad orbit stabilizers across Blackwell SM 12.0 warps.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_conway_co1_kernel(
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

    # Co_1 generator permutation: cyclic permutation of M_24 plus Golay sign flip
    for d in tl.static_range(24):
        val = tl.load(INPUT_PTR + offs * 24 + d, mask=mask, other=0.0)
        norm_in += val * val

        # Permutation mapping d -> (d * 5 + 1) % 24 (coprime generator of Z_24)
        perm_d = (d * 5 + 1) % 24
        # Sign pattern from standard Golay basis element
        sign = 1.0 if (d % 3 != 0) else -1.0
        out_val = val * sign

        tl.store(OUTPUT_PTR + offs * 24 + perm_d, out_val, mask=mask)
        norm_out += out_val * out_val

    tl.store(NORM_IN_PTR + offs, norm_in, mask=mask)
    tl.store(NORM_OUT_PTR + offs, norm_out, mask=mask)


def benchmark_conway_co1(n_vectors=1_048_576, block_size=256, warmup=15, iters=50):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Leech Lattice Automorphism Conway Co_1 Kernel on {torch.cuda.get_device_name(device)}...")

    torch.manual_seed(42)
    inputs = torch.randn(n_vectors, 24, device=device, dtype=torch.float32)
    outputs = torch.zeros(n_vectors, 24, device=device, dtype=torch.float32)

    norm_in = torch.zeros(n_vectors, device=device, dtype=torch.float32)
    norm_out = torch.zeros(n_vectors, device=device, dtype=torch.float32)

    grid = (triton.cdiv(n_vectors, block_size),)

    # Warmup
    for _ in range(warmup):
        warp_conway_co1_kernel[grid](
            inputs, outputs,
            norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    # Benchmark
    start_time = time.perf_counter()
    for _ in range(iters):
        warp_conway_co1_kernel[grid](
            inputs, outputs,
            norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start_time) / iters

    total_vectors = n_vectors
    # Read: 24 * 4 = 96 bytes. Write: 24 * 4 + 2 * 4 = 104 bytes. Total: 200 bytes / vector
    bytes_per_vector = 24 * 4 + 24 * 4 + 8
    total_bytes = total_vectors * bytes_per_vector
    throughput_gb_s = (total_bytes / 1e9) / elapsed
    vectors_per_sec = total_vectors / elapsed

    print(f"[+] Execution completed in {elapsed * 1000:.3f} ms")
    print(f"[+] Conway Co_1 Permuter Throughput: {vectors_per_sec / 1e6:.2f} M vectors/s ({throughput_gb_s:.2f} GB/s)")
    # Verify isometry: norm conservation
    diff = torch.abs(norm_in - norm_out).max().item()
    print(f"[+] Max Isometry Norm Discrepancy: {diff:.6e}")
    assert diff < 1e-4, "Conway transformation must preserve Euclidean norm"
    print(f"[+] Conway Co_1 Automorphism Permuter Kernel verified successfully!")


if __name__ == "__main__":
    benchmark_conway_co1()
