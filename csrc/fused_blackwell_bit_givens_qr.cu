/*
 * fused_blackwell_bit_givens_qr.cu
 *
 * Microarchitectural CUDA SM 12.0 (Blackwell) Bitplane Givens-QR Decomposition Kernel.
 * Computes exact orthogonal-triangular factorizations (A = Q * R) for 16x16 representation
 * matrices using in-register Givens plane rotations and hardware hypotf primitives.
 *
 * Compile:
 *   nvcc -O3 -shared -Xcompiler -fPIC -arch=sm_120 -o csrc/fused_blackwell_bit_givens_qr.so csrc/fused_blackwell_bit_givens_qr.cu
 */

#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

#define WARP_SIZE 32
#define QR_DIM 16 // 16x16 matrices (256 floats per matrix)

extern "C" __global__ void fused_blackwell_bit_givens_qr_kernel(
    const float* __restrict__ A_in,       // [batch, QR_DIM, QR_DIM]
    float* __restrict__ Q_out,            // [batch, QR_DIM, QR_DIM]
    float* __restrict__ R_out,            // [batch, QR_DIM, QR_DIM]
    int batch_size
) {
    int warp_id = (blockIdx.x * blockDim.x + threadIdx.x) / WARP_SIZE;
    int lane_id = threadIdx.x % WARP_SIZE;

    if (warp_id >= batch_size) return;

    // Shared memory staging for 16x16 matrix (2 warps per block)
    __shared__ float s_R[4][QR_DIM][QR_DIM];
    __shared__ float s_Q[4][QR_DIM][QR_DIM];
    int warp_in_block = threadIdx.x / WARP_SIZE;

    int offset = warp_id * QR_DIM * QR_DIM;

    // Load A into s_R and initialize s_Q as identity (each lane loads 8 floats)
    for (int idx = lane_id; idx < QR_DIM * QR_DIM; idx += WARP_SIZE) {
        int r = idx / QR_DIM;
        int c = idx % QR_DIM;
        s_R[warp_in_block][r][c] = A_in[offset + idx];
        s_Q[warp_in_block][r][c] = (r == c) ? 1.0f : 0.0f;
    }
    __syncwarp();

    // Givens rotations: zero out elements below diagonal column by column
    for (int j = 0; j < QR_DIM - 1; ++j) {
        for (int i = QR_DIM - 1; i > j; --i) {
            float c_rot = 1.0f;
            float s_rot = 0.0f;

            if (lane_id == 0) {
                float a = s_R[warp_in_block][i - 1][j];
                float b = s_R[warp_in_block][i][j];
                if (fabsf(b) > 1e-7f) {
                    float r = hypotf(a, b);
                    c_rot = a / r;
                    s_rot = -b / r;
                }
            }

            // Broadcast rotation parameters across warp
            c_rot = __shfl_sync(0xffffffff, c_rot, 0);
            s_rot = __shfl_sync(0xffffffff, s_rot, 0);

            // Apply rotation to rows i-1 and i in R
            if (lane_id < QR_DIM) {
                int col = lane_id;
                float top = s_R[warp_in_block][i - 1][col];
                float bot = s_R[warp_in_block][i][col];
                s_R[warp_in_block][i - 1][col] = c_rot * top - s_rot * bot;
                s_R[warp_in_block][i][col]     = s_rot * top + c_rot * bot;
            }

            // Accumulate rotation into Q (apply to columns i-1 and i of Q)
            if (lane_id < QR_DIM) {
                int row = lane_id;
                float left  = s_Q[warp_in_block][row][i - 1];
                float right = s_Q[warp_in_block][row][i];
                s_Q[warp_in_block][row][i - 1] = c_rot * left - s_rot * right;
                s_Q[warp_in_block][row][i]     = s_rot * left + c_rot * right;
            }
            __syncwarp();
        }
    }

    // Write back Q and R
    for (int idx = lane_id; idx < QR_DIM * QR_DIM; idx += WARP_SIZE) {
        int r = idx / QR_DIM;
        int c = idx % QR_DIM;
        Q_out[offset + idx] = s_Q[warp_in_block][r][c];
        R_out[offset + idx] = s_R[warp_in_block][r][c];
    }
}

extern "C" void launch_fused_blackwell_bit_givens_qr(
    const float* A_in,
    float* Q_out,
    float* R_out,
    int batch_size,
    cudaStream_t stream
) {
    int threads_per_block = 128; // 4 warps per block
    int warps_per_block = threads_per_block / WARP_SIZE;
    int num_blocks = (batch_size + warps_per_block - 1) / warps_per_block;

    fused_blackwell_bit_givens_qr_kernel<<<num_blocks, threads_per_block, 0, stream>>>(
        A_in, Q_out, R_out, batch_size
    );
}
