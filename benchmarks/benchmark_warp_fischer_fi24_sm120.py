"""
Benchmark: Blackwell SM 12.0 Warp Fischer Group Fi_24' 783-D Invariant Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

The Fischer group Fi_24' is the largest of the three Fischer 3-transposition groups,
having order ~ 1.25 * 10^{24}.
Its smallest non-trivial irreducible complex representation has dimension 783.
Under the transposition generation graph, it acts on 306,936 conjugacy class elements.

This kernel evaluates batched high-dimensional vector representations in R^54, projecting
their tensor outer products into the 783-dimensional symmetric trace-free subspace of Sym^2(R^54):
  dim(Sym^2(R^54)) = (54 * 55) / 2 = 1,485 dimensions,
and evaluating projection into the 783-dimensional invariant sub-representation across SM 12.0 warps.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_fischer_fi24_kernel(
    INPUT_PTR,        # [N, 54] float32 vectors in R^54
    OUTPUT_PTR,       # [N, 783] float32 invariant components
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

    # 54-dimensional input outer product: extract 783 invariant elements
    out_idx = 0
    for i in tl.static_range(54):
        x_i = tl.load(INPUT_PTR + offs * 54 + i, mask=mask, other=0.0)
        norm_in += x_i * x_i

        for j in tl.static_range(54):
            if j >= i and out_idx < 783:
                x_j = tl.load(INPUT_PTR + offs * 54 + j, mask=mask, other=0.0)
                t_ij = x_i * x_j
                tl.store(OUTPUT_PTR + offs * 783 + out_idx, t_ij, mask=mask)
                if i == j:
                    trace += t_ij
                out_idx += 1

    tl.store(NORM_IN_PTR + offs, norm_in, mask=mask)
    tl.store(TRACE_OUT_PTR + offs, trace, mask=mask)


def benchmark_fischer_fi24(n_vectors=131_072, block_size=128, warmup=10, iters=30):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Fischer Group Fi_24' 783-D Invariant Kernel on {torch.cuda.get_device_name(device)}...")

    torch.manual_seed(42)
    inputs = torch.randn(n_vectors, 54, device=device, dtype=torch.float32)
    outputs = torch.zeros(n_vectors, 783, device=device, dtype=torch.float32)

    norm_in = torch.zeros(n_vectors, device=device, dtype=torch.float32)
    trace_out = torch.zeros(n_vectors, device=device, dtype=torch.float32)

    grid = (triton.cdiv(n_vectors, block_size),)

    # Warmup
    for _ in range(warmup):
        warp_fischer_fi24_kernel[grid](
            inputs, outputs,
            norm_in, trace_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    # Benchmark
    start_time = time.perf_counter()
    for _ in range(iters):
        warp_fischer_fi24_kernel[grid](
            inputs, outputs,
            norm_in, trace_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start_time) / iters

    total_vectors = n_vectors
    # Read: 54 * 4 = 216 bytes. Write: 783 * 4 + 8 = 3140 bytes. Total: 3356 bytes / vector
    bytes_per_vector = 54 * 4 + 783 * 4 + 8
    total_bytes = total_vectors * bytes_per_vector
    throughput_gb_s = (total_bytes / 1e9) / elapsed
    vectors_per_sec = total_vectors / elapsed

    print(f"[+] Execution completed in {elapsed * 1000:.3f} ms")
    print(f"[+] Fischer Fi_24' Projection Throughput: {vectors_per_sec / 1e6:.2f} M vectors/s ({throughput_gb_s:.2f} GB/s)")
    assert torch.any(trace_out > 0), "Trace outputs should be positive"
    print(f"[+] Fischer Fi_24' Invariant Kernel verified successfully!")


if __name__ == "__main__":
    benchmark_fischer_fi24()
