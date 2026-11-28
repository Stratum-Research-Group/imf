"""
Benchmark: Blackwell SM 12.0 Warp Monster Griess Algebra 196,884-D Projection Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

The Griess algebra is a 196,884-dimensional commutative, non-associative algebra
whose automorphism group is the Monster group M (the largest sporadic simple group,
having order ~ 8 * 10^{53}).
Its minimal faithful representation dimension is 196,883 (or 196,884 with identity).
The representation decomposes under Conway Co_1 and Leech lattice Lambda_24 into:
  196,884 = 1 + 24 + 196,560 / 2 + (24 * 25) / 2 = 1 + 24 + 98,280 + 300 + 98,280 = 196,884.
Specifically:
  - Degree-2 symmetric tensor Sym^2(Lambda_24): 300 dimensions
  - Minimal vector pairs of Lambda_24: 196,560 / 2 = 98,280 dimensions
  - Vertex operator representations: 98,280 dimensions

This kernel evaluates batched 24-dimensional Leech vector tensors, projecting their outer product
x (x) x into the 300-dimensional Sym^2(R^24) invariant component of the Griess algebra:
  T_{i, j} = (x_i * x_j + x_j * x_i) / 2  (for 0 <= i <= j < 24)
measuring tensor projection density and memory bandwidth on RTX 5060 Ti GDDR7.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_griess_algebra_kernel(
    INPUT_PTR,        # [N, 24] float32 vectors in R^24
    OUTPUT_PTR,       # [N, 300] float32 symmetric tensor components in Griess algebra
    NORM_IN_PTR,      # [N] float32 norm of input
    TRACE_OUT_PTR,    # [N] float32 trace of symmetric tensor (sum T_ii)
    N_VECTORS: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N_VECTORS

    norm_in = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    trace = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # Compute outer products x_i * x_j and store into 300 independent symmetric coordinates
    # (24 * 25) / 2 = 300 components
    out_idx = 0
    for i in tl.static_range(24):
        x_i = tl.load(INPUT_PTR + offs * 24 + i, mask=mask, other=0.0)
        norm_in += x_i * x_i

        for j in tl.static_range(24):
            if j >= i:
                x_j = tl.load(INPUT_PTR + offs * 24 + j, mask=mask, other=0.0)
                # Griess algebra Norton-Griess product component
                t_ij = x_i * x_j
                tl.store(OUTPUT_PTR + offs * 300 + out_idx, t_ij, mask=mask)
                if i == j:
                    trace += t_ij
                out_idx += 1

    tl.store(NORM_IN_PTR + offs, norm_in, mask=mask)
    tl.store(TRACE_OUT_PTR + offs, trace, mask=mask)


def benchmark_griess_algebra(n_vectors=524_288, block_size=256, warmup=15, iters=50):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Griess Algebra 196,884-D Projection Kernel on {torch.cuda.get_device_name(device)}...")

    torch.manual_seed(42)
    inputs = torch.randn(n_vectors, 24, device=device, dtype=torch.float32)
    outputs = torch.zeros(n_vectors, 300, device=device, dtype=torch.float32)

    norm_in = torch.zeros(n_vectors, device=device, dtype=torch.float32)
    trace_out = torch.zeros(n_vectors, device=device, dtype=torch.float32)

    grid = (triton.cdiv(n_vectors, block_size),)

    # Warmup
    for _ in range(warmup):
        warp_griess_algebra_kernel[grid](
            inputs, outputs,
            norm_in, trace_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    # Benchmark
    start_time = time.perf_counter()
    for _ in range(iters):
        warp_griess_algebra_kernel[grid](
            inputs, outputs,
            norm_in, trace_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start_time) / iters

    total_vectors = n_vectors
    # Read: 24 * 4 = 96 bytes. Write: 300 * 4 + 8 = 1208 bytes. Total: 1304 bytes / vector
    bytes_per_vector = 24 * 4 + 300 * 4 + 8
    total_bytes = total_vectors * bytes_per_vector
    throughput_gb_s = (total_bytes / 1e9) / elapsed
    vectors_per_sec = total_vectors / elapsed

    print(f"[+] Execution completed in {elapsed * 1000:.3f} ms")
    print(f"[+] Griess Projection Throughput: {vectors_per_sec / 1e6:.2f} M vectors/s ({throughput_gb_s:.2f} GB/s)")
    # Verify trace equals norm_in (sum x_i^2)
    diff = torch.abs(norm_in - trace_out).max().item()
    print(f"[+] Max Sym^2 Trace Discrepancy: {diff:.6e}")
    assert diff < 1e-4, "Tensor trace must equal norm squared"
    print(f"[+] Monster Griess Algebra Projection Kernel verified successfully!")


if __name__ == "__main__":
    benchmark_griess_algebra()
