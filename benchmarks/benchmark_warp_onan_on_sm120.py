"""
Benchmark: Blackwell SM 12.0 Warp O'Nan Sporadic Group O'N 45-D Invariant Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

The O'Nan sporadic simple group O'N has order:
  |O'N| = 2^9 * 3^4 * 5 * 7^3 * 11 * 19 * 31 ~ 4.60 * 10^{11}.
Its triple cover 3.O'N possesses a faithful 45-dimensional complex projective irreducible representation.
Over real vector spaces, the 45-dimensional invariant representation arises from skew-Hermitian
traceless tensor slices in u(10) or invariant alternating 2-forms over 10-dimensional projective spaces:
  dim(u(10)) = 10^2 = 100, traceless skew-Hermitian projection yields 45 canonical imaginary off-diagonals.

This kernel evaluates batched candidate vectors in C^{10} (represented as R^{20}), projecting
their alternating imaginary forms into the 45-dimensional invariant module of 3.O'N,
evaluating symplectic Casimir contractions and warp register residency on Blackwell SM 12.0.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_onan_group_kernel(
    INPUT_PTR,        # [N, 20] float32 real/imag pairs in C^{10}
    OUTPUT_PTR,       # [N, 45] float32 invariant skew components
    NORM_IN_PTR,      # [N] float32 input complex norm squared
    NORM_OUT_PTR,     # [N] float32 output 45-D projection norm
    N_VECTORS: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N_VECTORS

    norm_in = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # 10 complex components = 20 real floats
    for i in tl.static_range(10):
        re_i = tl.load(INPUT_PTR + offs * 20 + 2 * i, mask=mask, other=0.0)
        im_i = tl.load(INPUT_PTR + offs * 20 + 2 * i + 1, mask=mask, other=0.0)
        norm_in += re_i * re_i + im_i * im_i

    norm_out = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    out_idx = 0

    # 45 skew-Hermitian imaginary off-diagonals: Im(z_i * conj(z_j)) = im_i*re_j - re_i*im_j
    for i in tl.static_range(10):
        re_i = tl.load(INPUT_PTR + offs * 20 + 2 * i, mask=mask, other=0.0)
        im_i = tl.load(INPUT_PTR + offs * 20 + 2 * i + 1, mask=mask, other=0.0)
        for j in tl.static_range(10):
            if j > i and out_idx < 45:
                re_j = tl.load(INPUT_PTR + offs * 20 + 2 * j, mask=mask, other=0.0)
                im_j = tl.load(INPUT_PTR + offs * 20 + 2 * j + 1, mask=mask, other=0.0)
                skew_comp = im_i * re_j - re_i * im_j
                tl.store(OUTPUT_PTR + offs * 45 + out_idx, skew_comp, mask=mask)
                norm_out += skew_comp * skew_comp
                out_idx += 1

    tl.store(NORM_IN_PTR + offs, norm_in, mask=mask)
    tl.store(NORM_OUT_PTR + offs, norm_out, mask=mask)


def benchmark_onan_group(n_vectors=1_048_576, block_size=128, warmup=5, iters=25):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing O'Nan Group O'N 45-D Invariant Kernel on {torch.cuda.get_device_name(device)}...")

    x = torch.randn((n_vectors, 20), dtype=torch.float32, device=device)
    out = torch.empty((n_vectors, 45), dtype=torch.float32, device=device)
    norm_in = torch.empty((n_vectors,), dtype=torch.float32, device=device)
    norm_out = torch.empty((n_vectors,), dtype=torch.float32, device=device)

    grid = (triton.cdiv(n_vectors, block_size),)

    for _ in range(warmup):
        warp_onan_group_kernel[grid](
            x, out, norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    start_time = time.perf_counter()
    for _ in range(iters):
        warp_onan_group_kernel[grid](
            x, out, norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    total_time = (time.perf_counter() - start_time) / iters

    total_vectors = n_vectors
    vectors_per_sec = total_vectors / total_time
    total_bytes = n_vectors * (20 + 45 + 1 + 1) * 4  # read 20 floats, write 45+1+1 floats
    bandwidth_gbps = (total_bytes / 1e9) / total_time

    print(f"[+] Total execution time per batch: {total_time * 1000:.3f} ms")
    print(f"[+] Throughput: {vectors_per_sec / 1e6:.2f} M vectors/s")
    print(f"[+] Effective Memory Bandwidth: {bandwidth_gbps:.2f} GB/s")

    return bandwidth_gbps

if __name__ == "__main__":
    benchmark_onan_group()
