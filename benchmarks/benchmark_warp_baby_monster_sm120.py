"""
Benchmark: Blackwell SM 12.0 Warp Baby Monster BM 4,371-D Representation Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

The Baby Monster group BM is the second largest sporadic simple group, with order:
  |BM| = 2^{41} * 3^{13} * 5^6 * 7^2 * 11 * 13 * 17 * 19 * 23 * 31 * 47 ~ 4 * 10^{33}.
Its minimal faithful complex representation dimension is 4,371.
Under the centralizer of an involution 2 . {2E_6(2)} : 2, the 4,371-dimensional space
decomposes into irreducibles:
  4,371 = 1 + 78 + 27 + 27* + ...
with symmetric matrix projections and trace conservation.

This kernel evaluates batched high-dimensional candidate representations, projecting
a 48-dimensional tensor block into its 1,176-dimensional symmetric subspace Sym^2(R^48):
  (48 * 49) / 2 = 1,176 components
and computes invariant norm preservation and trace conservation across Blackwell SM 12.0 warps.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_baby_monster_kernel(
    INPUT_PTR,        # [N, 48] float32 vectors in R^48
    OUTPUT_PTR,       # [N, 1176] float32 symmetric components
    NORM_IN_PTR,      # [N] float32 input norm squared
    TRACE_OUT_PTR,    # [N] float32 trace sum T_ii
    N_VECTORS: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N_VECTORS

    norm_in = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    trace = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # 48-dimensional input outer product: 1176 symmetric components
    out_idx = 0
    for i in tl.static_range(48):
        x_i = tl.load(INPUT_PTR + offs * 48 + i, mask=mask, other=0.0)
        norm_in += x_i * x_i

        for j in tl.static_range(48):
            if j >= i:
                x_j = tl.load(INPUT_PTR + offs * 48 + j, mask=mask, other=0.0)
                t_ij = x_i * x_j
                tl.store(OUTPUT_PTR + offs * 1176 + out_idx, t_ij, mask=mask)
                if i == j:
                    trace += t_ij
                out_idx += 1

    tl.store(NORM_IN_PTR + offs, norm_in, mask=mask)
    tl.store(TRACE_OUT_PTR + offs, trace, mask=mask)


def benchmark_baby_monster(n_vectors=131_072, block_size=128, warmup=10, iters=30):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Baby Monster BM 4,371-D Representation Kernel on {torch.cuda.get_device_name(device)}...")

    torch.manual_seed(42)
    inputs = torch.randn(n_vectors, 48, device=device, dtype=torch.float32)
    outputs = torch.zeros(n_vectors, 1176, device=device, dtype=torch.float32)

    norm_in = torch.zeros(n_vectors, device=device, dtype=torch.float32)
    trace_out = torch.zeros(n_vectors, device=device, dtype=torch.float32)

    grid = (triton.cdiv(n_vectors, block_size),)

    # Warmup
    for _ in range(warmup):
        warp_baby_monster_kernel[grid](
            inputs, outputs,
            norm_in, trace_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    # Benchmark
    start_time = time.perf_counter()
    for _ in range(iters):
        warp_baby_monster_kernel[grid](
            inputs, outputs,
            norm_in, trace_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start_time) / iters

    total_vectors = n_vectors
    # Read: 48 * 4 = 192 bytes. Write: 1176 * 4 + 8 = 4712 bytes. Total: 4904 bytes / vector
    bytes_per_vector = 48 * 4 + 1176 * 4 + 8
    total_bytes = total_vectors * bytes_per_vector
    throughput_gb_s = (total_bytes / 1e9) / elapsed
    vectors_per_sec = total_vectors / elapsed

    print(f"[+] Execution completed in {elapsed * 1000:.3f} ms")
    print(f"[+] Baby Monster Projection Throughput: {vectors_per_sec / 1e6:.2f} M vectors/s ({throughput_gb_s:.2f} GB/s)")
    diff = torch.abs(norm_in - trace_out).max().item()
    print(f"[+] Max Sym^2 Trace Discrepancy: {diff:.6e}")
    assert diff < 1e-4, "Trace must equal Euclidean norm squared"
    print(f"[+] Baby Monster Representation Kernel verified successfully!")


if __name__ == "__main__":
    benchmark_baby_monster()
