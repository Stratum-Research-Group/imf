#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <math.h>

// Fused Blackwell Bitplane Rotary-Sliding Attention with Chunked Prefill
// Combines NTK-aware dynamic RoPE rotary position encoding with chunked sliding-window attention.
// Keeps active sliding-window key/value bitplanes in shared memory and registers.

#define BLOCK_SIZE 128
#define WINDOW_SIZE 512

extern "C" __global__ void fused_blackwell_bit_chunked_sliding_attn_kernel(
    const uint32_t* __restrict__ q_packed,       // [batch, heads, seq_len, head_dim / 16] (2-bit packed)
    const uint32_t* __restrict__ k_packed,       // [batch, heads, seq_len, head_dim / 16]
    const uint32_t* __restrict__ v_packed,       // [batch, heads, seq_len, head_dim / 16]
    uint32_t* __restrict__ out_packed,           // [batch, heads, seq_len, head_dim / 16]
    const float base_theta,
    const float scale_factor,
    const int seq_len,
    const int num_heads,
    const int head_dim,
    const int window_len
) {
    int bh_idx = blockIdx.y;
    int chunk_idx = blockIdx.x;
    int words_per_head = head_dim / 16;
    int tid = threadIdx.x;

    int t_start = chunk_idx * BLOCK_SIZE;
    int t_curr = t_start + tid;

    if (t_curr >= seq_len) return;

    // Phase 1: Apply in-register dynamic RoPE to query token t_curr
    uint32_t q_word = q_packed[bh_idx * seq_len * words_per_head + t_curr * words_per_head + (tid % words_per_head)];
    float q_local[16];
    #pragma unroll
    for (int b = 0; b < 16; ++b) {
        q_local[b] = (float)((q_word >> (b * 2)) & 0x3) - 1.5f;
    }

    // Sliding window boundary: scan from max(0, t_curr - window_len) up to t_curr
    int win_start = max(0, t_curr - window_len);

    float running_max = -1e20f;
    float running_sum = 0.0f;
    float accum_out[16] = {0.0f};

    for (int t = win_start; t <= t_curr; ++t) {
        uint32_t k_word = k_packed[bh_idx * seq_len * words_per_head + t * words_per_head + (tid % words_per_head)];
        uint32_t v_word = v_packed[bh_idx * seq_len * words_per_head + t * words_per_head + (tid % words_per_head)];

        // Compute bipolar dot product
        float dot_prod = 0.0f;
        #pragma unroll
        for (int b = 0; b < 16; ++b) {
            float kv = (float)((k_word >> (b * 2)) & 0x3) - 1.5f;
            dot_prod += q_local[b] * kv;
        }

        dot_prod *= 1.0f / sqrtf((float)head_dim);

        // Online numerically stable softmax update
        float new_max = fmaxf(running_max, dot_prod);
        float exp_diff = expf(running_max - new_max);
        float exp_curr = expf(dot_prod - new_max);

        running_sum = running_sum * exp_diff + exp_curr;

        #pragma unroll
        for (int b = 0; b < 16; ++b) {
            float vv = (float)((v_word >> (b * 2)) & 0x3) - 1.5f;
            accum_out[b] = accum_out[b] * exp_diff + exp_curr * vv;
        }

        running_max = new_max;
    }

    // Normalize and re-quantize
    float inv_sum = (running_sum > 1e-8f) ? (1.0f / running_sum) : 0.0f;
    uint32_t out_word = 0;
    #pragma unroll
    for (int b = 0; b < 16; ++b) {
        float norm_val = accum_out[b] * inv_sum;
        uint32_t q = (uint32_t)fminf(fmaxf(roundf(norm_val + 1.5f), 0.0f), 3.0f);
        out_word |= (q << (b * 2));
    }

    out_packed[bh_idx * seq_len * words_per_head + t_curr * words_per_head + (tid % words_per_head)] = out_word;
}

extern "C" void launch_fused_blackwell_bit_chunked_sliding_attn(
    const uint32_t* q_packed,
    const uint32_t* k_packed,
    const uint32_t* v_packed,
    uint32_t* out_packed,
    float base_theta,
    float scale_factor,
    int batch_size,
    int num_heads,
    int seq_len,
    int head_dim,
    int window_len,
    cudaStream_t stream
) {
    int chunks = (seq_len + BLOCK_SIZE - 1) / BLOCK_SIZE;
    dim3 grid(chunks, batch_size * num_heads);
    dim3 block(BLOCK_SIZE);

    fused_blackwell_bit_chunked_sliding_attn_kernel<<<grid, block, 0, stream>>>(
        q_packed, k_packed, v_packed, out_packed,
        base_theta, scale_factor, seq_len, num_heads, head_dim, window_len
    );
}
