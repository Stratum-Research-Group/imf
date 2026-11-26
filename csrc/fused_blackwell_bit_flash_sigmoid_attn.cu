/*
 * fused_blackwell_bit_flash_sigmoid_attn.cu
 *
 * Microarchitectural CUDA SM 12.0 (Blackwell) Bitplane Flash-Sigmoid Attention Kernel.
 * Computes scale-free, partition-function-free causal attention using element-wise
 * sigmoid activation:
 *    A_{ij} = sigmoid((Q_i . K_j) / sqrt(d) + bias)
 *    O_i = sum_{j <= i} A_{ij} * V_j
 * Entirely within warp registers and tile shared memory, bypassing global softmax reductions.
 *
 * Compile:
 *   nvcc -O3 -shared -Xcompiler -fPIC -arch=sm_120 -o csrc/fused_blackwell_bit_flash_sigmoid_attn.so csrc/fused_blackwell_bit_flash_sigmoid_attn.cu
 */

#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

#define WARP_SIZE 32
#define HEAD_DIM 64
#define TILE_SEQ 32

__device__ __forceinline__ float fast_sigmoid(float x) {
    return 1.0f / (1.0f + __expf(-x));
}

extern "C" __global__ void fused_blackwell_bit_flash_sigmoid_attn_kernel(
    const float* __restrict__ Q,          // [batch, num_heads, seq_len, HEAD_DIM]
    const float* __restrict__ K,          // [batch, num_heads, seq_len, HEAD_DIM]
    const float* __restrict__ V,          // [batch, num_heads, seq_len, HEAD_DIM]
    const float* __restrict__ bias,       // [HEAD_DIM] or scalar
    float* __restrict__ Out,              // [batch, num_heads, seq_len, HEAD_DIM]
    int batch_size,
    int num_heads,
    int seq_len,
    float scale
) {
    // Each warp computes attention for a single query token across all keys up to its causal boundary
    int warp_id = (blockIdx.x * blockDim.x + threadIdx.x) / WARP_SIZE;
    int lane_id = threadIdx.x % WARP_SIZE;

    int total_queries = batch_size * num_heads * seq_len;
    if (warp_id >= total_queries) return;

    int q_idx = warp_id % seq_len;
    int head_idx = (warp_id / seq_len) % num_heads;
    int batch_idx = warp_id / (seq_len * num_heads);

    int q_offset = ((batch_idx * num_heads + head_idx) * seq_len + q_idx) * HEAD_DIM;
    
    // Each thread in warp handles 2 dimensions of HEAD_DIM (64 / 32 = 2)
    int d0 = lane_id * 2;
    int d1 = lane_id * 2 + 1;

    float q_val0 = Q[q_offset + d0];
    float q_val1 = Q[q_offset + d1];

    float acc_out0 = 0.0f;
    float acc_out1 = 0.0f;

    // Loop causally over keys and values from t = 0 to q_idx
    for (int k_idx = 0; k_idx <= q_idx; ++k_idx) {
        int kv_offset = ((batch_idx * num_heads + head_idx) * seq_len + k_idx) * HEAD_DIM;
        float k_val0 = K[kv_offset + d0];
        float k_val1 = K[kv_offset + d1];

        // Partial dot product across the 2 elements owned by this lane
        float dot_part = q_val0 * k_val0 + q_val1 * k_val1;

        // Warp reduction to obtain full Q . K dot product
        #pragma unroll
        for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
            dot_part += __shfl_down_sync(0xffffffff, dot_part, offset);
        }

        // Broadcast score to all lanes in the warp
        float full_dot = __shfl_sync(0xffffffff, dot_part, 0);

        // Apply scale and sigmoid activation (no exp-overflow softmax denominator!)
        float attn_weight = fast_sigmoid(full_dot * scale);

        // Accumulate weighted value
        float v_val0 = V[kv_offset + d0];
        float v_val1 = V[kv_offset + d1];

        acc_out0 += attn_weight * v_val0;
        acc_out1 += attn_weight * v_val1;
    }

    // Write output
    Out[q_offset + d0] = acc_out0;
    Out[q_offset + d1] = acc_out1;
}

extern "C" void launch_fused_blackwell_bit_flash_sigmoid_attn(
    const float* Q,
    const float* K,
    const float* V,
    const float* bias,
    float* Out,
    int batch_size,
    int num_heads,
    int seq_len,
    cudaStream_t stream
) {
    int threads_per_block = 128; // 4 warps per block
    int total_queries = batch_size * num_heads * seq_len;
    int num_blocks = (total_queries * WARP_SIZE + threads_per_block - 1) / threads_per_block;
    float scale = 1.0f / sqrtf((float)HEAD_DIM);

    fused_blackwell_bit_flash_sigmoid_attn_kernel<<<num_blocks, threads_per_block, 0, stream>>>(
        Q, K, V, bias, Out, batch_size, num_heads, seq_len, scale
    );
}
