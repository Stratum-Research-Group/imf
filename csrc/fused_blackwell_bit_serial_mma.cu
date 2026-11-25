#include <cuda_runtime.h>
#include <stdint.h>

// Microarchitecture: Fused Blackwell Sub-Byte Bit-Serial Matrix Multiply-Accumulate
// Hardware Target: NVIDIA GeForce RTX 5060 Ti (Blackwell SM 12.0)
// Accumulates arbitrary precision bit-planes (b0, b1) via bitwise AND and hardware popcount,
// dynamically weighting bit-planes as C = sum_{k} 2^k * popc(A_k & B_k).

extern "C" __global__ void fused_blackwell_bit_serial_mma_kernel(
    const uint32_t* __restrict__ A_plane0,  // Matrix A bitplane 0 (least significant bit)
    const uint32_t* __restrict__ A_plane1,  // Matrix A bitplane 1 (most significant bit)
    const uint32_t* __restrict__ B_plane0,  // Matrix B bitplane 0
    const uint32_t* __restrict__ B_plane1,  // Matrix B bitplane 1
    int32_t* __restrict__ C_out,            // Accumulated output vector/matrix
    int N                                   // Length in 32-bit words
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int stride = blockDim.x * gridDim.x;

    int32_t local_accum = 0;

    for (int i = idx; i < N; i += stride) {
        uint32_t a0 = A_plane0[i];
        uint32_t a1 = A_plane1[i];
        uint32_t b0 = B_plane0[i];
        uint32_t b1 = B_plane1[i];

        // 2-bit x 2-bit expansion:
        // (2*a1 + a0) * (2*b1 + b0) = 4*(a1 & b1) + 2*(a1 & b0 + a0 & b1) + 1*(a0 & b0)
        uint32_t p00 = a0 & b0;
        uint32_t p01 = a0 & b1;
        uint32_t p10 = a1 & b0;
        uint32_t p11 = a1 & b1;

        int c00 = __popc(p00);
        int c01 = __popc(p01);
        int c10 = __popc(p10);
        int c11 = __popc(p11);

        local_accum += (c00 * 1) + ((c01 + c10) * 2) + (c11 * 4);
    }

    // Warp-level reduction
    for (int offset = 16; offset > 0; offset /= 2) {
        local_accum += __shfl_down_sync(0xffffffff, local_accum, offset);
    }

    if ((threadIdx.x & 31) == 0) {
        atomicAdd(C_out, local_accum);
    }
}
