// csrc/fused_blackwell_lie_rolling_kv.cu
// Production Fused Blackwell SM 12.0 Warp-Level Lie Rolling KV-Cache Kernel
// Supports optional contractive dissipation lambda in [0.0, 1.0], block-diagonal SO(4)^8,
// and multi-token chunked in-register caching to eliminate per-token global memory round-trips.

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

#define WARP_SIZE 32
#define MAX_HEAD_DIM 32

extern "C" __global__ void fused_blackwell_lie_rolling_kv_kernel(
    const float* __restrict__ q,          // [batch, heads, 1, head_dim]
    const float* __restrict__ k,          // [batch, heads, 1, head_dim]
    const float* __restrict__ v,          // [batch, heads, 1, head_dim]
    const float* __restrict__ U_mat,      // [heads, head_dim, head_dim]
    float* __restrict__ state_M,          // [batch, heads, head_dim, head_dim] (in/out)
    float* __restrict__ y_out,            // [batch, heads, 1, head_dim] (out)
    int batch_size,
    int num_heads,
    int head_dim,
    float lambda_dissipation              // Contraction factor in (0.0, 1.0]; default 1.0 (undamped)
) {
    int b = blockIdx.x;
    int h = blockIdx.y;
    if (b >= batch_size || h >= num_heads) return;

    int tid = threadIdx.x; // Thread handles a row of M: tid in [0, head_dim)
    if (tid >= head_dim) return;

    const float* q_ptr = q + ((size_t)b * num_heads + h) * head_dim;
    const float* k_ptr = k + ((size_t)b * num_heads + h) * head_dim;
    const float* v_ptr = v + ((size_t)b * num_heads + h) * head_dim;
    const float* U_ptr = U_mat + (size_t)h * head_dim * head_dim;
    float* M_ptr = state_M + ((size_t)b * num_heads + h) * head_dim * head_dim;
    float* y_ptr = y_out + ((size_t)b * num_heads + h) * head_dim;

    float v_i = v_ptr[tid];
    float k_i = k_ptr[tid];

    __shared__ float s_q[MAX_HEAD_DIM];
    __shared__ float s_k[MAX_HEAD_DIM];
    __shared__ float s_v[MAX_HEAD_DIM];
    __shared__ float s_temp[MAX_HEAD_DIM][MAX_HEAD_DIM];

    s_q[tid] = q_ptr[tid];
    s_k[tid] = k_i;
    s_v[tid] = v_i;
    __syncthreads();

    // 1. Compute Step 1 of similarity transform: Temp = U * M
    for (int j = 0; j < head_dim; ++j) {
        float sum = 0.0f;
        for (int m = 0; m < head_dim; ++m) {
            sum += U_ptr[tid * head_dim + m] * M_ptr[m * head_dim + j];
        }
        s_temp[tid][j] = sum;
    }
    __syncthreads();

    // 2. Compute Step 2: M_new = lambda * (Temp * U^T) + (v * k^T - k * v^T)
    for (int j = 0; j < head_dim; ++j) {
        float sum = 0.0f;
        for (int m = 0; m < head_dim; ++m) {
            sum += s_temp[tid][m] * U_ptr[j * head_dim + m]; // U^T[m, j] = U[j, m]
        }
        // Anti-symmetric commutator W = v k^T - k v^T
        float W_ij = s_v[tid] * s_k[j] - s_k[tid] * s_v[j];
        M_ptr[tid * head_dim + j] = lambda_dissipation * sum + W_ij;
    }
    __syncthreads();

    // 3. Query output y = M_new * q
    float y_val = 0.0f;
    for (int j = 0; j < head_dim; ++j) {
        y_val += M_ptr[tid * head_dim + j] * s_q[j];
    }
    y_ptr[tid] = y_val;
}

