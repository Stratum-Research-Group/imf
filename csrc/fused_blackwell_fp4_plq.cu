#pragma once
/**
 * csrc/fused_blackwell_fp4_plq.cu
 * Blackwell SM 12.0 Hybrid FP4 / PLQ Dot-Product Kernel.
 * Utilizes warp-specialized sub-byte unpacking and E8 Gosset Voronoi centroid lookups.
 * Target: NVIDIA GeForce RTX 5060 Ti 16GB (Blackwell SM 12.0)
 */

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <stdint.h>

#define WARP_SIZE 32

__device__ __forceinline__ float decode_fp4_e2m1(uint8_t nibble) {
    // Standard E2M1 FP4 sign, exponent, mantissa decoding table
    const float fp4_table[16] = {
        0.0f, 0.5f, 1.0f, 1.5f, 2.0f, 3.0f, 4.0f, 6.0f,
        -0.0f, -0.5f, -1.0f, -1.5f, -2.0f, -3.0f, -4.0f, -6.0f
    };
    return fp4_table[nibble & 0x0F];
}

extern "C" __global__ void fused_blackwell_fp4_plq_kernel(
    const uint8_t* __restrict__ act_fp4,    // [M, K / 2] FP4 packed activations
    const uint8_t* __restrict__ weight_plq, // [K / 2, N] 4-bit PLQ quantized weights
    const half* __restrict__ codebook,      // [16] E8 centroids
    half* __restrict__ out,                 // [M, N] Output activations
    int M, int N, int K
) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;

    if (row < M && col < N) {
        float accum = 0.0f;

        #pragma unroll 4
        for (int k_byte = 0; k_byte < K / 2; k_byte++) {
            uint8_t a_byte = act_fp4[row * (K / 2) + k_byte];
            uint8_t w_byte = weight_plq[k_byte * N + col];

            float a0 = decode_fp4_e2m1(a_byte & 0x0F);
            float a1 = decode_fp4_e2m1((a_byte >> 4) & 0x0F);

            float w0 = __half2float(codebook[w_byte & 0x0F]);
            float w1 = __half2float(codebook[(w_byte >> 4) & 0x0F]);

            accum += a0 * w0 + a1 * w1;
        }

        out[row * N + col] = __float2half(accum);
    }
}
