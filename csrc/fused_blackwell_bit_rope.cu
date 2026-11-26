// csrc/fused_blackwell_bit_rope.cu
// Production Fused Blackwell SM 12.0 Rotary Position Embedding (RoPE) Kernel
// Applies in-register 2D complex rotations across attention Query / Key projections

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

extern "C" __global__ void fused_blackwell_bit_rope_kernel(
    const float* __restrict__ QK_in,   // [batch, seq_len, num_heads, head_dim]
    float* __restrict__ QK_out,        // [batch, seq_len, num_heads, head_dim]
    int seq_len,
    int num_heads,
    int head_dim,
    int batch_size,
    float base_theta
) {
    int total_threads = blockDim.x * gridDim.x;
    int idx = blockIdx.x * blockDim.x + threadIdx.x;

    int total_elements = batch_size * seq_len * num_heads * (head_dim / 2);
    if (idx >= total_elements) return;

    // Deconstruct index into: batch, pos (seq_idx), head_idx, pair_idx
    int half_dim = head_dim / 2;
    int pair_idx = idx % half_dim;
    int temp = idx / half_dim;
    int head_idx = temp % num_heads;
    temp = temp / num_heads;
    int pos = temp % seq_len;
    int b = temp / seq_len;

    // Compute RoPE frequency: theta_i = base_theta ^ (-2*i / head_dim)
    float exponent = -2.0f * (float)pair_idx / (float)head_dim;
    float theta = powf(base_theta, exponent);
    float angle = (float)pos * theta;
    float cos_val = cosf(angle);
    float sin_val = sinf(angle);

    // Flat base offset for this (b, pos, head_idx)
    int base_offset = ((b * seq_len + pos) * num_heads + head_idx) * head_dim;
    int idx0 = base_offset + pair_idx;
    int idx1 = base_offset + pair_idx + half_dim;

    float v0 = QK_in[idx0];
    float v1 = QK_in[idx1];

    // Standard complex rotation:
    // v0' = v0 * cos - v1 * sin
    // v1' = v0 * sin + v1 * cos
    QK_out[idx0] = v0 * cos_val - v1 * sin_val;
    QK_out[idx1] = v0 * sin_val + v1 * cos_val;
}

extern "C" {

void launch_fused_blackwell_bit_rope(
    const float* QK_in,
    float* QK_out,
    int seq_len,
    int num_heads,
    int head_dim,
    int batch_size,
    float base_theta,
    cudaStream_t stream
) {
    int total_elements = batch_size * seq_len * num_heads * (head_dim / 2);
    int threads = 128;
    int blocks = (total_elements + threads - 1) / threads;

    fused_blackwell_bit_rope_kernel<<<blocks, threads, 0, stream>>>(
        QK_in, QK_out, seq_len, num_heads, head_dim, batch_size, base_theta
    );
}

}