// Multi-Token Chunked In-Register Lie Rolling KV-Cache Kernel
// Loads state M ONCE from global memory, processes an entire chunk of tokens (chunk_len)
// purely inside registers and shared staging memory, and commits state back ONCE.
extern "C" __global__ void fused_blackwell_chunked_lie_rolling_kv_kernel(
    const float* __restrict__ q_chunk,    // [batch, heads, chunk_len, head_dim]
    const float* __restrict__ k_chunk,    // [batch, heads, chunk_len, head_dim]
    const float* __restrict__ v_chunk,    // [batch, heads, chunk_len, head_dim]
    const float* __restrict__ U_mat,      // [heads, head_dim, head_dim]
    float* __restrict__ state_M,          // [batch, heads, head_dim, head_dim] (in/out)
    float* __restrict__ y_chunk_out,      // [batch, heads, chunk_len, head_dim] (out)
    int batch_size,
    int num_heads,
    int head_dim,
    int chunk_len,
    float lambda_dissipation
) {
    int b = blockIdx.x;
    int h = blockIdx.y;
    if (b >= batch_size || h >= num_heads) return;

    int tid = threadIdx.x;
    if (tid >= head_dim) return;

    const size_t bh_stride_chunk = ((size_t)b * num_heads + h) * chunk_len * head_dim;
    const size_t bh_stride_state = ((size_t)b * num_heads + h) * head_dim * head_dim;
    const float* U_ptr = U_mat + (size_t)h * head_dim * head_dim;
    float* M_ptr = state_M + bh_stride_state;

    // Load state M row into local register array ONCE at start of chunk
    float reg_M[MAX_HEAD_DIM];
    #pragma unroll
    for (int j = 0; j < head_dim; ++j) {
        reg_M[j] = M_ptr[tid * head_dim + j];
    }

    __shared__ float s_q[MAX_HEAD_DIM];
    __shared__ float s_k[MAX_HEAD_DIM];
    __shared__ float s_v[MAX_HEAD_DIM];
    __shared__ float s_temp[MAX_HEAD_DIM][MAX_HEAD_DIM];

    // Loop over all tokens in the chunk completely in registers
    for (int step = 0; step < chunk_len; ++step) {
        const size_t tok_offset = bh_stride_chunk + step * head_dim;
        const float* q_tok = q_chunk + tok_offset;
        const float* k_tok = k_chunk + tok_offset;
        const float* v_tok = v_chunk + tok_offset;
        float* y_tok = y_chunk_out + tok_offset;

        s_q[tid] = q_tok[tid];
        s_k[tid] = k_tok[tid];
        s_v[tid] = v_tok[tid];
        __syncthreads();

        // 1. Temp = U * reg_M
        for (int j = 0; j < head_dim; ++j) {
            float sum = 0.0f;
            for (int m = 0; m < head_dim; ++m) {
                sum += U_ptr[tid * head_dim + m] * reg_M[j];
            }
            s_temp[tid][j] = sum;
        }
        __syncthreads();

        // 2. reg_M_new = lambda * Temp * U^T + W
        float v_i = s_v[tid];
        for (int j = 0; j < head_dim; ++j) {
            float sum = 0.0f;
            for (int m = 0; m < head_dim; ++m) {
                sum += s_temp[tid][m] * U_ptr[j * head_dim + m];
            }
            float W_ij = v_i * s_k[j] - s_k[tid] * s_v[j];
            reg_M[j] = lambda_dissipation * sum + W_ij;
        }
        __syncthreads();

        // 3. Compute output for token y_step = reg_M * q
        float y_val = 0.0f;
        for (int j = 0; j < head_dim; ++j) {
            y_val += reg_M[j] * s_q[j];
        }
        y_tok[tid] = y_val;
        __syncthreads();
    }

    // Write state M row back to global memory ONCE at end of chunk
    #pragma unroll
    for (int j = 0; j < head_dim; ++j) {
        M_ptr[tid * head_dim + j] = reg_M[j];
    }
}

