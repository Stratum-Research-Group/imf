/*
 * fused_blackwell_bit_syrk.cu
 *
 * Microarchitectural CUDA SM 12.0 (Blackwell) Bitplane Symmetric Rank-K Update Kernel.
 * Computes in-register symmetric rank-k updates:
 *    C = alpha * A * A^T + beta * C
 * for covariance accumulation directly from 2-bit unpacked bitplane streams.
 *
 * Compile:
 *   nvcc -O3 -shared -Xcompiler -fPIC -arch=sm_120 -o csrc/fused_blackwell_bit_syrk.so csrc/fused_blackwell_bit_syrk.cu
 */

#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>

#define WARP_SIZE 32
#define SYRK_N 16 // 16x16 symmetric matrix

extern "C" __global__ void fused_blackwell_bit_syrk_kernel(
    const uint8_t* __restrict__ Bitplane_A, // [batch, K / 4, SYRK_N]
    const float* __restrict__ Scale_LUT,    // [4]
    float* __restrict__ C_out,              // [batch, SYRK_N, SYRK_N]
    int batch_size,
    int K,
    float alpha,
    float beta
) {
    int warp_id = (blockIdx.x * blockDim.x + threadIdx.x) / WARP_SIZE;
    int lane_id = threadIdx.x % WARP_SIZE;

    if (warp_id >= batch_size) return;

    // Staging symmetric matrix in shared memory
    __shared__ float s_C[4][SYRK_N][SYRK_N];
    int warp_in_block = threadIdx.x / WARP_SIZE;

    int c_offset = warp_id * SYRK_N * SYRK_N;

    // Initialize s_C with scaled beta * C_in (or 0 if beta == 0)
    for (int idx = lane_id; idx < SYRK_N * SYRK_N; idx += WARP_SIZE) {
        int r = idx / SYRK_N;
        int c = idx % SYRK_N;
        s_C[warp_in_block][r][c] = (beta != 0.0f) ? beta * C_out[c_offset + idx] : 0.0f;
    }
    __syncwarp();

    // Iterate over dimension K in chunks of 4 (one byte per matrix row)
    int num_bytes_k = K / 4;
    for (int byte_k = 0; byte_k < num_bytes_k; ++byte_k) {
        // Unpack 4 inner products across rank-k
        for (int p = 0; p < 4; ++p) {
            int bit_shift = p * 2;

            // Load row vector for this inner step into registers
            float a_vec[SYRK_N];
            for (int r = 0; r < SYRK_N; ++r) {
                int byte_idx = (warp_id * num_bytes_k + byte_k) * SYRK_N + r;
                uint8_t pack = Bitplane_A[byte_idx];
                uint8_t sym = (pack >> bit_shift) & 0x03;
                a_vec[r] = Scale_LUT[sym];
            }

            // Accumulate outer product A * A^T into symmetric matrix
            // Each lane updates a subset of lower-triangular coordinates
            for (int idx = lane_id; idx < (SYRK_N * (SYRK_N + 1)) / 2; idx += WARP_SIZE) {
                // Map linear index to lower triangular (r, c)
                int r = 0;
                int c = idx;
                while (c > r) {
                    c -= (r + 1);
                    r++;
                }
                float prod = alpha * a_vec[r] * a_vec[c];
                s_C[warp_in_block][r][c] += prod;
                if (r != c) {
                    s_C[warp_in_block][c][r] += prod;
                }
            }
            __syncwarp();
        }
    }

    // Write back result
    for (int idx = lane_id; idx < SYRK_N * SYRK_N; idx += WARP_SIZE) {
        int r = idx / SYRK_N;
        int c = idx % SYRK_N;
        C_out[c_offset + idx] = s_C[warp_in_block][r][c];
    }
}

extern "C" void launch_fused_blackwell_bit_syrk(
    const uint8_t* Bitplane_A,
    const float* Scale_LUT,
    float* C_out,
    int batch_size,
    int K,
    float alpha,
    float beta,
    cudaStream_t stream
) {
    int threads_per_block = 128; // 4 warps per block
    int warps_per_block = threads_per_block / WARP_SIZE;
    int num_blocks = (batch_size + warps_per_block - 1) / warps_per_block;

    fused_blackwell_bit_syrk_kernel<<<num_blocks, threads_per_block, 0, stream>>>(
        Bitplane_A, Scale_LUT, C_out, batch_size, K, alpha, beta
    );
}
