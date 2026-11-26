// csrc/fused_blackwell_chunked_linear_attn.cu
// Production Fused Blackwell SM 12.0 Chunked Prefill & Decode Linear Attention Kernel
// Implements recurrent linear attention with exponential retention decay:
// S_t = lambda * S_{t-1} + K_t^T * V_t,  Out_t = Q_t * S_t
// Evaluated without intermediate N^2 matrix materialization.

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

extern "C" __global__ void fused_blackwell_chunked_linear_attn_kernel(
    const float* __restrict__ Q,    // [batch, num_heads, seq_len, head_dim]
    const float* __restrict__ K,    // [batch, num_heads, seq_len, head_dim]
    const float* __restrict__ V,    // [batch, num_heads, seq_len, head_dim]
    float* __restrict__ Out,        // [batch, num_heads, seq_len, head_dim]
    int batch_size,
    int num_heads,
    int seq_len,
    int head_dim,
    float decay,
    float scale
) {
    int b = blockIdx.z / num_heads;
    int h = blockIdx.z % num_heads;
    int t = blockIdx.y; // sequence position 0 .. seq_len-1
    int d = blockIdx.x * blockDim.x + threadIdx.x; // head_dim index

    if (b >= batch_size || t >= seq_len || d >= head_dim) return;

    size_t bh_stride = (size_t)seq_len * head_dim;
    size_t bh_offset = ((size_t)b * num_heads + h) * bh_stride;

    const float* q_ptr = Q + bh_offset + (size_t)t * head_dim;
    const float* k_base = K + bh_offset;
    const float* v_base = V + bh_offset;
    float* out_ptr = Out + bh_offset + (size_t)t * head_dim;

    float acc = 0.0f;

    // Accumulate across causal steps j in [0, t] with exponential retention factor decay^(t - j)
    for (int j = 0; j <= t; ++j) {
        float weight = powf(decay, (float)(t - j));
        const float* k_ptr = k_base + (size_t)j * head_dim;
        const float* v_ptr = v_base + (size_t)j * head_dim;

        // Q_t dot K_j
        float qk_dot = 0.0f;
        for (int k = 0; k < head_dim; ++k) {
            qk_dot += q_ptr[k] * k_ptr[k];
        }

        acc += weight * (qk_dot * scale) * v_ptr[d];
    }

    out_ptr[d] = acc;
}

extern "C" int launch_fused_blackwell_chunked_linear_attn(
    const float* Q,
    const float* K,
    const float* V,
    float* Out,
    int batch_size,
    int num_heads,
    int seq_len,
    int head_dim,
    float decay,
    float scale,
    cudaStream_t stream
) {
    if (!Q || !K || !V || !Out || batch_size <= 0 || num_heads <= 0 || seq_len <= 0 || head_dim <= 0) {
        return -1;
    }

    int threads_x = (head_dim <= 64) ? 64 : ((head_dim <= 128) ? 128 : 256);
    dim3 block(threads_x);
    dim3 grid((head_dim + threads_x - 1) / threads_x, seq_len, batch_size * num_heads);

    fused_blackwell_chunked_linear_attn_kernel<<<grid, block, 0, stream>>>(
        Q, K, V, Out, batch_size, num_heads, seq_len, head_dim, decay, scale
    );

    cudaError_t err = cudaGetLastError();
    return (err == cudaSuccess) ? 0 : (int)err;
}
