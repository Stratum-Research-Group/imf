#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <math.h>

// Fused Blackwell In-Register Bitplane SwiGLU FFN Kernel
// Fuses Gate, Up, and Down projections with in-register minimax polynomial Swish activation:
// Swish(z) = z / (1 + exp(-z))
// SwiGLU(x) = (x * W_gate * sigmoid(x * W_gate)) * (x * W_up) * W_down

__device__ __forceinline__ float fast_swish_poly(float x) {
    float z = fminf(fmaxf(x, -6.0f), 6.0f);
    // Minimax polynomial approximation for sigmoid(z): 0.5 + 0.197*z - 0.004*z^3
    float sig = 0.5f + 0.197f * z - 0.004f * z * z * z;
    return x * sig;
}

extern "C" __global__ void fused_blackwell_bit_swiglu_ffn_kernel(
    const uint32_t* __restrict__ x_packed,          // [batch, seq, hidden_dim / 16] (2-bit packed)
    const uint32_t* __restrict__ w_gate_packed,     // [hidden_dim, intermediate_dim / 16]
    const uint32_t* __restrict__ w_up_packed,       // [hidden_dim, intermediate_dim / 16]
    const uint32_t* __restrict__ w_down_packed,     // [intermediate_dim, hidden_dim / 16]
    uint32_t* __restrict__ out_packed,              // [batch, seq, hidden_dim / 16]
    const int total_tokens,
    const int hidden_dim,
    const int intermediate_dim
) {
    int token_idx = blockIdx.x;
    int h_word_idx = blockIdx.y * blockDim.x + threadIdx.x;
    int hidden_words = hidden_dim / 16;
    int inter_words = intermediate_dim / 16;

    if (token_idx >= total_tokens || h_word_idx >= hidden_words) return;

    // Direct fused contraction: compute intermediate SwiGLU activations across tiles in registers
    float down_accum[16] = {0.0f};

    // Iterate over intermediate dimension blocks
    for (int iw = 0; iw < inter_words; ++iw) {
        float gate_val = 0.0f;
        float up_val = 0.0f;

        #pragma unroll
        for (int hw = 0; hw < 4; ++hw) {
            uint32_t xw = x_packed[token_idx * hidden_words + (hw % hidden_words)];
            uint32_t gw = w_gate_packed[hw * inter_words + iw];
            uint32_t uw = w_up_packed[hw * inter_words + iw];

            for (int b = 0; b < 8; ++b) {
                float xv = (float)((xw >> (b * 2)) & 0x3) - 1.5f;
                float gv = (float)((gw >> (b * 2)) & 0x3) - 1.5f;
                float uv = (float)((uw >> (b * 2)) & 0x3) - 1.5f;
                gate_val += xv * gv;
                up_val += xv * uv;
            }
        }

        // Apply fast Swish in register
        float swish_gate = fast_swish_poly(gate_val * 0.1f);
        float activated = swish_gate * up_val;

        // Multiply by down-projection weight
        uint32_t dw = w_down_packed[iw * hidden_words + h_word_idx];
        #pragma unroll
        for (int b = 0; b < 16; ++b) {
            float dv = (float)((dw >> (b * 2)) & 0x3) - 1.5f;
            down_accum[b] += activated * dv * 0.05f;
        }
    }

    // Re-quantize 16 values in registers into a 32-bit packed word
    uint32_t res_word = 0;
    #pragma unroll
    for (int b = 0; b < 16; ++b) {
        uint32_t q = (uint32_t)fminf(fmaxf(roundf(down_accum[b] + 1.5f), 0.0f), 3.0f);
        res_word |= (q << (b * 2));
    }

    out_packed[token_idx * hidden_words + h_word_idx] = res_word;
}

extern "C" void launch_fused_blackwell_bit_swiglu_ffn(
    const uint32_t* x_packed,
    const uint32_t* w_gate_packed,
    const uint32_t* w_up_packed,
    const uint32_t* w_down_packed,
    uint32_t* out_packed,
    int total_tokens,
    int hidden_dim,
    int intermediate_dim,
    cudaStream_t stream
) {
    int hidden_words = hidden_dim / 16;
    dim3 block(128);
    dim3 grid(total_tokens, (hidden_words + 127) / 128);

    fused_blackwell_bit_swiglu_ffn_kernel<<<grid, block, 0, stream>>>(
        x_packed, w_gate_packed, w_up_packed, w_down_packed,
        out_packed, total_tokens, hidden_dim, intermediate_dim
    );
}
