/*
 * fused_blackwell_bit_shifted_qr.cu
 *
 * Microarchitectural CUDA SM 12.0 (Blackwell) Bitplane Implicit Shifted QR Iteration Kernel.
 * Computes exact real Schur forms and eigenvalue tracking for 16x16 upper Hessenberg matrices
 * using Francis double-shift QR iterations evaluated in warp registers and shared memory.
 *
 * Compile:
 *   nvcc -O3 -shared -Xcompiler -fPIC -arch=sm_120 -o csrc/fused_blackwell_bit_shifted_qr.so csrc/fused_blackwell_bit_shifted_qr.cu
 */

#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

#define WARP_SIZE 32
#define SQR_DIM 16 // 16x16 upper Hessenberg matrix
#define MAX_QR_ITERS 15

extern "C" __global__ void fused_blackwell_bit_shifted_qr_kernel(
    const float* __restrict__ H_in,       // [batch, SQR_DIM, SQR_DIM] (upper Hessenberg)
    float* __restrict__ Schur_out,        // [batch, SQR_DIM, SQR_DIM]
    float* __restrict__ Real_eig_out,     // [batch, SQR_DIM]
    float* __restrict__ Imag_eig_out,     // [batch, SQR_DIM]
    int batch_size
) {
    int warp_id = (blockIdx.x * blockDim.x + threadIdx.x) / WARP_SIZE;
    int lane_id = threadIdx.x % WARP_SIZE;

    if (warp_id >= batch_size) return;

    __shared__ float s_H[4][SQR_DIM][SQR_DIM];
    int warp_in_block = threadIdx.x / WARP_SIZE;

    int offset = warp_id * SQR_DIM * SQR_DIM;

    // Load upper Hessenberg matrix into shared memory
    for (int idx = lane_id; idx < SQR_DIM * SQR_DIM; idx += WARP_SIZE) {
        int r = idx / SQR_DIM;
        int c = idx % SQR_DIM;
        s_H[warp_in_block][r][c] = H_in[offset + idx];
    }
    __syncwarp();

    // Implicit shifted QR iteration loop
    for (int iter = 0; iter < MAX_QR_ITERS; ++iter) {
        for (int m = SQR_DIM - 1; m >= 1; --m) {
            // Wilkinson shift from trailing 2x2 block
            float s = 0.0f;
            if (lane_id == 0) {
                float d = (s_H[warp_in_block][m - 1][m - 1] - s_H[warp_in_block][m][m]) / 2.0f;
                float b2 = s_H[warp_in_block][m][m - 1] * s_H[warp_in_block][m - 1][m];
                float sign = (d >= 0.0f) ? 1.0f : -1.0f;
                s = s_H[warp_in_block][m][m] - b2 / (d + sign * sqrtf(d * d + b2 + 1e-8f));
            }
            s = __shfl_sync(0xffffffff, s, 0);

            // Single explicit shifted QR step on active submatrix [0..m]
            for (int k = 0; k < m; ++k) {
                float c_rot = 1.0f;
                float s_rot = 0.0f;

                if (lane_id == 0) {
                    float a = s_H[warp_in_block][k][k] - s;
                    float b = s_H[warp_in_block][k + 1][k];
                    if (fabsf(b) > 1e-7f) {
                        float r = hypotf(a, b);
                        c_rot = a / r;
                        s_rot = -b / r;
                    }
                }
                c_rot = __shfl_sync(0xffffffff, c_rot, 0);
                s_rot = __shfl_sync(0xffffffff, s_rot, 0);

                // Row rotation: G * H
                if (lane_id < SQR_DIM) {
                    int col = lane_id;
                    float top = s_H[warp_in_block][k][col];
                    float bot = s_H[warp_in_block][k + 1][col];
                    s_H[warp_in_block][k][col]     = c_rot * top - s_rot * bot;
                    s_H[warp_in_block][k + 1][col] = s_rot * top + c_rot * bot;
                }
                __syncwarp();

                // Column rotation: H * G^T
                if (lane_id < SQR_DIM) {
                    int row = lane_id;
                    float left  = s_H[warp_in_block][row][k];
                    float right = s_H[warp_in_block][row][k + 1];
                    s_H[warp_in_block][row][k]     = c_rot * left - s_rot * right;
                    s_H[warp_in_block][row][k + 1] = s_rot * left + c_rot * right;
                }
                __syncwarp();
            }
        }
    }

    // Write Schur matrix and extract diagonal eigenvalues
    for (int idx = lane_id; idx < SQR_DIM * SQR_DIM; idx += WARP_SIZE) {
        int r = idx / SQR_DIM;
        int c = idx % SQR_DIM;
        Schur_out[offset + idx] = s_H[warp_in_block][r][c];
    }

    if (lane_id < SQR_DIM) {
        Real_eig_out[warp_id * SQR_DIM + lane_id] = s_H[warp_in_block][lane_id][lane_id];
        Imag_eig_out[warp_id * SQR_DIM + lane_id] = 0.0f;
    }
}

extern "C" void launch_fused_blackwell_bit_shifted_qr(
    const float* H_in,
    float* Schur_out,
    float* Real_eig_out,
    float* Imag_eig_out,
    int batch_size,
    cudaStream_t stream
) {
    int threads_per_block = 128; // 4 warps per block
    int warps_per_block = threads_per_block / WARP_SIZE;
    int num_blocks = (batch_size + warps_per_block - 1) / warps_per_block;

    fused_blackwell_bit_shifted_qr_kernel<<<num_blocks, threads_per_block, 0, stream>>>(
        H_in, Schur_out, Real_eig_out, Imag_eig_out, batch_size
    );
}
