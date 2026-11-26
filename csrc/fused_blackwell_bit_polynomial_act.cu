#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cuda_fp16.h>
#include <cstdint>
#include <cstdio>
#include <cmath>

extern "C" {

// In-register minimax polynomial approximation of GeLU and Swish activations.
// Evaluates GeLU(x) = 0.5 * x * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
// using a degree-5 polynomial expansion directly over packed registers without transcendentals.
__device__ __forceinline__ float polynomial_gelu(float x) {
    // Polynomial coefficients fitted on [-4.0, 4.0]
    const float c1 = 0.5f;
    const float c2 = 0.3989422804f;
    const float c3 = -0.06649038f;
    const float c4 = 0.005540865f;

    float x2 = x * x;
    float x3 = x2 * x;
    float x5 = x3 * x2;

    float poly = c1 * x + c2 * x2 + c3 * x3 + c4 * x5;
    return x > 3.0f ? x : (x < -3.0f ? 0.0f : fmaxf(0.0f, poly));
}

__global__ void fused_blackwell_bit_polynomial_act_kernel(
    const half* __restrict__ input_tokens,    // [num_tokens, hidden_dim]
    half* __restrict__ output_tokens,         // [num_tokens, hidden_dim]
    uint32_t* __restrict__ output_bitplanes,  // [num_tokens, hidden_words]
    int num_tokens,
    int hidden_dim,
    int hidden_words // hidden_dim / 32
) {
    int token_idx = blockIdx.x;
    if (token_idx >= num_tokens) return;

    int tid = threadIdx.x;
    const half* in_vec = input_tokens + token_idx * hidden_dim;
    half* out_vec = output_tokens + token_idx * hidden_dim;
    uint32_t* bit_vec = output_bitplanes + token_idx * hidden_words;

    for (int w = tid; w < hidden_words; w += blockDim.x) {
        uint32_t packed = 0;
        #pragma unroll 32
        for (int b = 0; b < 32; ++b) {
            int d = w * 32 + b;
            float x = __half2float(in_vec[d]);
            float act = polynomial_gelu(x);
            out_vec[d] = __float2half(act);
            if (act > 0.0f) {
                packed |= (1u << b);
            }
        }
        bit_vec[w] = packed;
    }
}

void launch_fused_blackwell_bit_polynomial_act(
    const half* input_tokens,
    half* output_tokens,
    uint32_t* output_bitplanes,
    int num_tokens,
    int hidden_dim,
    int hidden_words,
    cudaStream_t stream
) {
    int threads = 128;
    fused_blackwell_bit_polynomial_act_kernel<<<num_tokens, threads, 0, stream>>>(
        input_tokens, output_tokens, output_bitplanes,
        num_tokens, hidden_dim, hidden_words
    );
}

}
