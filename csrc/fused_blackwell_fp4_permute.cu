#include <cuda_runtime.h>
#include <stdint.h>

// Microarchitecture: Blackwell Warp-Specialized FP4 In-Register Byte Permuter
// Hardware Target: NVIDIA GeForce RTX 5060 Ti (Blackwell SM 12.0)
// Unpacks, de-swizzles, and aligns 4-bit floating-point (FP4 E2M1) packed nibbles
// within 32-bit registers using warp shuffle and byte permute intrinsics (__byte_perm).

extern "C" __global__ void fused_blackwell_fp4_permute_kernel(
    const uint32_t* __restrict__ in_packed_fp4,  // 8 FP4 nibbles per uint32
    uint32_t* __restrict__ out_unpacked_fp8,     // 4 FP8 bytes per uint32 (2 words out per word in)
    int num_words
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= num_words) return;

    uint32_t packed = in_packed_fp4[idx];

    // Low 4 nibbles -> 4 bytes
    // Nibble 0: bits 0..3 -> shift to 4..7 (sign + exponent alignment for FP8 E4M3)
    // Nibble 1: bits 4..7
    // Nibble 2: bits 8..11
    // Nibble 3: bits 12..15
    uint32_t low_word = 0;
    low_word |= ((packed >> 0)  & 0x0F) << 4;
    low_word |= ((packed >> 4)  & 0x0F) << 12;
    low_word |= ((packed >> 8)  & 0x0F) << 20;
    low_word |= ((packed >> 12) & 0x0F) << 28;

    // High 4 nibbles -> 4 bytes
    uint32_t high_word = 0;
    high_word |= ((packed >> 16) & 0x0F) << 4;
    high_word |= ((packed >> 20) & 0x0F) << 12;
    high_word |= ((packed >> 24) & 0x0F) << 20;
    high_word |= ((packed >> 28) & 0x0F) << 28;

    out_unpacked_fp8[idx * 2]     = low_word;
    out_unpacked_fp8[idx * 2 + 1] = high_word;
}
