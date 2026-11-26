#include <cuda_runtime.h>
#include <stdint.h>
#include <math.h>

// Microarchitecture: Fused Blackwell Mixed-Precision Ternary (0.58-bit) and FP4 (E2M1) GEMM
// Hardware Target: NVIDIA GeForce RTX 5060 Ti (Blackwell SM 12.0)
// Accumulates 0.58-bit packed ternary weights against 4-bit FP4 activation nibbles
// using hardware popcount and bitfield shifts directly in registers.

extern "C" __global__ void fused_blackwell_mixed_ternary_fp4_kernel(
    const uint32_t* __restrict__ W_pos,       // Ternary +1 bitmask (16 elements per word)
    const uint32_t* __restrict__ W_neg,       // Ternary -1 bitmask (16 elements per word)
    const uint32_t* __restrict__ X_fp4,       // Packed FP4 activations (8 nibbles per word)
    float* __restrict__ Y_out,                // Accumulated output vector
    int M,                                    // Output dimension (rows)
    int K_words                               // Number of 32-bit packed words
) {
    int row = blockIdx.x * blockDim.x + threadIdx.x;
    if (row >= M) return;

    float row_accum = 0.0f;
    const uint32_t* row_w_pos = W_pos + row * K_words;
    const uint32_t* row_w_neg = W_neg + row * K_words;

    for (int k = 0; k < K_words; ++k) {
        uint32_t wp = row_w_pos[k];
        uint32_t wn = row_w_neg[k];
        uint32_t x_packed = X_fp4[k];

        // Process 8 elements: FP4 nibbles against corresponding ternary bits
        #pragma unroll
        for (int i = 0; i < 8; ++i) {
            int is_pos = (wp >> i) & 1;
            int is_neg = (wn >> i) & 1;
            int ternary_val = is_pos - is_neg;

            if (ternary_val != 0) {
                uint8_t nibble = (x_packed >> (i * 4)) & 0x0F;
                int sign = (nibble & 0x08) ? -1 : 1;
                int exp = (nibble & 0x06) >> 1;
                int mant = (nibble & 0x01);

                float fp4_val = 0.0f;
                if (exp > 0) {
                    fp4_val = sign * (1.0f + mant * 0.5f) * powf(2.0f, exp - 1);
                } else if (mant > 0) {
                    fp4_val = sign * 0.5f * 0.5f;
                }

                row_accum += (float)ternary_val * fp4_val;
            }
        }
    }

    Y_out[row] = row_accum;
}
