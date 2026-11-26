#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cuda_fp16.h>
#include <cstdint>
#include <cstdio>
#include <cmath>

extern "C" {

// Fused bitplane cross-attention: computes cross-attention between packed query bitplanes
// and memory (KV) bitplanes directly in warp registers with zero HBM intermediate score buffers.
__global__ void fused_blackwell_bit_cross_attention_kernel(
    const uint32_t* __restrict__ query_bitplanes, // [batch_size, num_heads, seq_q, hidden_words]
    const uint32_t* __restrict__ key_bitplanes,   // [batch_size, num_heads, seq_kv, hidden_words]
    const half* __restrict__ value_states,        // [batch_size, num_heads, seq_kv, head_dim]
    half* __restrict__ output_states,             // [batch_size, num_heads, seq_q, head_dim]
    int batch_size,
    int num_heads,
    int seq_q,
    int seq_kv,
    int hidden_words, // head_dim / 32
    int head_dim,
    float scale
) {
    int bh = blockIdx.z; // batch_size * num_heads
    int q_idx = blockIdx.x; // seq_q
    if (bh >= batch_size * num_heads || q_idx >= seq_q) return;

    int tid = threadIdx.x;
    int warp_size = 32;

    const uint32_t* q_vec = query_bitplanes + (bh * seq_q + q_idx) * hidden_words;
    const uint32_t* k_base = key_bitplanes + bh * seq_kv * hidden_words;
    const half* v_base = value_states + bh * seq_kv * head_dim;
    half* out_vec = output_states + (bh * seq_q + q_idx) * head_dim;

    // Step 1: Compute attention scores S_{q, kv} across seq_kv
    // Each thread processes a subset of kv tokens
    float local_max = -1e20f;
    for (int kv = tid; kv < seq_kv; kv += blockDim.x) {
        const uint32_t* k_vec = k_base + kv * hidden_words;
        int hamming = 0;
        #pragma unroll 4
        for (int w = 0; w < hidden_words; ++w) {
            hamming += __popc(q_vec[w] ^ k_vec[w]);
        }
        float bipolar_dot = (float)(hidden_words * 32) - 2.0f * (float)hamming;
        float score = bipolar_dot * scale;
        if (score > local_max) local_max = score;
    }

    // Warp reduction for max
    for (int offset = warp_size / 2; offset > 0; offset /= 2) {
        float other = __shfl_xor_sync(0xffffffff, local_max, offset);
        if (other > local_max) local_max = other;
    }

    extern __shared__ float s_max[];
    int warp_id = tid / warp_size;
    int lane_id = tid % warp_size;
    if (lane_id == 0) s_max[warp_id] = local_max;
    __syncthreads();

    float global_max = -1e20f;
    int num_warps = blockDim.x / warp_size;
    for (int w = 0; w < num_warps; ++w) {
        if (s_max[w] > global_max) global_max = s_max[w];
    }
    __syncthreads();

    // Step 2: Compute softmax sum exp
    float local_sum = 0.0f;
    for (int kv = tid; kv < seq_kv; kv += blockDim.x) {
        const uint32_t* k_vec = k_base + kv * hidden_words;
        int hamming = 0;
        #pragma unroll 4
        for (int w = 0; w < hidden_words; ++w) {
            hamming += __popc(q_vec[w] ^ k_vec[w]);
        }
        float bipolar_dot = (float)(hidden_words * 32) - 2.0f * (float)hamming;
        float score = bipolar_dot * scale;
        local_sum += expf(score - global_max);
    }

    for (int offset = warp_size / 2; offset > 0; offset /= 2) {
        local_sum += __shfl_xor_sync(0xffffffff, local_sum, offset);
    }
    if (lane_id == 0) s_max[warp_id] = local_sum;
    __syncthreads();

    float global_sum = 0.0f;
    for (int w = 0; w < num_warps; ++w) global_sum += s_max[w];
    __syncthreads();

    // Step 3: Project onto value states
    for (int d = tid; d < head_dim; d += blockDim.x) {
        float accum = 0.0f;
        for (int kv = 0; kv < seq_kv; ++kv) {
            const uint32_t* k_vec = k_base + kv * hidden_words;
            int hamming = 0;
            #pragma unroll 4
            for (int w = 0; w < hidden_words; ++w) {
                hamming += __popc(q_vec[w] ^ k_vec[w]);
            }
            float bipolar_dot = (float)(hidden_words * 32) - 2.0f * (float)hamming;
            float p_attn = expf(bipolar_dot * scale - global_max) / (global_sum + 1e-8f);
            accum += p_attn * __half2float(v_base[kv * head_dim + d]);
        }
        out_vec[d] = __float2half(accum);
    }
}

void launch_fused_blackwell_bit_cross_attention(
    const uint32_t* query_bitplanes,
    const uint32_t* key_bitplanes,
    const half* value_states,
    half* output_states,
    int batch_size,
    int num_heads,
    int seq_q,
    int seq_kv,
    int hidden_words,
    int head_dim,
    float scale,
    cudaStream_t stream
) {
    dim3 grid(seq_q, 1, batch_size * num_heads);
    int threads = 128;
    size_t shared_mem = (threads / 32) * sizeof(float);
    fused_blackwell_bit_cross_attention_kernel<<<grid, threads, shared_mem, stream>>>(
        query_bitplanes, key_bitplanes, value_states, output_states,
        batch_size, num_heads, seq_q, seq_kv, hidden_words, head_dim, scale
    );
}

}
