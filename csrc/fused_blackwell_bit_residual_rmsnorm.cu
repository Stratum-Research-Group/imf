#include <cuda_runtime.h>
#include <stdint.h>
#include <math.h>

#define WARP_SIZE 32

// Fused in-register Bit-Level Residual Addition and RMSNorm
// Adds residual bitplane (or FP16 equivalent) to incoming bitplanes and computes
// RMS normalization directly in warp registers using __popc and __shfl_xor_sync.

__device__ __forceinline__ float warp_reduce_sum(float val) {
    #pragma unroll
    for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
        val += __shfl_xor_sync(0xffffffff, val, offset);
    }
    return val;
}

extern "C" __global__ void fused_blackwell_bit_residual_rmsnorm_kernel(
    const uint32_t* __restrict__ input_bits,
    const uint32_t* __restrict__ residual_bits,
    const float* __restrict__ gamma_scale,
    float* __restrict__ output_normed,
    int num_rows,
    int words_per_row,
    float epsilon
) {
    int row = blockIdx.x;
    if (row >= num_rows) return;

    int lane_id = threadIdx.x % WARP_SIZE;
    int warp_id = threadIdx.x / WARP_SIZE;
    if (warp_id > 0) return; // 1 warp per row

    float local_val = 0.0f;
    if (lane_id < words_per_row) {
        uint32_t in_w = input_bits[row * words_per_row + lane_id];
        uint32_t res_w = residual_bits[row * words_per_row + lane_id];
        
        // Ternary residual addition: combine bit excitations
        int count_in = __popc(in_w) - 16;
        int count_res = __popc(res_w) - 16;
        local_val = (float)(count_in + count_res);
    }

    float local_sq = local_val * local_val;
    float sum_sq = warp_reduce_sum(local_sq);
    float rms = rsqrtf((sum_sq / (float)words_per_row) + epsilon);

    if (lane_id < words_per_row) {
        float gamma = gamma_scale ? gamma_scale[lane_id] : 1.0f;
        output_normed[row * words_per_row + lane_id] = local_val * rms * gamma;
    }
}
