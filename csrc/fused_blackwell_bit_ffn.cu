#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cuda_fp16.h>
#include <cstdint>
#include <cstdio>
#include <cmath>

extern "C" {

// In-register Bit-FFN: evaluates fused Gate/Up projections, SwiGLU activation,
// and Down projection using packed 32-bit bitplanes and warp-level popcounts.
__global__ void fused_blackwell_bit_ffn_kernel(
    const uint32_t* __restrict__ input_bitplanes,    // [batch_size, hidden_words]
    const uint32_t* __restrict__ w_gate_bitplanes,   // [ffn_dim, hidden_words]
    const uint32_t* __restrict__ w_up_bitplanes,     // [ffn_dim, hidden_words]
    const uint32_t* __restrict__ w_down_bitplanes,   // [hidden_dim, ffn_words]
    half* __restrict__ output_tokens,                // [batch_size, hidden_dim]
    int batch_size,
    int hidden_words, // hidden_dim / 32
    int ffn_dim,      // e.g. 4096 or 8192
    int ffn_words,    // ffn_dim / 32
    int hidden_dim
) {
    int b = blockIdx.x;
    if (b >= batch_size) return;

    int tid = threadIdx.x;
    int stride = blockDim.x;

    const uint32_t* in_vec = input_bitplanes + b * hidden_words;
    half* out_vec = output_tokens + b * hidden_dim;

    // Shared buffer for intermediate SwiGLU activations (in FP16)
    extern __shared__ half s_swiglu_activations[];

    // Phase 1: Compute Gate & Up popcount dot products -> SwiGLU activation
    for (int f = tid; f < ffn_dim; f += stride) {
        const uint32_t* gate_row = w_gate_bitplanes + f * hidden_words;
        const uint32_t* up_row = w_up_bitplanes + f * hidden_words;

        int gate_popc = 0;
        int up_popc = 0;

        #pragma unroll 4
        for (int w = 0; w < hidden_words; ++w) {
            uint32_t in_val = in_vec[w];
            gate_popc += __popc(in_val ^ gate_row[w]);
            up_popc += __popc(in_val ^ up_row[w]);
        }

        // Bipolar normalization: S = 1.0 - 2.0 * (hamming / total_bits)
        float total_bits = (float)(hidden_words * 32);
        float gate_act = 1.0f - 2.0f * ((float)gate_popc / total_bits);
        float up_act = 1.0f - 2.0f * ((float)up_popc / total_bits);

        // SiLU(gate) = gate / (1 + exp(-gate))
        float silu_gate = gate_act / (1.0f + expf(-gate_act));
        float swiglu = silu_gate * up_act;

        s_swiglu_activations[f] = __float2half(swiglu);
    }

    __syncthreads();

    // Phase 2: Compute Down projection into output_tokens
    for (int d = tid; d < hidden_dim; d += stride) {
        float accum = 0.0f;
        // Project across the ffn_dim using the swiglu activations
        for (int f = 0; f < ffn_dim; ++f) {
            int word_idx = f / 32;
            int bit_idx = f % 32;
            uint32_t down_mask = w_down_bitplanes[d * ffn_words + word_idx];
            float weight_sign = ((down_mask >> bit_idx) & 1) ? 1.0f : -1.0f;
            accum += __half2float(s_swiglu_activations[f]) * weight_sign;
        }
        out_vec[d] = __float2half(accum * 0.015625f); // Scale factor 1/sqrt(hidden)
    }
}

void launch_fused_blackwell_bit_ffn(
    const uint32_t* input_bitplanes,
    const uint32_t* w_gate_bitplanes,
    const uint32_t* w_up_bitplanes,
    const uint32_t* w_down_bitplanes,
    half* output_tokens,
    int batch_size,
    int hidden_words,
    int ffn_dim,
    int ffn_words,
    int hidden_dim,
    cudaStream_t stream
) {
    size_t shared_mem = ffn_dim * sizeof(half);
    int threads = 256;
    fused_blackwell_bit_ffn_kernel<<<batch_size, threads, shared_mem, stream>>>(
        input_bitplanes, w_gate_bitplanes, w_up_bitplanes, w_down_bitplanes,
        output_tokens, batch_size, hidden_words, ffn_dim, ffn_words, hidden_dim
    );
}

}
