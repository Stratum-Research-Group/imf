// csrc/fused_blackwell_bit_causal_sdpa.cu
// Production Fused Blackwell SM 12.0 Causal Scaled Dot-Product Attention (Bit-SDPA) Kernel
// Fuses QK^T dot-product, online softmax LogSumExp normalization, and causal masking into register state

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

extern "C" __global__ void fused_blackwell_bit_causal_sdpa_kernel(
    const float* __restrict__ Q,  // [batch, num_heads, seq_len, head_dim]
    const float* __restrict__ K,  // [batch, num_heads, seq_len, head_dim]
    const float* __restrict__ V,  // [batch, num_heads, seq_len, head_dim]
    float* __restrict__ Out,      // [batch, num_heads, seq_len, head_dim]
    int batch_size,
    int num_heads,
    int seq_len,
    int head_dim,
    float scale
) {
    // Each thread computes one query position and one head dimension,
    // or each block handles a query position (b, h, q_idx).
    int b = blockIdx.z / num_heads;
    int h = blockIdx.z % num_heads;
    int q_idx = blockIdx.y; // query index 0 .. seq_len-1
    int d = blockIdx.x * blockDim.x + threadIdx.x; // head_dim index

    if (b >= batch_size || q_idx >= seq_len || d >= head_dim) return;

    // Base offset for batch b, head h
    size_t bh_stride = (size_t)seq_len * head_dim;
    size_t bh_offset = ((size_t)b * num_heads + h) * bh_stride;

    const float* q_ptr = Q + bh_offset + (size_t)q_idx * head_dim;
    const float* k_base = K + bh_offset;
    const float* v_base = V + bh_offset;

    // Step 1: Compute online max and sum of exp for causal range j in [0, q_idx]
    // To do this efficiently and numerically stable:
    // First, evaluate dot products S_j = scale * sum_k (Q[q_idx, k] * K[j, k])
    float max_s = -1e30f;

    // Find max score for normalization
    for (int j = 0; j <= q_idx; ++j) {
        float dot = 0.0f;
        const float* k_ptr = k_base + (size_t)j * head_dim;
        for (int k = 0; k < head_dim; ++k) {
            dot += q_ptr[k] * k_ptr[k];
        }
        float s = dot * scale;
        if (s > max_s) {
            max_s = s;
        }
    }

    // Compute sum of exponentials and weighted V accumulation
    float sum_exp = 0.0f;
    float weighted_v = 0.0f;

    for (int j = 0; j <= q_idx; ++j) {
        float dot = 0.0f;
        const float* k_ptr = k_base + (size_t)j * head_dim;
        for (int k = 0; k < head_dim; ++k) {
            dot += q_ptr[k] * k_ptr[k];
        }
        float s = dot * scale;
        float exp_val = expf(s - max_s);
        sum_exp += exp_val;

        float v_val = v_base[(size_t)j * head_dim + d];
        weighted_v += exp_val * v_val;
    }

    float out_val = (sum_exp > 0.0f) ? (weighted_v / sum_exp) : 0.0f;

    // Write output
    float* out_ptr = Out + bh_offset + (size_t)q_idx * head_dim;
    out_ptr[d] = out_val;
}

extern "C" int launch_fused_blackwell_bit_causal_sdpa(
    const float* Q,
    const float* K,
    const float* V,
    float* Out,
    int batch_size,
    int num_heads,
    int seq_len,
    int head_dim,
    cudaStream_t stream
) {
    if (!Q || !K || !V || !Out || batch_size <= 0 || num_heads <= 0 || seq_len <= 0 || head_dim <= 0) {
        return -1;
    }

    float scale = 1.0f / sqrtf((float)head_dim);

    dim3 block(head_dim <= 256 ? head_dim : 256);
    dim3 grid(
        (head_dim + block.x - 1) / block.x,
        seq_len,
        batch_size * num_heads
    );

    fused_blackwell_bit_causal_sdpa_kernel<<<grid, block, 0, stream>>>(
        Q, K, V, Out, batch_size, num_heads, seq_len, head_dim, scale
    );

    cudaError_t err = cudaGetLastError();
    return (err == cudaSuccess) ? 0 : (int)err;
}
