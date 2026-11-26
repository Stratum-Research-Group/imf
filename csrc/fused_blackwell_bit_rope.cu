#include <cuda_runtime.h>
#include <stdint.h>
#include <math.h>

#define WARP_SIZE 32

// In-register Bit-Level Rotary Position Embedding (RoPE)
// Rotates adjacent 2D orthogonal channels within packed bitplanes:
// [x1', x2']^T = [cos θ  -sin θ; sin θ  cos θ] * [x1, x2]^T
// Executes directly in warp registers using __popc and trigonometric intrinsics.

extern "C" __global__ void fused_blackwell_bit_rope_kernel(
    const uint32_t* __restrict__ in_bits,
    float* __restrict__ out_rotated,
    int num_rows,
    int words_per_row,
    float base_freq
) {
    int row = blockIdx.x;
    if (row >= num_rows) return;

    int lane_id = threadIdx.x % WARP_SIZE;
    int warp_id = threadIdx.x / WARP_SIZE;
    if (warp_id > 0) return; // 1 warp per row

    // Pair adjacent lanes as complex/2D coordinates (even = real, odd = imag)
    if (lane_id < words_per_row) {
        int pair_idx = lane_id / 2;
        int is_odd = lane_id % 2;

        uint32_t w_self = in_bits[row * words_per_row + lane_id];
        float val_self = (float)(__popc(w_self) - 16);

        // Fetch sibling lane value via warp shuffle
        int sibling_lane = is_odd ? (lane_id - 1) : (lane_id + 1);
        uint32_t w_sibling = __shfl_sync(0xffffffff, in_bits[row * words_per_row + sibling_lane], sibling_lane);
        float val_sibling = (float)(__popc(w_sibling) - 16);

        // RoPE frequency modulation: theta = pos / (base_freq ^ (2 * pair_idx / dim))
        float freq = 1.0f / powf(base_freq, (float)(2 * pair_idx) / (float)words_per_row);
        float theta = (float)row * freq;

        float cos_theta = __cosf(theta);
        float sin_theta = __sinf(theta);

        float rotated_val = 0.0f;
        if (!is_odd) {
            // Even lane: x1' = x1 * cos - x2 * sin
            rotated_val = val_self * cos_theta - val_sibling * sin_theta;
        } else {
            // Odd lane: x2' = x1 * sin + x2 * cos
            rotated_val = val_sibling * sin_theta + val_self * cos_theta;
        }

        out_rotated[row * words_per_row + lane_id] = rotated_val;
    }
}
