#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cuda_fp16.h>
#include <cstdint>
#include <cstdio>

extern "C" {

// Fused speculative decoding verification kernel: verifies draft token bitplane sequences
// against target model distribution logit bitplanes in warp registers.
__global__ void fused_blackwell_bit_speculative_verify_kernel(
    const int* __restrict__ draft_tokens,           // [batch_size, num_draft]
    const uint32_t* __restrict__ target_logit_bits, // [batch_size, num_draft, vocab_words]
    const float* __restrict__ uniform_samples,      // [batch_size, num_draft]
    int* __restrict__ num_accepted_tokens,          // [batch_size]
    int* __restrict__ verified_tokens,              // [batch_size, num_draft + 1]
    int batch_size,
    int num_draft,
    int vocab_words // vocab_size / 32
) {
    int b = blockIdx.x;
    if (b >= batch_size) return;

    int tid = threadIdx.x;
    if (tid != 0) return; // Single-thread verification coordinator per batch item

    int accepted = 0;
    for (int k = 0; k < num_draft; ++k) {
        int token = draft_tokens[b * num_draft + k];
        int word_idx = token / 32;
        int bit_idx = token % 32;

        uint32_t bit_word = target_logit_bits[(b * num_draft + k) * vocab_words + word_idx];
        bool is_valid = (bit_word >> bit_idx) & 1;

        // Rejection sampling check against uniform sample
        float u = uniform_samples[b * num_draft + k];
        if (is_valid && u < 0.95f) {
            verified_tokens[b * (num_draft + 1) + accepted] = token;
            accepted++;
        } else {
            // Rejection encountered: break speculative chain
            break;
        }
    }

    num_accepted_tokens[b] = accepted;
}

void launch_fused_blackwell_bit_speculative_verify(
    const int* draft_tokens,
    const uint32_t* target_logit_bits,
    const float* uniform_samples,
    int* num_accepted_tokens,
    int* verified_tokens,
    int batch_size,
    int num_draft,
    int vocab_words,
    cudaStream_t stream
) {
    fused_blackwell_bit_speculative_verify_kernel<<<batch_size, 32, 0, stream>>>(
        draft_tokens, target_logit_bits, uniform_samples,
        num_accepted_tokens, verified_tokens,
        batch_size, num_draft, vocab_words
    );
}

}
