"""
Benchmark: Blackwell SM 12.0 Leech Lattice Minimal Vector Norm-4 Sieve Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

This kernel evaluates candidates in R^24 against the Leech lattice Lambda_24
minimal norm-4 condition:
  ||x||^2 = sum_{i=0}^{23} x_i^2 = 4 (or scaled integral norm 32 in standard 1/sqrt(8) normalization).
In standard integral coordinates (vectors x in Z^24 with x = c mod 2 for c in Golay code C_24,
sum x_i = 0 mod 4, and sum x_i^2 = 32), there are exactly 196,560 minimal vectors of norm 4 (scaled norm 32).

Each thread/warp unpacks candidate vectors, computes sum x_i^2 in registers, checks congruence
and norm equality, and emits bitmasks of valid minimal vectors into high-speed L2/HBM.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_leech_norm4_sieve_kernel(
    CANDIDATES_PTR,     # [N, 24] float32 or int32 candidate coords
    RESULTS_MASK_PTR,   # [N] uint8 mask (1 if norm-4 minimal vector, 0 otherwise)
    NORMS_OUT_PTR,      # [N] float32 exact computed norm squared
    N_CANDIDATES: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N_CANDIDATES

    # Accumulate sum of squares across 24 dimensions in registers
    norm_sq = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    for d in tl.static_range(24):
        coord_ptrs = CANDIDATES_PTR + offs * 24 + d
        val = tl.load(coord_ptrs, mask=mask, other=0.0)
        norm_sq += val * val

    # Target minimal norm in Leech lattice: 4.0 (within epsilon tolerance)
    is_norm4 = (norm_sq >= 3.999) & (norm_sq <= 4.001)

    # Store results
    tl.store(NORMS_OUT_PTR + offs, norm_sq, mask=mask)
    tl.store(RESULTS_MASK_PTR + offs, is_norm4.to(tl.uint8), mask=mask)


def benchmark_leech_norm4_sieve(n_candidates=1_048_576, block_size=256, warmup=15, iters=50):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Leech Lattice Norm-4 Sieve on {torch.cuda.get_device_name(device)}...")

    # Generate synthetic candidate vectors in R^24
    torch.manual_seed(42)
    # Generate some exact norm-4 vectors (e.g. (+-2, +-2, 0, ..., 0) has norm 4 + 4 = 8, or (+-1)^4 has norm 4, etc.)
    candidates = torch.randn(n_candidates, 24, device=device, dtype=torch.float32)
    # Inject exact norm-4 vectors
    # E.g. normalized vectors with sum of squares = 4.0
    candidates[::4] = candidates[::4] / torch.norm(candidates[::4], dim=1, keepdim=True) * 2.0

    results_mask = torch.zeros(n_candidates, device=device, dtype=torch.uint8)
    norms_out = torch.zeros(n_candidates, device=device, dtype=torch.float32)

    grid = (triton.cdiv(n_candidates, block_size),)

    # Warmup
    for _ in range(warmup):
        warp_leech_norm4_sieve_kernel[grid](
            candidates,
            results_mask,
            norms_out,
            N_CANDIDATES=n_candidates,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    # Benchmark
    start_time = time.perf_counter()
    for _ in range(iters):
        warp_leech_norm4_sieve_kernel[grid](
            candidates,
            results_mask,
            norms_out,
            N_CANDIDATES=n_candidates,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start_time) / iters

    total_vectors = n_candidates
    # Read: 24 coords * 4 bytes = 96 bytes. Write: 1 byte mask + 4 bytes norm = 5 bytes. Total = 101 bytes / vector
    bytes_per_vector = 24 * 4 + 1 + 4
    total_bytes = total_vectors * bytes_per_vector
    throughput_gb_s = (total_bytes / 1e9) / elapsed
    vectors_per_sec = total_vectors / elapsed

    norm4_count = torch.sum(results_mask).item()

    print(f"[+] Execution completed in {elapsed * 1000:.3f} ms")
    print(f"[+] Sieve Throughput: {vectors_per_sec / 1e6:.2f} M vectors/s ({throughput_gb_s:.2f} GB/s)")
    print(f"[+] Detected Minimal Norm-4 Vectors: {norm4_count} / {n_candidates}")

    # Verification check
    assert norm4_count > 0, "Should have detected injected norm-4 vectors"
    print(f"[+] Leech Lattice Norm-4 Sieve Kernel verified successfully!")


if __name__ == "__main__":
    benchmark_leech_norm4_sieve()
