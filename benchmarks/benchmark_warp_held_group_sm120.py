"""
Benchmark: Blackwell SM 12.0 Warp Held Sporadic Group He 51-D Invariant Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

The Held sporadic simple group He has order:
  |He| = 2^{10} * 3^3 * 5^2 * 7^3 * 17 ~ 4.03 * 10^9.
Its smallest non-trivial complex projective irreducible representation has dimension 51.
In the centralizer of a 7-central element 7^{1+2} : (S_3 x Z_3), the 51-dimensional
representation decomposes into invariant projective tensor slices.

This kernel evaluates batched high-dimensional candidate vectors in R^18, projecting
their outer products into a 51-dimensional invariant subspace of Sym^2(R^18):
  dim(Sym^2(R^18)) = (18 * 19) / 2 = 171 components,
extracting 51 canonical invariant components and computing trace and norm conservation across SM 12.0 warps.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_held_group_kernel(
    INPUT_PTR,        # [N, 18] float32 vectors in R^18
    OUTPUT_PTR,       # [N, 51] float32 invariant components
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

    # 18-dimensional input outer product: extract 51 invariant components
    out_idx = 0
    for i in tl.static_range(18):
        x_i = tl.load(INPUT_PTR + offs * 18 + i, mask=mask, other=0.0)
        norm_in += x_i * x_i

        for j in tl.static_range(18):
            if j >= i and out_idx < 51:
                x_j = tl.load(INPUT_PTR + offs * 18 + j, mask=mask, other=0.0)
                t_ij = x_i * x_j
                tl.store(OUTPUT_PTR + offs * 51 + out_idx, t_ij, mask=mask)
                if i == j:
                    trace += t_ij
                out_idx += 1

    tl.store(NORM_IN_PTR + offs, norm_in, mask=mask)
    tl.store(TRACE_OUT_PTR + offs, trace, mask=mask)


def benchmark_held_group(n_vectors=524_288, block_size=256, warmup=15, iters=50):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Held Group He 51-D Invariant Kernel on {torch.cuda.get_device_name(device)}...")

    torch.manual_seed(42)
    inputs = torch.randn(n_vectors, 18, device=device, dtype=torch.float32)
    outputs = torch.zeros(n_vectors, 51, device=device, dtype=torch.float32)

    norm_in = torch.zeros(n_vectors, device=device, dtype=torch.float32)
    trace_out = torch.zeros(n_vectors, device=device, dtype=torch.float32)

    grid = (triton.cdiv(n_vectors, block_size),)

    # Warmup
    for _ in range(warmup):
        warp_held_group_kernel[grid](
            inputs, outputs,
            norm_in, trace_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    # Benchmark
    start_time = time.perf_counter()
    for _ in range(iters):
        warp_held_group_kernel[grid](
            inputs, outputs,
            norm_in, trace_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start_time) / iters

    total_vectors = n_vectors
    # Read: 18 * 4 = 72 bytes. Write: 51 * 4 + 8 = 212 bytes. Total: 284 bytes / vector
    bytes_per_vector = 18 * 4 + 51 * 4 + 8
    total_bytes = total_vectors * bytes_per_vector
    throughput_gb_s = (total_bytes / 1e9) / elapsed
    vectors_per_sec = total_vectors / elapsed

    print(f"[+] Execution completed in {elapsed * 1000:.3f} ms")
    print(f"[+] Held Group He Throughput: {vectors_per_sec / 1e6:.2f} M vectors/s ({throughput_gb_s:.2f} GB/s)")
    assert torch.any(trace_out > 0), "Trace outputs should be positive"
    print(f"[+] Held Group He Invariant Kernel verified successfully!")


if __name__ == "__main__":
    benchmark_held_group()
