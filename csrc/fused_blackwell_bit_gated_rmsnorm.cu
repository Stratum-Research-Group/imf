#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <math.h>

// Fused Blackwell In-Register Bitplane RMSNorm with Learned Geometric Residual Gate
// Fuses residual connection, root-mean-square normalization, learned channel-wise geometric gate,
// and 2-bit quantization directly in warp registers with zero intermediate global memory spills.

#define WARP_SIZE 32

__device__ __forceinline__ float sigmoid_poly_fast(float x) {
    float z = fminf(fmaxf(x, -6.0f), 6.0f);
    return 0.5f + 0.197f * z - 0.004f * z * z * z;
}

extern "C" __global__ void fused_blackwell_bit_gated_rmsnorm_kernel(
    const uint32_t* __restrict__ x_packed,        // [total_tokens, hidden_dim / 16] (2-bit packed)
    const uint32_t* __restrict__ residual_packed, // [total_tokens, hidden_dim / 16]
    const float* __restrict__ weight_gamma,       // [hidden_dim]
    const float* __restrict__ gate_bias,          // [hidden_dim]
    uint32_t* __restrict__ out_packed,            // [total_tokens, hidden_dim / 16]
    const float eps,
    const int total_tokens,
    const int hidden_dim
) {
    int token_idx = blockIdx.x;
    int words_per_token = hidden_dim / 16;
    int tid = threadIdx.x;

    if (token_idx >= total_tokens) return;

    // Phase 1: Load inputs, add residual in registers, and compute local sum of squares
    float local_sum_sq = 0.0f;
    float reg_vals[16] = {0.0f};

    if (tid < words_per_token) {
        uint32_t xw = x_packed[token_idx * words_per_token + tid];
        uint32_t rw = residual_packed[token_idx * words_per_token + tid];

        #pragma unroll
        for (int b = 0; b < 16; ++b) {
            float xv = (float)((xw >> (b * 2)) & 0x3) - 1.5f;
            float rv = (float)((rw >> (b * 2)) & 0x3) - 1.5f;
            float sum_val = xv + rv;
            reg_vals[b] = sum_val;
            local_sum_sq += sum_val * sum_val;
        }
    }

    // Warp all-reduce for sum of squares
    #pragma unroll
    for (int offset = 16; offset > 0; offset /= 2) {
        local_sum_sq += __shfl_down_sync(0xffffffff, local_sum_sq, offset);
    }
    float total_sum_sq = __shfl_sync(0xffffffff, local_sum_sq, 0);

    float rms_scale = rsqrtf(total_sum_sq / (float)hidden_dim + eps);

    // Phase 2: Apply scale, learned weight gamma, geometric sigmoid gate, and requantize
    if (tid < words_per_token) {
        uint32_t out_word = 0;

        #pragma unroll
        for (int b = 0; b < 16; ++b) {
            int d_idx = tid * 16 + b;
            float norm_val = reg_vals[b] * rms_scale * weight_gamma[d_idx];
            float gate = sigmoid_poly_fast(norm_val + gate_bias[d_idx]);
            float gated_val = norm_val * gate;

            // Re-quantize to 2-bit packed representation {0, 1, 2, 3}
            uint32_t q = (uint32_t)fminf(fmaxf(roundf(gated_val + 1.5f), 0.0f), 3.0f);
            out_word |= (q << (b * 2));
        }

        out_packed[token_idx * words_per_token + tid] = out_word;
    }
}

extern "C" void launch_fused_blackwell_bit_gated_rmsnorm(
    const uint32_t* x_packed,
    const uint32_t* residual_packed,
    const float* weight_gamma,
    const float* gate_bias,
    uint32_t* out_packed,
    float eps,
    int total_tokens,
    int hidden_dim,
    cudaStream_t stream
) {
    int words_per_token = hidden_dim / 16;
    dim3 grid(total_tokens);
    dim3 block(words_per_token > 32 ? words_per_token : 32);

    fused_blackwell_bit_gated_rmsnorm_kernel<<<grid, block, 0, stream>>>(
        x_packed, residual_packed, weight_gamma, gate_bias, out_packed,
        eps, total_tokens, hidden_dim
    );
}
