#include <cuda_runtime.h>
#include <stdint.h>

// Microarchitecture: Fused Blackwell FP8 (E4M3) Matrix-Vector Contraction
// Hardware Target: NVIDIA GeForce RTX 5060 Ti (Blackwell SM 12.0)
// High-efficiency sub-byte autoregressive decoding for 70B parameter inference.

extern "C" __global__ void fused_blackwell_fp8_gemv_kernel(
    const uint8_t* __restrict__ W_fp8,     // Weight matrix [M, K] in FP8 E4M3
    const float* __restrict__ X_in,        // Activation vector [K] in FP32
    float* __restrict__ Y_out,             // Output vector [M] in FP32
    int M,
    int K
) {
    int row = blockIdx.x * blockDim.x + threadIdx.x;
    if (row >= M) return;

    float accum = 0.0f;
    const uint8_t* row_ptr = W_fp8 + row * K;

    for (int k = 0; k < K; ++k) {
        uint8_t raw = row_ptr[k];
        // Decode FP8 E4M3: 1 sign bit, 4 exponent bits (bias 7), 3 mantissa bits
        int sign = (raw & 0x80) ? -1 : 1;
        int exp = (raw & 0x78) >> 3;
        int mant = (raw & 0x07);

        float val = 0.0f;
        if (exp > 0) {
            val = sign * (1.0f + mant / 8.0f) * powf(2.0f, exp - 7);
        } else if (mant > 0) {
            val = sign * (mant / 8.0f) * powf(2.0f, -6);
        }

        accum += val * X_in[k];
    }

    Y_out[row] = accum;
}
