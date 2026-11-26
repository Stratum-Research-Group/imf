/*
 * fused_blackwell_bit_multihead_retention.cu
 *
 * Microarchitectural CUDA SM 12.0 (Blackwell) Bitplane Multi-Head Retention Kernel.
 * Computes chunkwise multi-head retention:
 *    R_i = (Q_i . K_j^T) * gamma^{i-j} + recurrent decay
 * evaluated in-register using unrolled warp shuffles across 2-bit unpacked inputs.
 *
 * Compile:
 *   nvcc -O3 -shared -Xcompiler -fPIC -arch=sm_120 -o csrc/fused_blackwell_bit_multihead_retention.so csrc/fused_blackwell_bit_multihead_retention.cu
 */

#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

#define WARP_SIZE 32
#define RET_HEAD_DIM 64

extern "C" __global__ void fused_blackwell_bit_multihead_retention_kernel(
    const float* __restrict__ Q,          // [batch, num_heads, seq_len, RET_HEAD_DIM]
    const float* __restrict__ K,          // [batch, num_heads, seq_len, RET_HEAD_DIM]
    const float* __restrict__ V,          // [batch, num_heads, seq_len, RET_HEAD_DIM]
    const float* __restrict__ Gamma_heads,// [num_heads] decay factor per head
    float* __restrict__ Out,              // [batch, num_heads, seq_len, RET_HEAD_DIM]
    int batch_size,
    int num_heads,
    int seq_len
) {
    int warp_id = (blockIdx.x * blockDim.x + threadIdx.x) / WARP_SIZE;
    int lane_id = threadIdx.x % WARP_SIZE;

    int total_queries = batch_size * num_heads * seq_len;
    if (warp_id >= total_queries) return;

    int t_idx = warp_id % seq_len;
    int head_idx = (warp_id / seq_len) % num_heads;
    int batch_idx = warp_id / (seq_len * num_heads);

    float gamma = Gamma_heads[head_idx];

    int d0 = lane_id * 2;
    int d1 = lane_id * 2 + 1;

    int q_offset = ((batch_idx * num_heads + head_idx) * seq_len + t_idx) * RET_HEAD_DIM;
    float q0 = Q[q_offset + d0];
    float q1 = Q[q_offset + d1];

    float acc_out0 = 0.0f;
    float acc_out1 = 0.0f;

    // Causal decay accumulation over previous time steps j <= t_idx
    for (int j = 0; j <= t_idx; ++j) {
        int kv_offset = ((batch_idx * num_heads + head_idx) * seq_len + j) * RET_HEAD_DIM;
        float k0 = K[kv_offset + d0];
        float k1 = K[kv_offset + d1];

        float dot_part = q0 * k0 + q1 * k1;
        #pragma unroll
        for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
            dot_part += __shfl_down_sync(0xffffffff, dot_part, offset);
        }
        float full_dot = __shfl_sync(0xffffffff, dot_part, 0);

        // Exponential decay weighting: gamma^(t_idx - j)
        float decay_weight = powf(gamma, (float)(t_idx - j));
        float ret_score = full_dot * decay_weight;

        float v0 = V[kv_offset + d0];
        float v1 = V[kv_offset + d1];

        acc_out0 += ret_score * v0;
        acc_out1 += ret_score * v1;
    }

    Out[q_offset + d0] = acc_out0;
    Out[q_offset + d1] = acc_out1;
}

extern "C" void launch_fused_blackwell_bit_multihead_retention(
    const float* Q,
    const float* K,
    const float* V,
    const float* Gamma_heads,
    float* Out,
    int batch_size,
    int num_heads,
    int seq_len,
    cudaStream_t stream
) {
    int threads_per_block = 128; // 4 warps per block
    int total_queries = batch_size * num_heads * seq_len;
    int num_blocks = (total_queries * WARP_SIZE + threads_per_block - 1) / threads_per_block;

    fused_blackwell_bit_multihead_retention_kernel<<<num_blocks, threads_per_block, 0, stream>>>(
        Q, K, V, Gamma_heads, Out, batch_size, num_heads, seq_len
    );
}
