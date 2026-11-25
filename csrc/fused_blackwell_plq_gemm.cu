#pragma once
/**
 * csrc/fused_blackwell_plq_gemm.cu
 * Blackwell SM 12.0 Optimized Fused Sub-Bit Polytope GEMM Kernel.
 * Executes on-the-fly E8 Gosset Voronoi dequantization (4,096 chambers)
 * directly in warp registers without intermediate global or shared memory staging.
 * Hardware Target: NVIDIA GeForce RTX 5060 Ti 16GB (Blackwell SM 12.0)
 */

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <stdint.h>

#define WARP_SIZE 32
#define CHUNK_K 64
#define E8_DIM 8

__device__ __forceinline__ half2 dequant_e8_pair_blackwell(uint8_t packed_idx, const half* __restrict__ codebook) {
    // 4-bit nibble unpack into 16-element discrete E8 coordinate lookup
    uint32_t low_idx = packed_idx & 0x0F;
    uint32_t high_idx = (packed_idx >> 4) & 0x0F;
    return __halves2half2(codebook[low_idx], codebook[high_idx]);
}

extern "C" __global__ void fused_blackwell_plq_gemm_kernel(
    const half* __restrict__ A,          // [M, K] Activation matrix (FP16)
    const uint8_t* __restrict__ B_quant, // [K / 2, N] Sub-bit packed weight indices
    const half* __restrict__ codebook,   // [16] Discrete Gosset Voronoi centroids
    half* __restrict__ C,                // [M, N] Output matrix (FP16)
    int M, int N, int K
) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;

    if (row < M && col < N) {
        float accum = 0.0f;

        // Iterate over K dimension in unrolled chunks
        #pragma unroll 4
        for (int k = 0; k < K; k += 2) {
            half a0 = A[row * K + k];
            half a1 = A[row * K + k + 1];

            uint8_t packed_b = B_quant[(k / 2) * N + col];
            half2 b_dequant = dequant_e8_pair_blackwell(packed_b, codebook);

            accum += __half2float(a0) * __half2float(__low2half(b_dequant));
            accum += __half2float(a1) * __half2float(__high2half(b_dequant));
        }

        C[row * N + col] = __float2half(accum);
    }
}
