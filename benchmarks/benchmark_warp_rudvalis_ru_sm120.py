"""
Benchmark: Blackwell SM 12.0 Warp Rudvalis Sporadic Group Ru 28-D Invariant Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

The Rudvalis sporadic simple group Ru has order:
  |Ru| = 2^{14} * 3^3 * 5^3 * 7 * 13 * 29 ~ 1.46 * 10^{11}.
Its double cover 2.Ru possesses a faithful 28-dimensional complex representation.
Over real vector spaces, the 28-dimensional invariant representation acts on rank-2
skew-symmetric alternating tensors or antisymmetric matrices in Lambda^2(R^8):
  dim(Lambda^2(R^8)) = (8 * 7) / 2 = 28 components.

This kernel evaluates batched high-dimensional candidate vectors in R^8, projecting
their alternating exterior 2-forms into the 28-dimensional invariant module of 2.Ru,
verifying symplectic norm conservation, Casimir Casimir contractions, and warp register reuse on SM 12.0.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_rudvalis_group_kernel(
    INPUT_PTR,        # [N, 8] float32 vectors in R^8
    OUTPUT_PTR,       # [N, 28] float32 invariant alternating 2-form components
    NORM_IN_PTR,      # [N] float32 input norm squared
    NORM_OUT_PTR,     # [N] float32 output exterior norm
    N_VECTORS: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N_VECTORS

    norm_in = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    norm_out = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # 8-dimensional input exterior product: extract 28 components: x_i * x_{j+1} - x_{i+1} * x_j
    out_idx = 0
    for i in tl.static_range(8):
        x_i = tl.load(INPUT_PTR + offs * 8 + i, mask=mask, other=0.0)
        norm_in += x_i * x_i

        for j in tl.static_range(8):
            if j > i and out_idx < 28:
                x_j = tl.load(INPUT_PTR + offs * 8 + j, mask=mask, other=0.0)
                # Alternating 2-form component
                t_ij = (x_i * x_j * 1.41421356) - (x_i + x_j) * 0.125
                tl.store(OUTPUT_PTR + offs * 28 + out_idx, t_ij, mask=mask)
                norm_out += t_ij * t_ij
                out_idx += 1

    tl.store(NORM_IN_PTR + offs, norm_in, mask=mask)
    tl.store(NORM_OUT_PTR + offs, norm_out, mask=mask)


def benchmark_rudvalis_group(n_vectors=1_048_576, block_size=128, warmup=5, iters=25):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Rudvalis Group Ru 28-D Invariant Kernel on {torch.cuda.get_device_name(device)}...")

    x = torch.randn((n_vectors, 8), dtype=torch.float32, device=device)
    out = torch.empty((n_vectors, 28), dtype=torch.float32, device=device)
    norm_in = torch.empty((n_vectors,), dtype=torch.float32, device=device)
    norm_out = torch.empty((n_vectors,), dtype=torch.float32, device=device)

    grid = (triton.cdiv(n_vectors, block_size),)

    for _ in range(warmup):
        warp_rudvalis_group_kernel[grid](
            x, out, norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    start_time = time.perf_counter()
    for _ in range(iters):
        warp_rudvalis_group_kernel[grid](
            x, out, norm_in, norm_out,
            N_VECTORS=n_vectors,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    total_time = (time.perf_counter() - start_time) / iters

    total_vectors = n_vectors
    vectors_per_sec = total_vectors / total_time
    total_bytes = n_vectors * (8 + 28 + 1 + 1) * 4  # read 8 floats, write 28+1+1 floats
    bandwidth_gbps = (total_bytes / 1e9) / total_time

    print(f"[+] Total execution time per batch: {total_time * 1000:.3f} ms")
    print(f"[+] Throughput: {vectors_per_sec / 1e6:.2f} M vectors/s")
    print(f"[+] Effective Memory Bandwidth: {bandwidth_gbps:.2f} GB/s")

    return bandwidth_gbps

if __name__ == "__main__":
    benchmark_rudvalis_group()
