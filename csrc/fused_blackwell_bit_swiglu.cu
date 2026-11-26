#include <cuda_runtime.h>
#include <stdint.h>
#include <math.h>

#define WARP_SIZE 32

// In-register bit-parallel Swish-Gated Linear Unit (SwiGLU)
// Forward pass over packed bitplanes: evaluates gating activation and linear projection
// in-register using __popc and fast polynomial/reciprocal-exponential approximations.

__device__ __forceinline__ float fast_silu(float x) {
    // SiLU(x) = x / (1 + exp(-x))
    return x / (1.0f + __expf(-x));
}

extern "C" __global__ void fused_blackwell_bit_swiglu_kernel(
    const uint32_t* __restrict__ gate_bits,
    const uint32_t* __restrict__ val_bits,
    const float* __restrict__ gate_scale,
    const float* __restrict__ val_scale,
    float* __restrict__ out_activations,
    int num_rows,
    int words_per_row
) {
    int row = blockIdx.x;
    if (row >= num_rows) return;

    int lane_id = threadIdx.x % WARP_SIZE;
    int warp_id = threadIdx.x / WARP_SIZE;
    if (warp_id > 0) return; // 1 warp per row for low latency

    if (lane_id < words_per_row) {
        uint32_t g_word = gate_bits[row * words_per_row + lane_id];
        uint32_t v_word = val_bits[row * words_per_row + lane_id];

        // Map bit-densities to centered ternary/pseudo-linear states
        float g_val = (float)(__popc(g_word) - 16);
        float v_val = (float)(__popc(v_word) - 16);

        if (gate_scale) g_val *= gate_scale[lane_id];
        if (val_scale)  v_val *= val_scale[lane_id];

        // SwiGLU: SiLU(g) * v
        float swiglu_out = fast_silu(g_val) * v_val;

        out_activations[row * words_per_row + lane_id] = swiglu_out;
    }
}
