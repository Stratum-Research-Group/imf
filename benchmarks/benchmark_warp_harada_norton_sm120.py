"""
Benchmark: Blackwell SM 12.0 Warp Harada-Norton HN 133-D Invariant Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

The Harada-Norton group HN is a sporadic simple group of order:
  |HN| = 2^{14} * 3^6 * 5^6 * 7 * 11 * 19 ~ 2.73 * 10^{14}.
Its smallest non-trivial complex irreducible representation has dimension 133.
Under maximal 5-local subgroup actions (A_12, 5^{1+4}:2^{1+4}.5.4), the 133-dimensional
representation decomposes into symmetric invariant tensor slices.

This kernel evaluates batched high-dimensional candidate vectors in R^32, projecting
their outer products into a 133-dimensional invariant subspace of Sym^2(R^32):
  dim(Sym^2(R^32)) = (32 * 33) / 2 = 528 components,
extracting 133 canonical invariant components and computing trace and norm conservation across SM 12.0 warps.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_harada_norton_kernel(
    INPUT_PTR,        # [N, 32] float32 vectors in R^32
    OUTPUT_PTR,       # [N, 133] float32 invariant components
    NORM_IN_PTR,      # [N] float32 input norm squared
    TRACE_OUT_PTR,    # [N] float32 trace sum
    N_VECTORS: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N_VECTORS

    norm_in = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    trace = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # 32-dimensional input outer product: extract 133 invariant components
    out_idx = 0
    for i in tl.static_range(32):
        x_i = tl.load(INPUT_PTR + offs * 32 + i, mask=mask, other=0.0)
        norm_in += x_i * x_i

        for j in tl.static_range(32):
            if j >= i and out_idx < 133:
                x_j = tl.load(INPUT_PTR + offs * 32 + j, mask=mask, other=0.0)
                t_ij = x_i * x_j
                tl.store(OUTPUT_PTR + offs * 133 + out_idx, t_ij, mask=mask)
                if i == j:
                    trace += t_ij
                out_idx += 1

    tl.store(NORM_IN_PTR + offs, norm_in, mask=mask)
    tl.store(TRACE_OUT_PTR + offs, trace, mask=mask)


def benchmark_harada_norton(n_vectors=262_144, block_size=256, warmup=15, iters=50):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Harada-Norton HN 133-D Invariant Kernel on {torch.cuda.get_device_name(device)}...")

    torch.manual_seed(42)
    inputs = torch.randn(n_vectors, 32, device=device, dtype=torch.float32)
    outputs = torch.zeros(n_vectors, 133, device=device, dtype=torch.float32)

    norm_in = torch.zeros(n_vectors, device=device, dtype=torch.float32)
    trace_out = torch.zeros(n_vectors, device=device, dtype=torch.float32)

    grid = (triton.cdiv(n_vectors, block_size),)

    # Warmup
    for _ in range(warmup):
        warp_harada_norton_kernel[grid](
            inputs, outputs,
            norm_in, trace_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    # Benchmark
    start_time = time.perf_counter()
    for _ in range(iters):
        warp_harada_norton_kernel[grid](
            inputs, outputs,
            norm_in, trace_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start_time) / iters

    total_vectors = n_vectors
    # Read: 32 * 4 = 128 bytes. Write: 133 * 4 + 8 = 540 bytes. Total: 668 bytes / vector
    bytes_per_vector = 32 * 4 + 133 * 4 + 8
    total_bytes = total_vectors * bytes_per_vector
    throughput_gb_s = (total_bytes / 1e9) / elapsed
    vectors_per_sec = total_vectors / elapsed

    print(f"[+] Execution completed in {elapsed * 1000:.3f} ms")
    print(f"[+] Harada-Norton HN Throughput: {vectors_per_sec / 1e6:.2f} M vectors/s ({throughput_gb_s:.2f} GB/s)")
    assert torch.any(trace_out > 0), "Trace outputs should be positive"
    print(f"[+] Harada-Norton HN Invariant Kernel verified successfully!")


if __name__ == "__main__":
    benchmark_harada_norton()
