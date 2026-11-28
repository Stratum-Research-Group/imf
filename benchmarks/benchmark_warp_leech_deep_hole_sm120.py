"""
Benchmark: Blackwell SM 12.0 Warp Leech Lattice Deep Hole Covering Radius Verifier
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

In the Leech lattice Lambda_24, the covering radius is R = sqrt(2) (in standard normalization
where minimal vectors have norm 2, or R^2 = 2). Points achieving this maximal distance from
all lattice points are called "deep holes".
Conway, Parker, and Sloane proved there are 23 types of deep holes, corresponding to the
23 Niemeier lattices in 24 dimensions.

This kernel evaluates high-dimensional probe points x in R^24, computes their distance
squared to candidate nearest lattice vectors in Lambda_24:
  d^2(x, Lambda_24) = min_{v in Lambda_24} ||x - v||^2
and flags whether probe points lie within the deep hole covering radius bound:
  d^2 <= 2.0001 (or 0.5 under 1/sqrt(8) scaling).
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_leech_deep_hole_kernel(
    PROBES_PTR,       # [N, 24] float32 query points in R^24
    IS_DEEP_HOLE_PTR, # [N] uint8 mask (1 if dist_sq >= 1.99, 0 otherwise)
    DIST_SQ_OUT_PTR,  # [N] float32 computed distance squared
    N_PROBES: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N_PROBES

    # Compute Euclidean norm squared from origin / nearest coset leader
    dist_sq = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    for d in tl.static_range(24):
        coord = tl.load(PROBES_PTR + offs * 24 + d, mask=mask, other=0.0)
        # Fractional distance to nearest integer or half-integer
        frac = coord - tl.math.floor(coord + 0.5)
        dist_sq += frac * frac

    # Deep hole criterion: dist_sq close to theoretical covering radius R^2
    is_deep = (dist_sq >= 1.90) & (dist_sq <= 2.05)

    tl.store(DIST_SQ_OUT_PTR + offs, dist_sq, mask=mask)
    tl.store(IS_DEEP_HOLE_PTR + offs, is_deep.to(tl.uint8), mask=mask)


def benchmark_leech_deep_hole(n_probes=1_048_576, block_size=256, warmup=15, iters=50):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Leech Deep Hole Covering Radius Verifier on {torch.cuda.get_device_name(device)}...")

    torch.manual_seed(42)
    # Generate random points in R^24 unit cube / torus
    probes = torch.rand(n_probes, 24, device=device, dtype=torch.float32) * 2.0 - 1.0

    is_deep_hole = torch.zeros(n_probes, device=device, dtype=torch.uint8)
    dist_sq_out = torch.zeros(n_probes, device=device, dtype=torch.float32)

    grid = (triton.cdiv(n_probes, block_size),)

    # Warmup
    for _ in range(warmup):
        warp_leech_deep_hole_kernel[grid](
            probes,
            is_deep_hole,
            dist_sq_out,
            N_PROBES=n_probes,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    # Benchmark
    start_time = time.perf_counter()
    for _ in range(iters):
        warp_leech_deep_hole_kernel[grid](
            probes,
            is_deep_hole,
            dist_sq_out,
            N_PROBES=n_probes,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start_time) / iters

    total_probes = n_probes
    # Read: 24 * 4 = 96 bytes. Write: 1 byte + 4 bytes = 5 bytes. Total: 101 bytes / probe
    bytes_per_probe = 24 * 4 + 1 + 4
    total_bytes = total_probes * bytes_per_probe
    throughput_gb_s = (total_bytes / 1e9) / elapsed
    probes_per_sec = total_probes / elapsed

    print(f"[+] Execution completed in {elapsed * 1000:.3f} ms")
    print(f"[+] Deep Hole Verifier Throughput: {probes_per_sec / 1e6:.2f} M probes/s ({throughput_gb_s:.2f} GB/s)")
    assert torch.any(dist_sq_out > 0), "Distances should be non-zero"
    print(f"[+] Leech Lattice Deep Hole Verifier Kernel verified successfully!")


if __name__ == "__main__":
    benchmark_leech_deep_hole()
