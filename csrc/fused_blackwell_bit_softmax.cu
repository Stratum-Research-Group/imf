#include <cuda_runtime.h>
#include <stdint.h>
#include <math.h>

#define WARP_SIZE 32

// In-register bitplane softmax: computes softmax over packed bitplane logits
// Each 32-bit word encodes 32 binary states or two 16-state channels.
// We map bit-density to approximate logit values, compute maximum, subtract,
// and exponentiate in-register using warp shuffles.

__device__ __forceinline__ float warp_reduce_max(float val) {
    #pragma unroll
    for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
        val = fmaxf(val, __shfl_xor_sync(0xffffffff, val, offset));
    }
    return val;
}

__device__ __forceinline__ float warp_reduce_sum(float val) {
    #pragma unroll
    for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
        val += __shfl_xor_sync(0xffffffff, val, offset);
    }
    return val;
}

extern "C" __global__ void fused_blackwell_bit_softmax_kernel(
    const uint32_t* __restrict__ bit_logits,
    float* __restrict__ softmax_probs,
    int num_rows,
    int words_per_row,
    float temperature
) {
    int row = blockIdx.x;
    if (row >= num_rows) return;

    int lane_id = threadIdx.x % WARP_SIZE;
    int warp_id = threadIdx.x / WARP_SIZE;
    if (warp_id > 0) return; // 1 warp per row for low-latency reduction

    float local_val = 0.0f;
    if (lane_id < words_per_row) {
        uint32_t word = bit_logits[row * words_per_row + lane_id];
        // Popcount maps binary excitation to relative raw energy level
        int count = __popc(word);
        local_val = ((float)count - 16.0f) / temperature;
    } else {
        local_val = -1e20f;
    }

    float max_val = warp_reduce_max(local_val);
    float exp_val = (lane_id < words_per_row) ? __expf(local_val - max_val) : 0.0f;
    float sum_exp = warp_reduce_sum(exp_val);

    float inv_sum = (sum_exp > 1e-12f) ? (1.0f / sum_exp) : 0.0f;

    if (lane_id < words_per_row) {
        softmax_probs[row * words_per_row + lane_id] = exp_val * inv_sum;
    }
}
