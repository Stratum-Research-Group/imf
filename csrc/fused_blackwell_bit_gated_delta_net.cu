/*
 * fused_blackwell_bit_gated_delta_net.cu
 *
 * Microarchitectural CUDA SM 12.0 (Blackwell) Bitplane Recurrent Gated Delta-Net Kernel.
 * Computes fast in-register associative Delta-rule updates:
 *    S_t = S_{t-1} + beta_t * (v_t - S_{t-1} * k_t) (x) k_t^T
 * evaluated directly within Blackwell warp registers from 2-bit unpacked feature vectors.
 *
 * Compile:
 *   nvcc -O3 -shared -Xcompiler -fPIC -arch=sm_120 -o csrc/fused_blackwell_bit_gated_delta_net.so csrc/fused_blackwell_bit_gated_delta_net.cu
 */

#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>

#define WARP_SIZE 32
#define DELTA_DIM 16 // 16x16 state matrix S_t

extern "C" __global__ void fused_blackwell_bit_gated_delta_net_kernel(
    const uint8_t* __restrict__ Bitplane_K, // [batch, seq_len / 4, DELTA_DIM]
    const float* __restrict__ V_in,         // [batch, seq_len, DELTA_DIM]
    const float* __restrict__ Beta_in,      // [batch, seq_len] learning rates
    const float* __restrict__ Scale_LUT,    // [4]
    float* __restrict__ Out,                // [batch, seq_len, DELTA_DIM]
    int batch_size,
    int seq_len
) {
    int warp_id = (blockIdx.x * blockDim.x + threadIdx.x) / WARP_SIZE;
    int lane_id = threadIdx.x % WARP_SIZE;

    if (warp_id >= batch_size) return;

    // State matrix S_t (16x16 = 256 floats) in shared memory
    __shared__ float s_S[4][DELTA_DIM][DELTA_DIM];
    int warp_in_block = threadIdx.x / WARP_SIZE;

    // Initialize state S_0 to zeros
    for (int idx = lane_id; idx < DELTA_DIM * DELTA_DIM; idx += WARP_SIZE) {
        int r = idx / DELTA_DIM;
        int c = idx % DELTA_DIM;
        s_S[warp_in_block][r][c] = 0.0f;
    }
    __syncwarp();

    for (int t = 0; t < seq_len; ++t) {
        // Unpack key vector k_t
        int byte_idx = (warp_id * (seq_len / 4) + (t / 4)) * DELTA_DIM;
        int bit_shift = (t % 4) * 2;

        float k_vec[DELTA_DIM];
        for (int d = 0; d < DELTA_DIM; ++d) {
            uint8_t pack = Bitplane_K[byte_idx + d];
            uint8_t sym = (pack >> bit_shift) & 0x03;
            k_vec[d] = Scale_LUT[sym];
        }

        int v_offset = (warp_id * seq_len + t) * DELTA_DIM;
        float v_val = (lane_id < DELTA_DIM) ? V_in[v_offset + lane_id] : 0.0f;
        float beta = Beta_in[warp_id * seq_len + t];

        // Compute predicted memory readout: y_pred = S_{t-1} * k_t
        // Row r of S multiplied by k_vec
        float pred_r = 0.0f;
        if (lane_id < DELTA_DIM) {
            int r = lane_id;
            for (int c = 0; c < DELTA_DIM; ++c) {
                pred_r += s_S[warp_in_block][r][c] * k_vec[c];
            }
        }
        __syncwarp();

        // Error vector: err = v_t - y_pred
        float err_r = (lane_id < DELTA_DIM) ? (v_val - pred_r) : 0.0f;

        // Delta-rule update: S_t = S_{t-1} + beta * (err) (x) k_t^T
        for (int idx = lane_id; idx < DELTA_DIM * DELTA_DIM; idx += WARP_SIZE) {
            int r = idx / DELTA_DIM;
            int c = idx % DELTA_DIM;
            s_S[warp_in_block][r][c] += beta * err_r * k_vec[c];
        }
        __syncwarp();

        // Write output readout
        if (lane_id < DELTA_DIM) {
            Out[v_offset + lane_id] = pred_r;
        }
    }
}

extern "C" void launch_fused_blackwell_bit_gated_delta_net(
    const uint8_t* Bitplane_K,
    const float* V_in,
    const float* Beta_in,
    const float* Scale_LUT,
    float* Out,
    int batch_size,
    int seq_len,
    cudaStream_t stream
) {
    int threads_per_block = 128; // 4 warps per block
    int warps_per_block = threads_per_block / WARP_SIZE;
    int num_blocks = (batch_size + warps_per_block - 1) / warps_per_block;

    fused_blackwell_bit_gated_delta_net_kernel<<<num_blocks, threads_per_block, 0, stream>>>(
        Bitplane_K, V_in, Beta_in, Scale_LUT, Out, batch_size, seq_len
    );
}
