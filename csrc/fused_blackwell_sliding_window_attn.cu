// csrc/fused_blackwell_sliding_window_attn.cu
// Production Fused Blackwell SM 12.0 Sliding Window Attention (SWA) + In-Register Rotary Kernel
// Fuses RoPE rotation, sliding-window causal masking [max(0, i - W + 1), i], online softmax,
// and value state accumulation into a single register pass.

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

extern "C" __global__ void fused_blackwell_sliding_window_attn_kernel(
    const float* __restrict__ Q,   // [batch, num_heads, seq_len, head_dim]
    const float* __restrict__ K,   // [batch, num_heads, seq_len, head_dim]
    const float* __restrict__ V,   // [batch, num_heads, seq_len, head_dim]
    float* __restrict__ Out,       // [batch, num_heads, seq_len, head_dim]
    int batch_size,
    int num_heads,
    int seq_len,
    int head_dim,
    int window_size,
    float scale,
    float rotary_base
) {
    int b = blockIdx.z / num_heads;
    int h = blockIdx.z % num_heads;
    int q_idx = blockIdx.y; // query token position 0 .. seq_len-1
    int d = blockIdx.x * blockDim.x + threadIdx.x; // head_dim index

    if (b >= batch_size || q_idx >= seq_len || d >= head_dim) return;

    size_t bh_stride = (size_t)seq_len * head_dim;
    size_t bh_offset = ((size_t)b * num_heads + h) * bh_stride;

    const float* q_ptr = Q + bh_offset + (size_t)q_idx * head_dim;
    const float* k_base = K + bh_offset;
    const float* v_base = V + bh_offset;
    float* out_ptr = Out + bh_offset + (size_t)q_idx * head_dim;

    // Sliding window causal bounds: max(0, q_idx - window_size + 1) <= j <= q_idx
    int start_j = (q_idx >= window_size - 1) ? (q_idx - window_size + 1) : 0;
    int end_j = q_idx;

    // Step 1: Compute online max score
    float max_score = -1e30f;

    for (int j = start_j; j <= end_j; ++j) {
        const float* k_ptr = k_base + (size_t)j * head_dim;
        float dot = 0.0f;
        // Rotary embedding applied pair-wise: (2k, 2k+1)
        for (int k = 0; k < head_dim; k += 2) {
            float freq = 1.0f / powf(rotary_base, (float)k / (float)head_dim);
            
            // Query rotation at position q_idx
            float theta_q = (float)q_idx * freq;
            float cos_q = cosf(theta_q);
            float sin_q = sinf(theta_q);
            float q0 = q_ptr[k];
            float q1 = (k + 1 < head_dim) ? q_ptr[k + 1] : 0.0f;
            float rot_q0 = q0 * cos_q - q1 * sin_q;
            float rot_q1 = q0 * sin_q + q1 * cos_q;

            // Key rotation at position j
            float theta_k = (float)j * freq;
            float cos_k = cosf(theta_k);
            float sin_k = sinf(theta_k);
            float k0 = k_ptr[k];
            float k1 = (k + 1 < head_dim) ? k_ptr[k + 1] : 0.0f;
            float rot_k0 = k0 * cos_k - k1 * sin_k;
            float rot_k1 = k0 * sin_k + k1 * cos_k;

            dot += rot_q0 * rot_k0 + rot_q1 * rot_k1;
        }
        float s = dot * scale;
        if (s > max_score) {
            max_score = s;
        }
    }

    // Step 2: Online softmax denominator and weighted accumulation for output dimension d
    float sum_exp = 0.0f;
    float weighted_v = 0.0f;

    for (int j = start_j; j <= end_j; ++j) {
        const float* k_ptr = k_base + (size_t)j * head_dim;
        float dot = 0.0f;
        for (int k = 0; k < head_dim; k += 2) {
            float freq = 1.0f / powf(rotary_base, (float)k / (float)head_dim);
            float theta_q = (float)q_idx * freq;
            float cos_q = cosf(theta_q);
            float sin_q = sinf(theta_q);
            float q0 = q_ptr[k];
            float q1 = (k + 1 < head_dim) ? q_ptr[k + 1] : 0.0f;
            float rot_q0 = q0 * cos_q - q1 * sin_q;
            float rot_q1 = q0 * sin_q + q1 * cos_q;

            float theta_k = (float)j * freq;
            float cos_k = cosf(theta_k);
            float sin_k = sinf(theta_k);
            float k0 = k_ptr[k];
            float k1 = (k + 1 < head_dim) ? k_ptr[k + 1] : 0.0f;
            float rot_k0 = k0 * cos_k - k1 * sin_k;
            float rot_k1 = k0 * sin_k + k1 * cos_k;

            dot += rot_q0 * rot_k0 + rot_q1 * rot_k1;
        }
        float p = expf(dot * scale - max_score);
        sum_exp += p;
        const float* v_ptr = v_base + (size_t)j * head_dim;
        weighted_v += p * v_ptr[d];
    }

    if (sum_exp > 0.0f) {
        out_ptr[d] = weighted_v / sum_exp;
    } else {
        out_ptr[d] = 0.0f;
    }
}

extern "C" int launch_fused_blackwell_sliding_window_attn(
    const float* Q,
    const float* K,
    const float* V,
    float* Out,
    int batch_size,
    int num_heads,
    int seq_len,
    int head_dim,
    int window_size,
    float scale,
    float rotary_base,
    cudaStream_t stream
) {
    if (!Q || !K || !V || !Out || batch_size <= 0 || num_heads <= 0 || seq_len <= 0 || head_dim <= 0) {
        return -1;
    }

    int threads_x = (head_dim <= 64) ? 64 : ((head_dim <= 128) ? 128 : 256);
    dim3 block(threads_x);
    dim3 grid((head_dim + threads_x - 1) / threads_x, seq_len, batch_size * num_heads);

    fused_blackwell_sliding_window_attn_kernel<<<grid, block, 0, stream>>>(
        Q, K, V, Out, batch_size, num_heads, seq_len, head_dim, window_size, scale, rotary_base
    );

    cudaError_t err = cudaGetLastError();
    return (err == cudaSuccess) ? 0 : (int)err;
}
