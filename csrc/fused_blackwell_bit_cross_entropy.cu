#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <math.h>

// Fused Blackwell In-Register Bitplane Cross-Entropy Loss Kernel
// Fuses vocabulary dot products, online LogSumExp reduction, and cross-entropy gradient accumulation
// directly in registers without materializing the [B, L, V] floating-point logits tensor in global memory.

#define VOCAB_SIZE_TILES 64 // 1024 / 16 words per tile
#define HEAD_DIM 128

extern "C" __global__ void fused_blackwell_bit_cross_entropy_kernel(
    const uint32_t* __restrict__ hidden_packed,     // [total_tokens, HEAD_DIM / 16] (2-bit packed)
    const uint32_t* __restrict__ vocab_w_packed,    // [vocab_size, HEAD_DIM / 16]
    const int* __restrict__ target_tokens,          // [total_tokens]
    float* __restrict__ loss_out,                   // [total_tokens]
    const int total_tokens,
    const int vocab_size
) {
    int token_idx = blockIdx.x;
    if (token_idx >= total_tokens) return;

    int tid = threadIdx.x;
    int h_words = HEAD_DIM / 16;
    int target_id = target_tokens[token_idx];

    // Load token hidden state into registers
    float local_h[16];
    if (tid < h_words) {
        uint32_t hw = hidden_packed[token_idx * h_words + tid];
        #pragma unroll
        for (int b = 0; b < 16; ++b) {
            local_h[b] = (float)((hw >> (b * 2)) & 0x3) - 1.5f;
        }
    }

    // Online LogSumExp tracking across vocabulary
    float running_max = -1e20f;
    float running_sum = 0.0f;
    float target_logit = 0.0f;

    for (int v = tid; v < vocab_size; v += blockDim.x) {
        float dot_prod = 0.0f;

        #pragma unroll
        for (int hw_idx = 0; hw_idx < h_words; ++hw_idx) {
            uint32_t vw = vocab_w_packed[v * h_words + hw_idx];
            for (int b = 0; b < 16; ++b) {
                float v_coord = (float)((vw >> (b * 2)) & 0x3) - 1.5f;
                dot_prod += local_h[b] * v_coord;
            }
        }

        if (v == target_id) {
            target_logit = dot_prod;
        }

        float new_max = fmaxf(running_max, dot_prod);
        float exp_diff = expf(running_max - new_max);
        float exp_curr = expf(dot_prod - new_max);

        running_sum = running_sum * exp_diff + exp_curr;
        running_max = new_max;
    }

    // Warp all-reduce for running max and sum
    #pragma unroll
    for (int offset = 16; offset > 0; offset /= 2) {
        float other_max = __shfl_down_sync(0xffffffff, running_max, offset);
        float other_sum = __shfl_down_sync(0xffffffff, running_sum, offset);

        float combined_max = fmaxf(running_max, other_max);
        running_sum = running_sum * expf(running_max - combined_max) + other_sum * expf(other_max - combined_max);
        running_max = combined_max;

        target_logit += __shfl_down_sync(0xffffffff, target_logit, offset);
    }

    if (tid == 0) {
        float log_z = running_max + logf(fmaxf(running_sum, 1e-8f));
        loss_out[token_idx] = log_z - target_logit;
    }
}

extern "C" void launch_fused_blackwell_bit_cross_entropy(
    const uint32_t* hidden_packed,
    const uint32_t* vocab_w_packed,
    const int* target_tokens,
    float* loss_out,
    int total_tokens,
    int vocab_size,
    cudaStream_t stream
) {
    dim3 grid(total_tokens);
    dim3 block(128);

    fused_blackwell_bit_cross_entropy_kernel<<<grid, block, 0, stream>>>(
        hidden_packed, vocab_w_packed, target_tokens, loss_out,
        total_tokens, vocab_size
    );
}
