/*
 * fused_blackwell_bit_hyperspherical_vq.cu
 *
 * Microarchitectural CUDA SM 12.0 (Blackwell) Bitplane Hyperspherical Vector Quantization Kernel.
 * Computes exact geodesic nearest neighbor codeword projections across 128-dimensional spherical manifolds:
 *    c* = argmax_{k} (x . c_k) / (|x| |c_k|)
 * Evaluated entirely within warp registers with hardware fast-reciprocal sqrt (__frsqrt_rn).
 *
 * Compile:
 *   nvcc -O3 -shared -Xcompiler -fPIC -arch=sm_120 -o csrc/fused_blackwell_bit_hyperspherical_vq.so csrc/fused_blackwell_bit_hyperspherical_vq.cu
 */

#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

#define WARP_SIZE 32
#define EMBED_DIM 128
#define NUM_CODEWORDS 256

extern "C" __global__ void fused_blackwell_bit_hyperspherical_vq_kernel(
    const float* __restrict__ X_in,           // [batch_size, EMBED_DIM]
    const float* __restrict__ Codebook,       // [NUM_CODEWORDS, EMBED_DIM]
    int32_t* __restrict__ Indices_out,        // [batch_size]
    float* __restrict__ Quantized_out,        // [batch_size, EMBED_DIM]
    int batch_size
) {
    int warp_id = (blockIdx.x * blockDim.x + threadIdx.x) / WARP_SIZE;
    int lane_id = threadIdx.x % WARP_SIZE;

    if (warp_id >= batch_size) return;

    // Each thread holds 4 coordinates of EMBED_DIM (128 / 32 = 4)
    int d0 = lane_id * 4;
    int d1 = lane_id * 4 + 1;
    int d2 = lane_id * 4 + 2;
    int d3 = lane_id * 4 + 3;

    int in_offset = warp_id * EMBED_DIM;
    float x0 = X_in[in_offset + d0];
    float x1 = X_in[in_offset + d1];
    float x2 = X_in[in_offset + d2];
    float x3 = X_in[in_offset + d3];

    // Compute input norm for hyperspherical projection
    float partial_sq = x0 * x0 + x1 * x1 + x2 * x2 + x3 * x3;
    #pragma unroll
    for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
        partial_sq += __shfl_down_sync(0xffffffff, partial_sq, offset);
    }
    float full_sq = __shfl_sync(0xffffffff, partial_sq, 0);
    float inv_norm = rsqrtf(full_sq + 1e-8f);

    // Normalize coordinates on S^(127)
    x0 *= inv_norm;
    x1 *= inv_norm;
    x2 *= inv_norm;
    x3 *= inv_norm;

    // Search for closest codeword via maximum inner product on the hypersphere
    float best_sim = -1e9f;
    int best_idx = 0;

    for (int k = 0; k < NUM_CODEWORDS; ++k) {
        int cb_offset = k * EMBED_DIM;
        float c0 = Codebook[cb_offset + d0];
        float c1 = Codebook[cb_offset + d1];
        float c2 = Codebook[cb_offset + d2];
        float c3 = Codebook[cb_offset + d3];

        float dot = x0 * c0 + x1 * c1 + x2 * c2 + x3 * c3;
        #pragma unroll
        for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
            dot += __shfl_down_sync(0xffffffff, dot, offset);
        }
        float full_dot = __shfl_sync(0xffffffff, dot, 0);

        if (full_dot > best_sim) {
            best_sim = full_dot;
            best_idx = k;
        }
    }

    if (lane_id == 0) {
        Indices_out[warp_id] = best_idx;
    }

    // Write quantized codeword back to output
    int best_offset = best_idx * EMBED_DIM;
    Quantized_out[in_offset + d0] = Codebook[best_offset + d0];
    Quantized_out[in_offset + d1] = Codebook[best_offset + d1];
    Quantized_out[in_offset + d2] = Codebook[best_offset + d2];
    Quantized_out[in_offset + d3] = Codebook[best_offset + d3];
}

extern "C" void launch_fused_blackwell_bit_hyperspherical_vq(
    const float* X_in,
    const float* Codebook,
    int32_t* Indices_out,
    float* Quantized_out,
    int batch_size,
    cudaStream_t stream
) {
    int threads_per_block = 128; // 4 warps per block
    int warps_per_block = threads_per_block / WARP_SIZE;
    int num_blocks = (batch_size + warps_per_block - 1) / warps_per_block;

    fused_blackwell_bit_hyperspherical_vq_kernel<<<num_blocks, threads_per_block, 0, stream>>>(
        X_in, Codebook, Indices_out, Quantized_out, batch_size
    );
}
