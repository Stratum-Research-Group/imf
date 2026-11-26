#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cuda_fp16.h>
#include <cstdint>
#include <cstdio>

extern "C" {

// Fused in-place KV cache 1-bit quantization kernel:
// Extracts the sign-bit of incoming FP16 KV states into packed 32-bit words,
// reducing KV cache footprint by 16x in GDDR7 memory.
__global__ void fused_blackwell_bit_kv_quantize_kernel(
    const half* __restrict__ fp16_kv,         // [batch_size, num_heads, seq_len, head_dim]
    uint32_t* __restrict__ packed_bitplanes, // [batch_size, num_heads, seq_len, hidden_words]
    int total_tokens,
    int head_dim,
    int hidden_words // head_dim / 32
) {
    int token_idx = blockIdx.x;
    if (token_idx >= total_tokens) return;

    int tid = threadIdx.x;
    if (tid >= hidden_words) return;

    const half* in_ptr = fp16_kv + token_idx * head_dim + tid * 32;
    uint32_t packed = 0;

    #pragma unroll 32
    for (int b = 0; b < 32; ++b) {
        float val = __half2float(in_ptr[b]);
        if (val >= 0.0f) {
            packed |= (1u << b);
        }
    }

    packed_bitplanes[token_idx * hidden_words + tid] = packed;
}

// Fused in-place KV cache dequantization kernel:
// Reconstructs bipolar FP16 representations from 1-bit packed bitplanes.
__global__ void fused_blackwell_bit_kv_dequantize_kernel(
    const uint32_t* __restrict__ packed_bitplanes, // [total_tokens, hidden_words]
    half* __restrict__ fp16_kv,                    // [total_tokens, head_dim]
    int total_tokens,
    int head_dim,
    int hidden_words,
    float scale_factor
) {
    int token_idx = blockIdx.x;
    if (token_idx >= total_tokens) return;

    int tid = threadIdx.x;
    if (tid >= hidden_words) return;

    uint32_t packed = packed_bitplanes[token_idx * hidden_words + tid];
    half* out_ptr = fp16_kv + token_idx * head_dim + tid * 32;

    #pragma unroll 32
    for (int b = 0; b < 32; ++b) {
        float sign_val = ((packed >> b) & 1) ? scale_factor : -scale_factor;
        out_ptr[b] = __float2half(sign_val);
    }
}

void launch_fused_blackwell_bit_kv_quantize(
    const half* fp16_kv,
    uint32_t* packed_bitplanes,
    int total_tokens,
    int head_dim,
    int hidden_words,
    cudaStream_t stream
) {
    int threads = hidden_words < 128 ? hidden_words : 128;
    fused_blackwell_bit_kv_quantize_kernel<<<total_tokens, threads, 0, stream>>>(
        fp16_kv, packed_bitplanes, total_tokens, head_dim, hidden_words
    );
}

void launch_fused_blackwell_bit_kv_dequantize(
    const uint32_t* packed_bitplanes,
    half* fp16_kv,
    int total_tokens,
    int head_dim,
    int hidden_words,
    float scale_factor,
    cudaStream_t stream
) {
    int threads = hidden_words < 128 ? hidden_words : 128;
    fused_blackwell_bit_kv_dequantize_kernel<<<total_tokens, threads, 0, stream>>>(
        packed_bitplanes, fp16_kv, total_tokens, head_dim, hidden_words, scale_factor
    );
}

}
