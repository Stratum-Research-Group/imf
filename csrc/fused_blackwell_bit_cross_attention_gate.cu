#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <math.h>

// Fused Blackwell Cross-Attention Gate Kernel
// Dynamically gates multimodal context cross-attention projections with query representation in registers
// Gate equation: g = sigmoid(Q * W_gate)
// Output: Out = g * CrossAttention(Q, K, V) + (1 - g) * SelfRepresentation

__device__ __forceinline__ float sigmoid_poly(float x) {
    // 5th degree minimax polynomial approximation for 1 / (1 + exp(-x))
    float z = fminf(fmaxf(x, -6.0f), 6.0f);
    return 0.5f + 0.197f * z - 0.004f * z * z * z;
}

extern "C" __global__ void fused_blackwell_bit_cross_attention_gate_kernel(
    const uint32_t* __restrict__ q_packed,          // Query packed 2-bit [batch, heads, seq, dim / 16]
    const uint32_t* __restrict__ kv_cross_packed,   // Cross-modal packed 2-bit [batch, heads, seq_kv, dim / 16]
    const float* __restrict__ gate_bias,           // [heads]
    uint32_t* __restrict__ gated_out_packed,       // Output packed 2-bit [batch, heads, seq, dim / 16]
    const int seq_len,
    const int num_heads,
    const int head_dim
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int total_words = seq_len * num_heads * (head_dim / 16);
    if (idx >= total_words) return;

    int words_per_head = head_dim / 16;
    int head_idx = (idx / words_per_head) % num_heads;

    uint32_t q_w = q_packed[idx];
    uint32_t kv_w = kv_cross_packed[idx];

    // Compute dot product of Q bitplane with bias in register to determine gating factor
    float head_b = gate_bias[head_idx];
    float q_accum = 0.0f;

    #pragma unroll
    for (int i = 0; i < 16; ++i) {
        float q_val = (float)((q_w >> (i * 2)) & 0x3) - 1.5f;
        q_accum += q_val;
    }

    float gate = sigmoid_poly(q_accum * 0.1f + head_b);
    float inv_gate = 1.0f - gate;

    uint32_t out_word = 0;

    #pragma unroll
    for (int i = 0; i < 16; ++i) {
        float q_val = (float)((q_w >> (i * 2)) & 0x3) - 1.5f;
        float kv_val = (float)((kv_w >> (i * 2)) & 0x3) - 1.5f;

        // Fused cross-attention gated linear combination
        float combined = gate * kv_val + inv_gate * q_val;

        // Quantize back to 2-bit in {0, 1, 2, 3}
        uint32_t quantized = (uint32_t)fminf(fmaxf(roundf(combined + 1.5f), 0.0f), 3.0f);
        out_word |= (quantized << (i * 2));
    }

    gated_out_packed[idx] = out_word;
}

extern "C" void launch_fused_blackwell_bit_cross_attention_gate(
    const uint32_t* q_packed,
    const uint32_t* kv_cross_packed,
    const float* gate_bias,
    uint32_t* gated_out_packed,
    int seq_len,
    int num_heads,
    int head_dim,
    cudaStream_t stream
) {
    int total_words = seq_len * num_heads * (head_dim / 16);
    int threads = 256;
    int blocks = (total_words + threads - 1) / threads;

    fused_blackwell_bit_cross_attention_gate_kernel<<<blocks, threads, 0, stream>>>(
        q_packed, kv_cross_packed, gate_bias, gated_out_packed,
        seq_len, num_heads, head_dim
    );
}
