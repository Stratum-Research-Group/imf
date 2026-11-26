#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <math.h>

// Fused Blackwell In-Register Bitplane Grouped-Query Attention with LogSumExp
// Executes GQA directly over packed 2-bit tensors in registers, tracking online running maximum
// and LogSumExp normalization without global memory spills.

#define WARP_SIZE 32

extern "C" __global__ void fused_blackwell_bit_gqa_logsumexp_kernel(
    const uint32_t* __restrict__ q_packed,       // [batch, num_q_heads, seq_len, head_dim / 16] (2-bit packed)
    const uint32_t* __restrict__ k_packed,       // [batch, num_kv_heads, seq_len, head_dim / 16]
    const uint32_t* __restrict__ v_packed,       // [batch, num_kv_heads, seq_len, head_dim / 16]
    uint32_t* __restrict__ out_packed,           // [batch, num_q_heads, seq_len, head_dim / 16]
    float* __restrict__ logsumexp_out,           // [batch, num_q_heads, seq_len]
    const int seq_len,
    const int num_q_heads,
    const int num_kv_heads,
    const int head_dim
) {
    int q_head_idx = blockIdx.y;
    int token_idx = blockIdx.x;
    int batch_idx = blockIdx.z;

    if (token_idx >= seq_len || q_head_idx >= num_q_heads) return;

    int words_per_head = head_dim / 16;
    int group_size = num_q_heads / num_kv_heads;
    int kv_head_idx = q_head_idx / group_size;

    int tid = threadIdx.x;
    if (tid >= words_per_head) return;

    // Load query packed word for this thread
    uint32_t q_word = q_packed[batch_idx * (num_q_heads * seq_len * words_per_head) +
                               q_head_idx * (seq_len * words_per_head) +
                               token_idx * words_per_head + tid];

    float local_q[16];
    #pragma unroll
    for (int b = 0; b < 16; ++b) {
        local_q[b] = (float)((q_word >> (b * 2)) & 0x3) - 1.5f;
    }

    float running_max = -1e20f;
    float running_sum = 0.0f;
    float accum_out[16] = {0.0f};

    // Scan causally over keys up to token_idx
    for (int t = 0; t <= token_idx; ++t) {
        uint32_t k_word = k_packed[batch_idx * (num_kv_heads * seq_len * words_per_head) +
                                   kv_head_idx * (seq_len * words_per_head) +
                                   t * words_per_head + tid];

        float dot_prod = 0.0f;
        #pragma unroll
        for (int b = 0; b < 16; ++b) {
            float kv = (float)((k_word >> (b * 2)) & 0x3) - 1.5f;
            dot_prod += local_q[b] * kv;
        }

        // Warp all-reduce dot product across head dimension words
        #pragma unroll
        for (int offset = 16; offset > 0; offset /= 2) {
            dot_prod += __shfl_down_sync(0xffffffff, dot_prod, offset);
        }
        dot_prod = __shfl_sync(0xffffffff, dot_prod, 0);

        dot_prod *= 1.0f / sqrtf((float)head_dim);

        // Numerically stable online LogSumExp update
        float new_max = fmaxf(running_max, dot_prod);
        float exp_diff = expf(running_max - new_max);
        float exp_curr = expf(dot_prod - new_max);

        running_sum = running_sum * exp_diff + exp_curr;

        // Update running output accumulator
        uint32_t v_word = v_packed[batch_idx * (num_kv_heads * seq_len * words_per_head) +
                                   kv_head_idx * (seq_len * words_per_head) +
                                   t * words_per_head + tid];

        #pragma unroll
        for (int b = 0; b < 16; ++b) {
            float vv = (float)((v_word >> (b * 2)) & 0x3) - 1.5f;
            accum_out[b] = accum_out[b] * exp_diff + exp_curr * vv;
        }

        running_max = new_max;
    }

    // Normalize by running_sum and re-quantize to 2-bit packed word
    float inv_sum = (running_sum > 1e-8f) ? (1.0f / running_sum) : 0.0f;
    uint32_t out_word = 0;
    #pragma unroll
    for (int b = 0; b < 16; ++b) {
        float norm_val = accum_out[b] * inv_sum;
        uint32_t q = (uint32_t)fminf(fmaxf(roundf(norm_val + 1.5f), 0.0f), 3.0f);
        out_word |= (q << (b * 2));
    }

    out_packed[batch_idx * (num_q_heads * seq_len * words_per_head) +
               q_head_idx * (seq_len * words_per_head) +
               token_idx * words_per_head + tid] = out_word;

    if (tid == 0) {
        logsumexp_out[batch_idx * (num_q_heads * seq_len) + q_head_idx * seq_len + token_idx] =
            running_max + logf(fmaxf(running_sum, 1e-8f));
    }
}

extern "C" void launch_fused_blackwell_bit_gqa_logsumexp(
    const uint32_t* q_packed,
    const uint32_t* k_packed,
    const uint32_t* v_packed,
    uint32_t* out_packed,
    float* logsumexp_out,
    int batch_size,
    int seq_len,
    int num_q_heads,
    int num_kv_heads,
    int head_dim,
    cudaStream_t stream
) {
    int words_per_head = head_dim / 16;
    dim3 grid(seq_len, num_q_heads, batch_size);
    dim3 block(words_per_head);

    fused_blackwell_bit_gqa_logsumexp_kernel<<<grid, block, 0, stream>>>(
        q_packed, k_packed, v_packed, out_packed, logsumexp_out,
        seq_len, num_q_heads, num_kv_heads, head_dim
    );
}
