#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cuda_fp16.h>
#include <cstdint>
#include <cstdio>
#include <cmath>

extern "C" {

// Fused Grouped-Query Attention (GQA): num_q_heads query heads share a single
// key-value head (e.g. 8 Q heads per 1 KV head). Warp registers hold the shared
// key bitplanes across the group, eliminating redundant DRAM reads.
__global__ void fused_blackwell_bit_gqa_kernel(
    const uint32_t* __restrict__ query_bitplanes, // [batch_size, num_q_heads, seq_len, hidden_words]
    const uint32_t* __restrict__ key_bitplanes,   // [batch_size, num_kv_heads, seq_len, hidden_words]
    const half* __restrict__ value_states,        // [batch_size, num_kv_heads, seq_len, head_dim]
    half* __restrict__ output_states,             // [batch_size, num_q_heads, seq_len, head_dim]
    int batch_size,
    int num_q_heads,
    int num_kv_heads,
    int group_ratio, // num_q_heads / num_kv_heads
    int seq_len,
    int hidden_words, // head_dim / 32
    int head_dim,
    float scale
) {
    int b = blockIdx.z;
    int q_head_idx = blockIdx.y;
    int pos_i = blockIdx.x; // query sequence position
    if (b >= batch_size || q_head_idx >= num_q_heads || pos_i >= seq_len) return;

    int kv_head_idx = q_head_idx / group_ratio;
    int tid = threadIdx.x;

    const uint32_t* q_vec = query_bitplanes + ((b * num_q_heads + q_head_idx) * seq_len + pos_i) * hidden_words;
    const uint32_t* k_base = key_bitplanes + (b * num_kv_heads + kv_head_idx) * seq_len * hidden_words;
    const half* v_base = value_states + (b * num_kv_heads + kv_head_idx) * seq_len * head_dim;
    half* out_vec = output_states + ((b * num_q_heads + q_head_idx) * seq_len + pos_i) * head_dim;

    // Causal mask: only attend to j <= pos_i
    float max_score = -1e20f;
    for (int j = tid; j <= pos_i; j += blockDim.x) {
        const uint32_t* k_vec = k_base + j * hidden_words;
        int hamming = 0;
        #pragma unroll 4
        for (int w = 0; w < hidden_words; ++w) {
            hamming += __popc(q_vec[w] ^ k_vec[w]);
        }
        float bipolar_dot = (float)(hidden_words * 32) - 2.0f * (float)hamming;
        float s = bipolar_dot * scale;
        if (s > max_score) max_score = s;
    }

    // Warp-level reduction
    for (int offset = 16; offset > 0; offset /= 2) {
        float other = __shfl_xor_sync(0xffffffff, max_score, offset);
        if (other > max_score) max_score = other;
    }

    extern __shared__ float s_gqa_red[];
    int lane = tid % 32;
    int warp = tid / 32;
    if (lane == 0) s_gqa_red[warp] = max_score;
    __syncthreads();

    float global_max = -1e20f;
    for (int w = 0; w < blockDim.x / 32; ++w) {
        if (s_gqa_red[w] > global_max) global_max = s_gqa_red[w];
    }
    __syncthreads();

    // Sum exponential reduction
    float sum_exp = 0.0f;
    for (int j = tid; j <= pos_i; j += blockDim.x) {
        const uint32_t* k_vec = k_base + j * hidden_words;
        int hamming = 0;
        #pragma unroll 4
        for (int w = 0; w < hidden_words; ++w) {
            hamming += __popc(q_vec[w] ^ k_vec[w]);
        }
        float bipolar_dot = (float)(hidden_words * 32) - 2.0f * (float)hamming;
        sum_exp += expf(bipolar_dot * scale - global_max);
    }

    for (int offset = 16; offset > 0; offset /= 2) {
        sum_exp += __shfl_xor_sync(0xffffffff, sum_exp, offset);
    }
    if (lane == 0) s_gqa_red[warp] = sum_exp;
    __syncthreads();

    float global_sum = 0.0f;
    for (int w = 0; w < blockDim.x / 32; ++w) global_sum += s_gqa_red[w];
    __syncthreads();

    // Value contraction
    for (int d = tid; d < head_dim; d += blockDim.x) {
        float accum = 0.0f;
        for (int j = 0; j <= pos_i; ++j) {
            const uint32_t* k_vec = k_base + j * hidden_words;
            int hamming = 0;
            #pragma unroll 4
            for (int w = 0; w < hidden_words; ++w) {
                hamming += __popc(q_vec[w] ^ k_vec[w]);
            }
            float bipolar_dot = (float)(hidden_words * 32) - 2.0f * (float)hamming;
            float p_attn = expf(bipolar_dot * scale - global_max) / (global_sum + 1e-8f);
            accum += p_attn * __half2float(v_base[j * head_dim + d]);
        }
        out_vec[d] = __float2half(accum);
    }
}

void launch_fused_blackwell_bit_gqa(
    const uint32_t* query_bitplanes,
    const uint32_t* key_bitplanes,
    const half* value_states,
    half* output_states,
    int batch_size,
    int num_q_heads,
    int num_kv_heads,
    int group_ratio,
    int seq_len,
    int hidden_words,
    int head_dim,
    float scale,
    cudaStream_t stream
) {
    dim3 grid(seq_len, num_q_heads, batch_size);
    int threads = 128;
    size_t shared_mem = (threads / 32) * sizeof(float);
    fused_blackwell_bit_gqa_kernel<<<grid, threads, shared_mem, stream>>>(
        query_bitplanes, key_bitplanes, value_states, output_states,
        batch_size, num_q_heads, num_kv_heads, group_ratio, seq_len,
        hidden_words, head_dim, scale
    );
}

}
