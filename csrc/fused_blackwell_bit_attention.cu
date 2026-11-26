#include <cuda_runtime.h>
#include <stdint.h>
#include <math.h>

#define WARP_SIZE 32

// In-register Bitplane Multi-Head Dot-Product Attention
// Computes Q * K^T integer popcount dot product, applies in-register softmax,
// and contracts with V bitplane directly within warp registers.

__device__ __forceinline__ float warp_reduce_max(float val) {
    #pragma unroll
    for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
        val = fmaxf(val, __shfl_xor_sync(0xffffffff, val, offset));
    }
    return val;
}

__device__ __forceinline__ float warp_reduce_sum(float val) {
    #pragma unroll
    for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
        val += __shfl_xor_sync(0xffffffff, val, offset);
    }
    return val;
}

extern "C" __global__ void fused_blackwell_bit_attention_kernel(
    const uint32_t* __restrict__ q_bits,
    const uint32_t* __restrict__ k_bits,
    const uint32_t* __restrict__ v_bits,
    float* __restrict__ out_context,
    int seq_len,
    int words_per_token,
    float scale
) {
    int q_idx = blockIdx.x;
    if (q_idx >= seq_len) return;

    int lane_id = threadIdx.x % WARP_SIZE;
    int warp_id = threadIdx.x / WARP_SIZE;
    if (warp_id > 0) return; // 1 warp processes one query token across sequence

    // Each lane computes dot product with key tokens
    float score = -1e20f;
    int k_idx = lane_id;
    if (k_idx < seq_len) {
        int dot = 0;
        for (int w = 0; w < words_per_token; ++w) {
            uint32_t qw = q_bits[q_idx * words_per_token + w];
            uint32_t kw = k_bits[k_idx * words_per_token + w];
            // Ternary dot: matches (+1) minus mismatches (-1)
            dot += (__popc(qw ^ ~kw) - 16);
        }
        score = (float)dot * scale;
    }

    // In-register softmax
    float max_score = warp_reduce_max(score);
    float exp_score = (k_idx < seq_len) ? __expf(score - max_score) : 0.0f;
    float sum_exp = warp_reduce_sum(exp_score);
    float prob = (sum_exp > 1e-12f) ? (exp_score / sum_exp) : 0.0f;

    // Contract with V bitplane
    for (int w = 0; w < words_per_token; ++w) {
        float v_val = (k_idx < seq_len) ? (float)(__popc(v_bits[k_idx * words_per_token + w]) - 16) : 0.0f;
        float weighted_v = prob * v_val;
        float out_w = warp_reduce_sum(weighted_v);
        if (lane_id == 0) {
            out_context[q_idx * words_per_token + w] = out_w;
        }
    }
}
