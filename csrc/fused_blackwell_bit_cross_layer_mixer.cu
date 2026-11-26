#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <math.h>

// Fused Blackwell In-Register Bitplane Cross-Layer Residual Attention Mixer
// Fuses current layer attention outputs, skip residual connections from prior layers,
// and a learned channel gate in registers with zero intermediate global memory spills.

__device__ __forceinline__ float sigmoid_poly_fast(float x) {
    float z = fminf(fmaxf(x, -6.0f), 6.0f);
    return 0.5f + 0.197f * z - 0.004f * z * z * z;
}

extern "C" __global__ void fused_blackwell_bit_cross_layer_mixer_kernel(
    const uint32_t* __restrict__ curr_attn_packed, // [batch, seq_len, hidden_dim / 16] (2-bit packed)
    const uint32_t* __restrict__ skip_res_packed,  // [batch, seq_len, hidden_dim / 16]
    const float* __restrict__ gate_weight,         // [hidden_dim]
    const float* __restrict__ gate_bias,           // [hidden_dim]
    uint32_t* __restrict__ mixed_out_packed,       // [batch, seq_len, hidden_dim / 16]
    const int total_tokens,
    const int hidden_dim
) {
    int token_idx = blockIdx.x;
    int words_per_token = hidden_dim / 16;
    int tid = threadIdx.x;

    if (token_idx >= total_tokens || tid >= words_per_token) return;

    uint32_t curr_w = curr_attn_packed[token_idx * words_per_token + tid];
    uint32_t skip_w = skip_res_packed[token_idx * words_per_token + tid];

    uint32_t out_word = 0;

    #pragma unroll
    for (int b = 0; b < 16; ++b) {
        int d_idx = tid * 16 + b;
        float curr_v = (float)((curr_w >> (b * 2)) & 0x3) - 1.5f;
        float skip_v = (float)((skip_w >> (b * 2)) & 0x3) - 1.5f;

        // Learned channel mixing gate: alpha = sigmoid(curr_v * w + bias)
        float alpha = sigmoid_poly_fast(curr_v * gate_weight[d_idx] + gate_bias[d_idx]);

        // Convex combination with residual skip
        float mixed = alpha * curr_v + (1.0f - alpha) * skip_v;

        // Re-quantize to 2-bit packed representation {0, 1, 2, 3}
        uint32_t q = (uint32_t)fminf(fmaxf(roundf(mixed + 1.5f), 0.0f), 3.0f);
        out_word |= (q << (b * 2));
    }

    mixed_out_packed[token_idx * words_per_token + tid] = out_word;
}

extern "C" void launch_fused_blackwell_bit_cross_layer_mixer(
    const uint32_t* curr_attn_packed,
    const uint32_t* skip_res_packed,
    const float* gate_weight,
    const float* gate_bias,
    uint32_t* mixed_out_packed,
    int total_tokens,
    int hidden_dim,
    cudaStream_t stream
) {
    int words_per_token = hidden_dim / 16;
    dim3 grid(total_tokens);
    dim3 block(words_per_token > 128 ? 128 : words_per_token);

    fused_blackwell_bit_cross_layer_mixer_kernel<<<grid, block, 0, stream>>>(
        curr_attn_packed, skip_res_packed, gate_weight, gate_bias, mixed_out_packed,
        total_tokens, hidden_dim
    );
}
