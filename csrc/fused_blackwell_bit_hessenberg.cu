/*
 * fused_blackwell_bit_hessenberg.cu
 *
 * Microarchitectural CUDA SM 12.0 (Blackwell) Bitplane Upper Hessenberg Reduction Kernel.
 * Computes exact orthogonal similarity transformation H = Q^T * A * Q reducing general
 * 16x16 matrices to upper Hessenberg form (H_{i,j} = 0 for i > j + 1) using unrolled Givens
 * rotations entirely within Blackwell warp registers and shared memory tiles.
 *
 * Compile:
 *   nvcc -O3 -shared -Xcompiler -fPIC -arch=sm_120 -o csrc/fused_blackwell_bit_hessenberg.so csrc/fused_blackwell_bit_hessenberg.cu
 */

#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

#define WARP_SIZE 32
#define HESS_DIM 16 // 16x16 matrix (256 floats)

extern "C" __global__ void fused_blackwell_bit_hessenberg_kernel(
    const float* __restrict__ A_in,       // [batch, HESS_DIM, HESS_DIM]
    float* __restrict__ H_out,            // [batch, HESS_DIM, HESS_DIM]
    float* __restrict__ Q_out,            // [batch, HESS_DIM, HESS_DIM]
    int batch_size
) {
    int warp_id = (blockIdx.x * blockDim.x + threadIdx.x) / WARP_SIZE;
    int lane_id = threadIdx.x % WARP_SIZE;

    if (warp_id >= batch_size) return;

    __shared__ float s_H[4][HESS_DIM][HESS_DIM];
    __shared__ float s_Q[4][HESS_DIM][HESS_DIM];
    int warp_in_block = threadIdx.x / WARP_SIZE;

    int offset = warp_id * HESS_DIM * HESS_DIM;

    // Load matrix A into s_H and initialize Q as identity
    for (int idx = lane_id; idx < HESS_DIM * HESS_DIM; idx += WARP_SIZE) {
        int r = idx / HESS_DIM;
        int c = idx % HESS_DIM;
        s_H[warp_in_block][r][c] = A_in[offset + idx];
        s_Q[warp_in_block][r][c] = (r == c) ? 1.0f : 0.0f;
    }
    __syncwarp();

    // Hessenberg reduction via Givens rotations:
    // For each column j from 0 to HESS_DIM - 3, zero out elements H(i, j) for i = HESS_DIM - 1 down to j + 2
    for (int j = 0; j < HESS_DIM - 2; ++j) {
        for (int i = HESS_DIM - 1; i > j + 1; --i) {
            float c_rot = 1.0f;
            float s_rot = 0.0f;

            if (lane_id == 0) {
                float a = s_H[warp_in_block][i - 1][j];
                float b = s_H[warp_in_block][i][j];
                if (fabsf(b) > 1e-7f) {
                    float r = hypotf(a, b);
                    c_rot = a / r;
                    s_rot = -b / r;
                }
            }

            c_rot = __shfl_sync(0xffffffff, c_rot, 0);
            s_rot = __shfl_sync(0xffffffff, s_rot, 0);

            // Left multiplication: G * H (acts on rows i-1 and i)
            if (lane_id < HESS_DIM) {
                int col = lane_id;
                float top = s_H[warp_in_block][i - 1][col];
                float bot = s_H[warp_in_block][i][col];
                s_H[warp_in_block][i - 1][col] = c_rot * top - s_rot * bot;
                s_H[warp_in_block][i][col]     = s_rot * top + c_rot * bot;
            }
            __syncwarp();

            // Right multiplication: H * G^T (acts on columns i-1 and i to preserve similarity)
            if (lane_id < HESS_DIM) {
                int row = lane_id;
                float left  = s_H[warp_in_block][row][i - 1];
                float right = s_H[warp_in_block][row][i];
                s_H[warp_in_block][row][i - 1] = c_rot * left - s_rot * right;
                s_H[warp_in_block][row][i]     = s_rot * left + c_rot * right;

                // Accumulate similarity transformations into Q
                float q_left  = s_Q[warp_in_block][row][i - 1];
                float q_right = s_Q[warp_in_block][row][i];
                s_Q[warp_in_block][row][i - 1] = c_rot * q_left - s_rot * q_right;
                s_Q[warp_in_block][row][i]     = s_rot * q_left + c_rot * q_right;
            }
            __syncwarp();
        }
    }

    // Write out results
    for (int idx = lane_id; idx < HESS_DIM * HESS_DIM; idx += WARP_SIZE) {
        int r = idx / HESS_DIM;
        int c = idx % HESS_DIM;
        H_out[offset + idx] = s_H[warp_in_block][r][c];
        Q_out[offset + idx] = s_Q[warp_in_block][r][c];
    }
}

extern "C" void launch_fused_blackwell_bit_hessenberg(
    const float* A_in,
    float* H_out,
    float* Q_out,
    int batch_size,
    cudaStream_t stream
) {
    int threads_per_block = 128; // 4 warps per block
    int warps_per_block = threads_per_block / WARP_SIZE;
    int num_blocks = (batch_size + warps_per_block - 1) / warps_per_block;

    fused_blackwell_bit_hessenberg_kernel<<<num_blocks, threads_per_block, 0, stream>>>(
        A_in, H_out, Q_out, batch_size
    );
}
