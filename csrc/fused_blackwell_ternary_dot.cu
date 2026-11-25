#include <cuda_runtime.h>
#include <stdint.h>

// Microarchitecture: Sub-Byte 0.58-bit Ternary Dot Product
// Hardware Target: NVIDIA GeForce RTX 5060 Ti (Blackwell SM 12.0)
// Representation: 2-bit packed ternary (-1, 0, +1):
// 00b = 0, 01b = +1, 11b = -1.
// 16 ternary values per uint32_t register.
// Accumulation via native bitwise masking and __popc (popcount) instructions.

extern "C" __global__ void fused_blackwell_ternary_dot_kernel(
    const uint32_t* __restrict__ A_pos,    // Positive bits mask
    const uint32_t* __restrict__ A_neg,    // Negative bits mask
    const uint32_t* __restrict__ B_pos,    // Activation positive sign mask
    const uint32_t* __restrict__ B_neg,    // Activation negative sign mask
    int32_t* __restrict__ C,               // Accumulated output
    int N                                  // Vector length in 32-bit words
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int stride = blockDim.x * gridDim.x;

    int32_t local_accum = 0;

    for (int i = idx; i < N; i += stride) {
        uint32_t a_p = A_pos[i];
        uint32_t a_n = A_neg[i];
        uint32_t b_p = B_pos[i];
        uint32_t b_n = B_neg[i];

        // +1 * +1 = +1
        // -1 * -1 = +1
        // +1 * -1 = -1
        // -1 * +1 = -1
        // Any with 0 = 0
        uint32_t matches_pos = (a_p & b_p) | (a_n & b_n);
        uint32_t matches_neg = (a_p & b_n) | (a_n & b_p);

        int pos_count = __popc(matches_pos);
        int neg_count = __popc(matches_neg);

        local_accum += (pos_count - neg_count);
    }

    // Warp-level reduction using ballot/shfl
    for (int offset = 16; offset > 0; offset /= 2) {
        local_accum += __shfl_down_sync(0xffffffff, local_accum, offset);
    }

    if ((threadIdx.x & 31) == 0) {
        atomicAdd(C, local_accum);
    }
}
