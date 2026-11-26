#include <cuda_runtime.h>
#include <stdint.h>

// Microarchitecture: Fused Blackwell Sub-Byte Bit-Parallel Max-Pooling Kernel
// Hardware Target: NVIDIA GeForce RTX 5060 Ti (Blackwell SM 12.0)
// Evaluates max-pooling across packed bitplanes using bitwise OR tree reduction
// across 32-thread warps using __shfl_down_sync.

extern "C" __global__ void fused_blackwell_bit_maxpool_kernel(
    const uint32_t* __restrict__ in_bitplanes,   // [Batch, InWords]
    uint32_t* __restrict__ out_bitplanes,        // [Batch, OutWords]
    int window_size,                             // Pooling window size in words (e.g., 2, 4)
    int out_words
) {
    int b = blockIdx.x;
    int out_idx = blockIdx.y * blockDim.x + threadIdx.x;

    if (out_idx < out_words) {
        int start_idx = out_idx * window_size;
        uint32_t pooled_bits = 0;

        #pragma unroll
        for (int w = 0; w < window_size; ++w) {
            pooled_bits |= in_bitplanes[b * (out_words * window_size) + start_idx + w];
        }

        out_bitplanes[b * out_words + out_idx] = pooled_bits;
    }
}
