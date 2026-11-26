#include <cuda_runtime.h>
#include <stdint.h>
#include <math.h>

// Microarchitecture: Fused Blackwell In-Register Bit-Level LayerNorm Normalizer
// Hardware Target: NVIDIA GeForce RTX 5060 Ti (Blackwell SM 12.0)
// Computes normalized statistics directly over bipolar ternary / bit-packed states
// using warp population counts and fast integer reciprocal approximations.

extern "C" __global__ void fused_blackwell_bit_layernorm_kernel(
    const uint32_t* __restrict__ in_bitplane0,   // Magnitude threshold bits [Batch, Words]
    const uint32_t* __restrict__ in_bitplane1,   // Sign polarity bits [Batch, Words]
    float* __restrict__ out_normalized,          // Output normalized floats [Batch, Words * 32]
    int words_per_row
) {
    int b = blockIdx.x;
    int lane = threadIdx.x; // 32 threads in a warp

    int total_elements = words_per_row * 32;
    int row_popc_sum = 0;
    int row_active_count = 0;

    // Phase 1: Compute mean over row
    for (int w = lane; w < words_per_row; w += 32) {
        uint32_t mag = in_bitplane0[b * words_per_row + w];
        uint32_t sign = in_bitplane1[b * words_per_row + w];

        int pos_bits = __popc(mag & sign);
        int neg_bits = __popc(mag & (~sign));

        row_popc_sum += (pos_bits - neg_bits);
        row_active_count += (pos_bits + neg_bits);
    }

    // Warp tree reduction for sum and active count
    for (int offset = 16; offset > 0; offset /= 2) {
        row_popc_sum += __shfl_down_sync(0xffffffff, row_popc_sum, offset);
        row_active_count += __shfl_down_sync(0xffffffff, row_active_count, offset);
    }

    float mean = __shfl_sync(0xffffffff, row_popc_sum, 0) / (float)total_elements;
    float variance = 1.0f / sqrtf((float)row_active_count / (float)total_elements + 1e-5f);

    // Phase 2: Compute normalized outputs
    for (int w = lane; w < words_per_row; w += 32) {
        uint32_t mag = in_bitplane0[b * words_per_row + w];
        uint32_t sign = in_bitplane1[b * words_per_row + w];

        for (int bit = 0; bit < 32; ++bit) {
            bool is_active = (mag >> bit) & 1;
            bool is_pos = (sign >> bit) & 1;
            float val = is_active ? (is_pos ? 1.0f : -1.0f) : 0.0f;

            out_normalized[b * total_elements + w * 32 + bit] = (val - mean) * variance;
        }
    }
}