// Block-Diagonal SO(4)^8 Kernel: Executes 8 independent 4x4 rotations per 32x32 head
extern "C" __global__ void fused_blackwell_block_diagonal_so4_kernel(
    const float* __restrict__ q,          // [batch, heads, 1, 32]
    const float* __restrict__ k,          // [batch, heads, 1, 32]
    const float* __restrict__ v,          // [batch, heads, 1, 32]
    const float* __restrict__ U_blocks,   // [heads, 8, 4, 4] -> 8 quaternion blocks
    float* __restrict__ state_M,          // [batch, heads, 32, 32]
    float* __restrict__ y_out,            // [batch, heads, 1, 32]
    int batch_size,
    int num_heads,
    float lambda_dissipation
) {
    int b = blockIdx.x;
    int h = blockIdx.y;
    if (b >= batch_size || h >= num_heads) return;

    int tid = threadIdx.x; // [0, 31]
    if (tid >= 32) return;

    int block_idx = tid / 4; // Which SO(4) block [0, 7]
    int local_r = tid % 4;   // Row within 4x4 block [0, 3]

    const float* q_ptr = q + ((size_t)b * num_heads + h) * 32;
    const float* k_ptr = k + ((size_t)b * num_heads + h) * 32;
    const float* v_ptr = v + ((size_t)b * num_heads + h) * 32;
    const float* Ub_ptr = U_blocks + ((size_t)h * 8 + block_idx) * 16;
    float* M_ptr = state_M + ((size_t)b * num_heads + h) * 1024;
    float* y_ptr = y_out + ((size_t)b * num_heads + h) * 32;

    __shared__ float s_q[32];
    __shared__ float s_k[32];
    __shared__ float s_v[32];
    __shared__ float s_temp[32][32];

    s_q[tid] = q_ptr[tid];
    s_k[tid] = k_ptr[tid];
    s_v[tid] = v_ptr[tid];
    __syncthreads();

    // 1. Block-diagonal Temp = U_block * M_block
    for (int j = 0; j < 32; ++j) {
        float sum = 0.0f;
        #pragma unroll
        for (int m = 0; m < 4; ++m) {
            sum += Ub_ptr[local_r * 4 + m] * M_ptr[(block_idx * 4 + m) * 32 + j];
        }
        s_temp[tid][j] = sum;
    }
    __syncthreads();

    // 2. Block-diagonal M_new = lambda * Temp * U_block^T + W
    for (int j = 0; j < 32; ++j) {
        int col_block = j / 4;
        int local_c = j % 4;
        const float* Ub_col = U_blocks + ((size_t)h * 8 + col_block) * 16;

        float sum = 0.0f;
        #pragma unroll
        for (int m = 0; m < 4; ++m) {
            sum += s_temp[tid][col_block * 4 + m] * Ub_col[local_c * 4 + m];
        }
        float W_ij = s_v[tid] * s_k[j] - s_k[tid] * s_v[j];
        M_ptr[tid * 32 + j] = lambda_dissipation * sum + W_ij;
    }
    __syncthreads();

    // 3. Query output y = M_new * q
    float y_val = 0.0f;
    for (int j = 0; j < 32; ++j) {
        y_val += M_ptr[tid * 32 + j] * s_q[j];
    }
    y_ptr[tid] = y_val;
}

extern "C" int launch_fused_blackwell_lie_rolling_kv(
    const float* q,
    const float* k,
    const float* v,
    const float* U_mat,
    float* state_M,
    float* y_out,
    int batch_size,
    int num_heads,
    int head_dim,
    float lambda_dissipation,
    cudaStream_t stream
) {
    if (!q || !k || !v || !U_mat || !state_M || !y_out || batch_size <= 0 || num_heads <= 0 || head_dim <= 0 || head_dim > MAX_HEAD_DIM) {
        return -1;
    }

    dim3 grid(batch_size, num_heads);
    dim3 block(head_dim);

    fused_blackwell_lie_rolling_kv_kernel<<<grid, block, 0, stream>>>(
        q, k, v, U_mat, state_M, y_out, batch_size, num_heads, head_dim, lambda_dissipation
    );

    cudaError_t err = cudaGetLastError();
    return (err == cudaSuccess) ? 0 : (int)err;
}

extern "C" int launch_fused_blackwell_chunked_lie_rolling_kv(
    const float* q_chunk,
    const float* k_chunk,
    const float* v_chunk,
    const float* U_mat,
    float* state_M,
    float* y_chunk_out,
    int batch_size,
    int num_heads,
    int head_dim,
    int chunk_len,
    float lambda_dissipation,
    cudaStream_t stream
) {
    if (!q_chunk || !k_chunk || !v_chunk || !U_mat || !state_M || !y_chunk_out || batch_size <= 0 || num_heads <= 0 || head_dim <= 0 || chunk_len <= 0) {
        return -1;
    }

    dim3 grid(batch_size, num_heads);
    dim3 block(head_dim);

    fused_blackwell_chunked_lie_rolling_kv_kernel<<<grid, block, 0, stream>>>(
        q_chunk, k_chunk, v_chunk, U_mat, state_M, y_chunk_out, batch_size, num_heads, head_dim, chunk_len, lambda_dissipation
    );

    cudaError_t err = cudaGetLastError();
    return (err == cudaSuccess) ? 0 : (int)err;
}

extern "C" int launch_fused_blackwell_block_diagonal_so4(
    const float* q,
    const float* k,
    const float* v,
    const float* U_blocks,
    float* state_M,
    float* y_out,
    int batch_size,
    int num_heads,
    float lambda_dissipation,
    cudaStream_t stream
) {
    if (!q || !k || !v || !U_blocks || !state_M || !y_out || batch_size <= 0 || num_heads <= 0) {
        return -1;
    }

    dim3 grid(batch_size, num_heads);
    dim3 block(32);

    fused_blackwell_block_diagonal_so4_kernel<<<grid, block, 0, stream>>>(
        q, k, v, U_blocks, state_M, y_out, batch_size, num_heads, lambda_dissipation
    );

    cudaError_t err = cudaGetLastError();
    return (err == cudaSuccess) ? 0 : (int)err;
}
