#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cuda_fp16.h>
#include <cstdint>
#include <cstdio>
#include <cmath>

#define WARP_SIZE 32

extern "C" {

__device__ __forceinline__ float warp_sum(float val) {
    #pragma unroll
    for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
        val += __shfl_xor_sync(0xffffffff, val, offset);
    }
    return val;
}

// In-register fused residual addition, RMSNorm, and bitplane re-quantization.
// Inputs: incoming FP16 tokens, residual FP16 tokens, scaling weight gamma.
// Outputs: normalized FP16 tokens, and packed 32-bit re-quantized bitplanes for subsequent layers.
__global__ void fused_blackwell_bit_residual_rmsnorm_quant_kernel(
    const half* __restrict__ input_tokens,    // [num_tokens, hidden_dim]
    const half* __restrict__ residual_tokens, // [num_tokens, hidden_dim]
    const half* __restrict__ gamma_scale,     // [hidden_dim]
    half* __restrict__ output_tokens,         // [num_tokens, hidden_dim]
    uint32_t* __restrict__ output_bitplanes,  // [num_tokens, hidden_words]
    int num_tokens,
    int hidden_dim,
    int hidden_words, // hidden_dim / 32
    float epsilon
) {
    int token_idx = blockIdx.x;
    if (token_idx >= num_tokens) return;

    int tid = threadIdx.x;
    const half* in_ptr = input_tokens + token_idx * hidden_dim;
    const half* res_ptr = residual_tokens + token_idx * hidden_dim;
    half* out_ptr = output_tokens + token_idx * hidden_dim;
    uint32_t* bit_ptr = output_bitplanes + token_idx * hidden_words;

    // Phase 1: Local sum of squares calculation
    float local_sq = 0.0f;
    for (int d = tid; d < hidden_dim; d += blockDim.x) {
        float x = __half2float(in_ptr[d]) + __half2float(res_ptr[d]);
        local_sq += x * x;
    }

    // Warp-level sum of squares
    local_sq = warp_sum(local_sq);

    extern __shared__ float s_sq[];
    int lane = tid % WARP_SIZE;
    int warp = tid / WARP_SIZE;
    if (lane == 0) s_sq[warp] = local_sq;
    __syncthreads();

    float total_sq = 0.0f;
    for (int w = 0; w < blockDim.x / WARP_SIZE; ++w) {
        total_sq += s_sq[w];
    }
    float rms = rsqrtf((total_sq / (float)hidden_dim) + epsilon);
    __syncthreads();

    // Phase 2: RMS normalization, gamma scaling, and sign-bit extraction
    for (int w = tid; w < hidden_words; w += blockDim.x) {
        uint32_t packed = 0;
        #pragma unroll 32
        for (int b = 0; b < 32; ++b) {
            int d = w * 32 + b;
            float x = (__half2float(in_ptr[d]) + __half2float(res_ptr[d])) * rms;
            float normed = x * __half2float(gamma_scale[d]);
            out_ptr[d] = __float2half(normed);
            if (normed >= 0.0f) {
                packed |= (1u << b);
            }
        }
        bit_ptr[w] = packed;
    }
}

void launch_fused_blackwell_bit_residual_rmsnorm_quant(
    const half* input_tokens,
    const half* residual_tokens,
    const half* gamma_scale,
    half* output_tokens,
    uint32_t* output_bitplanes,
    int num_tokens,
    int hidden_dim,
    int hidden_words,
    float epsilon,
    cudaStream_t stream
) {
    int threads = 128;
    size_t shared_mem = (threads / 32) * sizeof(float);
    fused_blackwell_bit_residual_rmsnorm_quant_kernel<<<num_tokens, threads, shared_mem, stream>>>(
        input_tokens, residual_tokens, gamma_scale, output_tokens, output_bitplanes,
        num_tokens, hidden_dim, hidden_words, epsilon
    );
}

}
