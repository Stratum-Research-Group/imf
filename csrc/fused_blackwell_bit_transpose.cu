#include <cuda_runtime.h>
#include <stdint.h>

// Microarchitecture: Fused Blackwell In-Register 32x32 Bit-Matrix Transpose
// Hardware Target: NVIDIA GeForce RTX 5060 Ti (Blackwell SM 12.0)
// Transposes 32 words of 32 bits across a 32-thread warp in-register
// using recursive butterfly permutation (__shfl_xor_sync) in log2(32) = 5 steps.

extern "C" __global__ void fused_blackwell_bit_transpose_kernel(
    const uint32_t* __restrict__ in_matrix,   // [Batch, 32]
    uint32_t* __restrict__ out_matrix,        // [Batch, 32]
    int batch_size
) {
    int b = blockIdx.x;
    int lane = threadIdx.x; // 32 threads per block (1 warp)

    if (b < batch_size && lane < 32) {
        uint32_t v = in_matrix[b * 32 + lane];

        // 5-stage butterfly transposition network
        // Stage 1: swap adjacent bits with thread partner (xor 1)
        uint32_t partner = __shfl_xor_sync(0xffffffff, v, 1);
        if (lane & 1) {
            v = (v & 0x55555555) | ((partner & 0xaaaaaaaa) >> 1);
        } else {
            v = ((partner & 0x55555555) << 1) | (v & 0xaaaaaaaa);
        }

        // Stage 2: 2-bit groups with thread partner (xor 2)
        partner = __shfl_xor_sync(0xffffffff, v, 2);
        if (lane & 2) {
            v = (v & 0x33333333) | ((partner & 0xcccccccc) >> 2);
        } else {
            v = ((partner & 0x33333333) << 2) | (v & 0xcccccccc);
        }

        // Stage 3: 4-bit groups with thread partner (xor 4)
        partner = __shfl_xor_sync(0xffffffff, v, 4);
        if (lane & 4) {
            v = (v & 0x0f0f0f0f) | ((partner & 0xf0f0f0f0) >> 4);
        } else {
            v = ((partner & 0x0f0f0f0f) << 4) | (v & 0xf0f0f0f0);
        }

        // Stage 4: 8-bit groups with thread partner (xor 8)
        partner = __shfl_xor_sync(0xffffffff, v, 8);
        if (lane & 8) {
            v = (v & 0x00ff00ff) | ((partner & 0xff00ff00) >> 8);
        } else {
            v = ((partner & 0x00ff00ff) << 8) | (v & 0xff00ff00);
        }

        // Stage 5: 16-bit groups with thread partner (xor 16)
        partner = __shfl_xor_sync(0xffffffff, v, 16);
        if (lane & 16) {
            v = (v & 0x0000ffff) | ((partner & 0xffff0000) >> 16);
        } else {
            v = ((partner & 0x0000ffff) << 16) | (v & 0xffff0000);
        }

        out_matrix[b * 32 + lane] = v;
    }
}
