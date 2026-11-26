#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cuda_fp16.h>
#include <cstdint>
#include <cstdio>
#include <cmath>

extern "C" {

// Fused bitplane sliding-window attention: enforces causal boundary |i - j| <= window_size
// entirely within warp registers using single-cycle __popc contractions.
__global__ void fused_blackwell_bit_sliding_window_attention_kernel(
    const uint32_t* __restrict__ query_bitplanes, // [batch_size, num_heads, seq_len, hidden_words]
    const uint32_t* __restrict__ key_bitplanes,   // [batch_size, num_heads, seq_len, hidden_words]
    const half* __restrict__ value_states,        // [batch_size, num_heads, seq_len, head_dim]
    half* __restrict__ output_states,             // [batch_size, num_heads, seq_len, head_dim]
    int batch_size,
    int num_heads,
    int seq_len,
    int window_size, // e.g. 512 or 1024
    int hidden_words, // head_dim / 32
    int head_dim,
    float scale
) {
    int bh = blockIdx.z; // batch_size * num_heads
    int pos_i = blockIdx.x; // query sequence position
    if (bh >= batch_size * num_heads || pos_i >= seq_len) return;

    int tid = threadIdx.x;

    // Window bounds for causal sliding attention: max(0, pos_i - window_size) <= j <= pos_i
    int start_j = pos_i > window_size ? pos_i - window_size : 0;
    int end_j = pos_i;

    const uint32_t* q_vec = query_bitplanes + (bh * seq_len + pos_i) * hidden_words;
    const uint32_t* k_base = key_bitplanes + bh * seq_len * hidden_words;
    const half* v_base = value_states + bh * seq_len * head_dim;
    half* out_vec = output_states + (bh * seq_len + pos_i) * head_dim;

    float local_max = -1e20f;
    for (int j = start_j + tid; j <= end_j; j += blockDim.x) {
        const uint32_t* k_vec = k_base + j * hidden_words;
        int hamming = 0;
        #pragma unroll 4
        for (int w = 0; w < hidden_words; ++w) {
            hamming += __popc(q_vec[w] ^ k_vec[w]);
        }
        float bipolar_dot = (float)(hidden_words * 32) - 2.0f * (float)hamming;
        float score = bipolar_dot * scale;
        if (score > local_max) local_max = score;
    }

    // Warp-level reduction
    for (int offset = 16; offset > 0; offset /= 2) {
        float other = __shfl_xor_sync(0xffffffff, local_max, offset);
        if (other > local_max) local_max = other;
    }

    extern __shared__ float s_swa_red[];
    int lane = tid % 32;
    int warp = tid / 32;
    if (lane == 0) s_swa_red[warp] = local_max;
    __syncthreads();

    float global_max = -1e20f;
    for (int w = 0; w < blockDim.x / 32; ++w) {
        if (s_swa_red[w] > global_max) global_max = s_swa_red[w];
    }
    __syncthreads();

    // Sum exp reduction within sliding window
    float local_sum = 0.0f;
    for (int j = start_j + tid; j <= end_j; j += blockDim.x) {
        const uint32_t* k_vec = k_base + j * hidden_words;
        int hamming = 0;
        #pragma unroll 4
        for (int w = 0; w < hidden_words; ++w) {
            hamming += __popc(q_vec[w] ^ k_vec[w]);
        }
        float bipolar_dot = (float)(hidden_words * 32) - 2.0f * (float)hamming;
        local_sum += expf(bipolar_dot * scale - global_max);
    }

    for (int offset = 16; offset > 0; offset /= 2) {
        local_sum += __shfl_xor_sync(0xffffffff, local_sum, offset);
    }
    if (lane == 0) s_swa_red[warp] = local_sum;
    __syncthreads();

    float global_sum = 0.0f;
    for (int w = 0; w < blockDim.x / 32; ++w) global_sum += s_swa_red[w];
    __syncthreads();

    // Value contraction directly into output
    for (int d = tid; d < head_dim; d += blockDim.x) {
        float accum = 0.0f;
        for (int j = start_j; j <= end_j; ++j) {
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

void launch_fused_blackwell_bit_sliding_window_attention(
    const uint32_t* query_bitplanes,
    const uint32_t* key_bitplanes,
    const half* value_states,
    half* output_states,
    int batch_size,
    int num_heads,
    int seq_len,
    int window_size,
    int hidden_words,
    int head_dim,
    float scale,
    cudaStream_t stream
) {
    dim3 grid(seq_len, 1, batch_size * num_heads);
    int threads = 128;
    size_t shared_mem = (threads / 32) * sizeof(float);
    fused_blackwell_bit_sliding_window_attention_kernel<<<grid, threads, shared_mem, stream>>>(
        query_bitplanes, key_bitplanes, value_states, output_states,
        batch_size, num_heads, seq_len, window_size, hidden_words, head_dim, scale
    );
}

}
