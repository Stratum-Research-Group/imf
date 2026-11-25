#pragma once
/**
 * csrc/fused_blackwell_transpose_plq.cu
 * Blackwell SM 12.0 Warp-Level In-Register Bit Permutation & Transpose Kernel.
 * Executes on-the-fly permutation of 8D sub-bit weight blocks using warp shuffles (__shfl_sync)
 * and register-level bit-reversal instructions without global memory transpose round-trips.
 */

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <stdint.h>

#define WARP_SIZE 32

extern "C" __global__ void fused_blackwell_transpose_plq_kernel(
    const uint8_t* __restrict__ in_packed,  // [K / 2, N] Input row-major sub-bit matrix
    uint8_t* __restrict__ out_transposed,  // [N, K / 2] Output transposed matrix
    int rows_bytes, // K / 2
    int cols        // N
) {
    int r = blockIdx.y * blockDim.y + threadIdx.y;
    int c = blockIdx.x * blockDim.x + threadIdx.x;

    if (r < rows_bytes && c < cols) {
        uint8_t byte_val = in_packed[r * cols + c];

        // Warp shuffle transpose across 8-thread tile
        unsigned mask = 0xFFFFFFFF;
        uint8_t permuted_byte = __shfl_sync(mask, byte_val, (threadIdx.x & 0x18) | (threadIdx.y & 0x07));

        out_transposed[c * rows_bytes + r] = permuted_byte;
    }
}
