#include <cuda_runtime.h>
#include <stdint.h>

// Microarchitecture: Fused Blackwell Sub-Byte Bit-Level Convolutional Shift Kernel
// Hardware Target: NVIDIA GeForce RTX 5060 Ti (Blackwell SM 12.0)
// Evaluates 1D temporal convolutions directly over 1-bit packed binary state words
// using hardware 64-bit funnel shift intrinsics (__funnelshift_r).

extern "C" __global__ void fused_blackwell_bit_conv_kernel(
    const uint32_t* __restrict__ in_bitstream,   // Packed 1-bit input sequence [N_words]
    const uint32_t* __restrict__ conv_kernel,    // Convolution filter masks [K_words]
    int32_t* __restrict__ out_accum,             // Accumulated correlation outputs [N_words]
    int N_words,
    int K_words
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= N_words) return;

    int32_t local_sum = 0;
    uint32_t curr_word = in_bitstream[idx];
    uint32_t next_word = (idx + 1 < N_words) ? in_bitstream[idx + 1] : 0;

    #pragma unroll
    for (int k = 0; k < K_words; ++k) {
        uint32_t filter = conv_kernel[k];
        // Shift window by k bits across word boundary using funnel shift
        uint32_t shifted = __funnelshift_r(curr_word, next_word, k);

        // Bitwise correlation: +1 for matching bit, -1 for mismatching bit
        uint32_t matches = ~(shifted ^ filter);
        int match_count = __popc(matches);
        int mismatch_count = 32 - match_count;

        local_sum += (match_count - mismatch_count);
    }

    out_accum[idx] = local_sum;
}
