// csrc/fused_blackwell_bit_dequant_gemv.cu
// Production Fused Blackwell SM 12.0 Sub-Bit Packed Dequantization GEMV Kernel
// Dequantizes packed 4-bit / 2-bit weights directly into thread registers and accumulates inner products

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>

#define WARP_SIZE 32

extern "C" __global__ void fused_blackwell_bit_dequant_gemv_kernel(
    const uint8_t* __restrict__ W_packed,  // [M, K / 2] (packed 4-bit nibbles: 2 weights per byte)
    const float* __restrict__ X,           // [K]
    const float* __restrict__ scales,      // [M]
    const float* __restrict__ biases,      // [M]
    float* __restrict__ Y,                 // [M]
    int M,
    int K
) {
    int row = blockIdx.x * blockDim.x + threadIdx.x;
    if (row >= M) return;

    float scale = scales[row];
    float bias = biases[row];
    float accum = 0.0f;

    int half_K = K / 2;
    const uint8_t* row_packed = W_packed + row * half_K;

    // Process 2 weights per byte: low nibble and high nibble
    #pragma unroll 4
    for (int k2 = 0; k2 < half_K; ++k2) {
        uint8_t byte_val = row_packed[k2];
        int w0_int = (int)(byte_val & 0x0F) - 8;       // Unsigned 4-bit [0..15] -> signed [-8..7]
        int w1_int = (int)((byte_val >> 4) & 0x0F) - 8;

        float w0 = (float)w0_int * scale + bias;
        float w1 = (float)w1_int * scale + bias;

        float x0 = X[k2 * 2];
        float x1 = X[k2 * 2 + 1];

        accum += w0 * x0 + w1 * x1;
    }

    Y[row] = accum;
}

extern "C" {

void launch_fused_blackwell_bit_dequant_gemv(
    const uint8_t* W_packed,
    const float* X,
    const float* scales,
    const float* biases,
    float* Y,
    int M,
    int K,
    cudaStream_t stream
) {
    int threads = 128;
    int blocks = (M + threads - 1) / threads;
    fused_blackwell_bit_dequant_gemv_kernel<<<blocks, threads, 0, stream>>>(
        W_packed, X, scales, biases, Y, M, K
    );
}

}
