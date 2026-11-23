#include <cuda_runtime.h>
#include <stdio.h>
#include <math.h>

/**
 * Robust Fused Flash-Cayley Attention Kernel.
 * Each warp processes one query token.
 * Cayley rotation is precomputed per-batch in global/shared memory.
 */

#define D_MODEL 8

__global__ void fused_flash_cayley_attention_kernel(
    const float* __restrict__ Q,      // [B, S, D]
    const float* __restrict__ K,      // [B, S, D]
    const float* __restrict__ V,      // [B, S, D]
    const float* __restrict__ R,      // [B, D, D] precomputed SO(D) rotation matrix
    float* __restrict__ Out,          // [B, S, D]
    int batch_size,
    int seq_len,
    float scale
) {
    int b = blockIdx.x;
    int q_idx = blockIdx.y * blockDim.x + threadIdx.x;

    if (b >= batch_size || q_idx >= seq_len) return;

    // Load local R into registers
    float local_R[8][8];
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            local_R[r][c] = R[b * 64 + r * 8 + c];
        }
    }

    // Load query
    float q_orig[8];
    for (int d = 0; d < 8; d++) {
        q_orig[d] = Q[b * seq_len * 8 + q_idx * 8 + d];
    }

    // Rotate query: q_rot = R * q_orig
    float q_rot[8] = {0.0f};
    for (int r = 0; r < 8; r++) {
        for (int c = 0; c < 8; c++) {
            q_rot[r] += local_R[r][c] * q_orig[c];
        }
    }

    // Online softmax state
    float m_prev = -1e30f;
    float l_prev = 0.0f;
    float acc[8] = {0.0f};

    // Iterate through all keys and values sequentially
    for (int k_idx = 0; k_idx < seq_len; k_idx++) {
        float score = 0.0f;
        for (int d = 0; d < 8; d++) {
            score += q_rot[d] * K[b * seq_len * 8 + k_idx * 8 + d];
        }
        score *= scale;

        float m_curr = fmaxf(m_prev, score);
        float exp_old = expf(m_prev - m_curr);
        float exp_new = expf(score - m_curr);

        l_prev = l_prev * exp_old + exp_new;
        for (int d = 0; d < 8; d++) {
            acc[d] = acc[d] * exp_old + exp_new * V[b * seq_len * 8 + k_idx * 8 + d];
        }
        m_prev = m_curr;
    }

    if (l_prev > 0.0f) {
        for (int d = 0; d < 8; d++) {
            Out[b * seq_len * 8 + q_idx * 8 + d] = acc[d] / l_prev;
        }
    }
}

extern "C" void launch_fused_flash_cayley_attention(
    const float* d_Q,
    const float* d_K,
    const float* d_V,
    const float* d_R,
    float* d_Out,
    int batch_size,
    int seq_len,
    float scale,
    cudaStream_t stream
) {
    int threads = 128;
    dim3 grid(batch_size, (seq_len + threads - 1) / threads);
    dim3 block(threads);
    fused_flash_cayley_attention_kernel<<<grid, block, 0, stream>>>(
        d_Q, d_K, d_V, d_R, d_Out, batch_size, seq_len, scale
    );
}
