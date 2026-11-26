#include <cuda_runtime.h>
#include <stdint.h>
#include <math.h>

// Microarchitecture: Fused Blackwell Bit-Packed Activation Quantizer
// Hardware Target: NVIDIA GeForce RTX 5060 Ti (Blackwell SM 12.0)
// Evaluates non-linear activation (GELU/ReLU) and quantizes/packs results
// into sub-byte bitplanes (2 bits per value: sign and magnitude threshold)
// directly within registers using ballot and warp vote intrinsics.

extern "C" __global__ void fused_blackwell_bit_activations_kernel(
    const float* __restrict__ in_acts,         // Continuous input activations [N]
    uint32_t* __restrict__ out_packed_plane0,   // Packed bitplane 0 (magnitude threshold)
    uint32_t* __restrict__ out_packed_plane1,   // Packed bitplane 1 (sign / polarity)
    int N_elements
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int lane = threadIdx.x & 31;

    float val = (idx < N_elements) ? in_acts[idx] : 0.0f;

    // Fast approximation of GELU: 0.5 * x * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
    float gelu_val = 0.5f * val * (1.0f + tanhf(0.79788456f * (val + 0.044715f * val * val * val)));

    // Quantize into 2-bit discrete states:
    // Bit 0: absolute magnitude > 0.5f threshold
    // Bit 1: sign bit (positive vs negative)
    bool bit0 = fabsf(gelu_val) > 0.5f;
    bool bit1 = gelu_val > 0.0f;

    // Pack across 32 threads in warp into single uint32 per bitplane
    uint32_t warp_mask0 = __ballot_sync(0xffffffff, bit0);
    uint32_t warp_mask1 = __ballot_sync(0xffffffff, bit1);

    if (lane == 0) {
        int word_idx = (blockIdx.x * blockDim.x + threadIdx.x) / 32;
        out_packed_plane0[word_idx] = warp_mask0;
        out_packed_plane1[word_idx] = warp_mask1;
    }
}
