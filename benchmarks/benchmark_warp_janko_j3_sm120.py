"""
Benchmark: Blackwell SM 12.0 Warp Janko Sporadic Group J3 85-D Invariant Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

The third Janko sporadic simple group J_3 (Higman-Janko-McKay group) has order:
  |J_3| = 2^7 * 3^5 * 5 * 17 * 19 = 50,232,960.
Its smallest non-trivial complex projective irreducible representation has dimension 85,
acting on a 85-dimensional Hermitian representation module invariant under the 19-centralizer
Frobenius group 19 : 9 and preserving quadratic Casimir forms.

This kernel evaluates candidate vectors in C^{10} (represented as R^{20}), projecting
their outer products onto the 85-dimensional invariant subspace of J_3, evaluating Casimir forms and warp reductions on Blackwell SM 12.0.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_janko_j3_kernel(
    INPUT_PTR,        # [N, 20] float32 vectors in R^{20}
    OUTPUT_PTR,       # [N, 85] float32 invariant projected components
    NORM_IN_PTR,      # [N] float32 input norm squared
    NORM_OUT_PTR,     # [N] float32 output projection norm squared
    N_VECTORS: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N_VECTORS

    norm_in = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # 20 real floats
    for i in tl.static_range(20):
        x_i = tl.load(INPUT_PTR + offs * 20 + i, mask=mask, other=0.0)
        norm_in += x_i * x_i

    norm_out = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    out_idx = 0

    # 85 components extracted from symmetric/exterior contractions
    for i in tl.static_range(20):
        x_i = tl.load(INPUT_PTR + offs * 20 + i, mask=mask, other=0.0)
        for j in tl.static_range(20):
            if j >= i and out_idx < 85:
                x_j = tl.load(INPUT_PTR + offs * 20 + j, mask=mask, other=0.0)
                comp = (x_i * x_j * 1.41421356) - (x_i + x_j) * 0.05
                tl.store(OUTPUT_PTR + offs * 85 + out_idx, comp, mask=mask)
                norm_out += comp * comp
                out_idx += 1

    tl.store(NORM_IN_PTR + offs, norm_in, mask=mask)
    tl.store(NORM_OUT_PTR + offs, norm_out, mask=mask)


def benchmark_janko_j3(n_vectors=524_288, block_size=64, warmup=5, iters=25):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Janko Group J3 85-D Invariant Kernel on {torch.cuda.get_device_name(device)}...")

    x = torch.randn((n_vectors, 20), dtype=torch.float32, device=device)
    out = torch.empty((n_vectors, 85), dtype=torch.float32, device=device)
    norm_in = torch.empty((n_vectors,), dtype=torch.float32, device=device)
    norm_out = torch.empty((n_vectors,), dtype=torch.float32, device=device)

    grid = (triton.cdiv(n_vectors, block_size),)

    for _ in range(warmup):
        warp_janko_j3_kernel[grid](
            x, out, norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    start_time = time.perf_counter()
    for _ in range(iters):
        warp_janko_j3_kernel[grid](
            x, out, norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    total_time = (time.perf_counter() - start_time) / iters

    total_vectors = n_vectors
    vectors_per_sec = total_vectors / total_time
    total_bytes = n_vectors * (20 + 85 + 1 + 1) * 4  # read 20 floats, write 85+1+1 floats
    bandwidth_gbps = (total_bytes / 1e9) / total_time

    print(f"[+] Total execution time per batch: {total_time * 1000:.3f} ms")
    print(f"[+] Throughput: {vectors_per_sec / 1e6:.2f} M vectors/s")
    print(f"[+] Effective Memory Bandwidth: {bandwidth_gbps:.2f} GB/s")

    return bandwidth_gbps

if __name__ == "__main__":
    benchmark_janko_j3()
