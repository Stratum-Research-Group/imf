#pragma once
/**
 * csrc/fused_blackwell_fp4_gemv.cu
 * Blackwell SM 12.0 Low-Latency Sub-Byte Autoregressive GEMV Kernel.
 * Executes single-token autoregressive generation (M = 1) across PLQ sub-bit weights
 * using warp-level reductions (__reduce_add_sync) directly in register files.
 */

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <stdint.h>

#define WARP_SIZE 32

__device__ __forceinline__ float decode_fp4_e2m1_fast(uint8_t nibble) {
    const float tbl[16] = {
        0.0f, 0.5f, 1.0f, 1.5f, 2.0f, 3.0f, 4.0f, 6.0f,
        -0.0f, -0.5f, -1.0f, -1.5f, -2.0f, -3.0f, -4.0f, -6.0f
    };
    return tbl[nibble & 0x0F];
}

extern "C" __global__ void fused_blackwell_fp4_gemv_kernel(
    const half* __restrict__ x,             // [K] Input vector (FP16)
    const uint8_t* __restrict__ W_packed,   // [K / 2, N] PLQ sub-bit weights
    const half* __restrict__ codebook,      // [16] E8 centroids
    half* __restrict__ y,                   // [N] Output logits
    int K, int N
) {
    int col = blockIdx.x; // Each block computes one or more output columns
    int tid = threadIdx.x;

    if (col < N) {
        float thread_sum = 0.0f;

        // Strided loop across K dimension
        for (int k_byte = tid; k_byte < K / 2; k_byte += blockDim.x) {
            half x0 = x[k_byte * 2];
            half x1 = x[k_byte * 2 + 1];

            uint8_t w_byte = W_packed[k_byte * N + col];
            float w0 = __half2float(codebook[w_byte & 0x0F]);
            float w1 = __half2float(codebook[(w_byte >> 4) & 0x0F]);

            thread_sum += __half2float(x0) * w0 + __half2float(x1) * w1;
        }

        // Warp synchronous tree reduction
        unsigned mask = 0xFFFFFFFF;
        #pragma unroll
        for (int offset = 16; offset > 0; offset /= 2) {
            thread_sum += __shfl_down_sync(mask, thread_sum, offset);
        }

        if (tid == 0) {
            y[col] = __float2half(thread_sum);
        }
    }
}
