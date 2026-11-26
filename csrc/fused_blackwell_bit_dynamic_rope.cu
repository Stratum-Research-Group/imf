#include <cuda_runtime.h>
#include <stdint.h>
#include <math.h>

// Fused Blackwell Dynamic RoPE Bitplane Kernel
// Dynamically scales the base frequency theta using an NTK-aware scaling factor:
// theta_scaled = theta * base_scale
// In-register complex rotation applied to packed 2-bit / 4-bit representation bitplanes

__device__ __forceinline__ float2 rotate_half(float2 v) {
    return make_float2(-v.y, v.x);
}

extern "C" __global__ void fused_blackwell_bit_dynamic_rope_kernel(
    const uint32_t* __restrict__ q_packed_in,   // [batch, heads, seq_len, dim / 16] packed 2-bit
    const uint32_t* __restrict__ k_packed_in,
    uint32_t* __restrict__ q_packed_out,
    uint32_t* __restrict__ k_packed_out,
    const int seq_len,
    const int num_heads,
    const int head_dim,
    const float base_theta,
    const float scale_factor,                   // NTK-aware dynamic base scaling factor
    const int stride_seq,
    const int stride_head
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    int total_elements = seq_len * num_heads * (head_dim / 16);
    if (idx >= total_elements) return;

    int pos = (idx / ((head_dim / 16) * num_heads));
    int rem = idx % ((head_dim / 16) * num_heads);
    int head = rem / (head_dim / 16);
    int d_idx = (rem % (head_dim / 16)) * 16;

    // NTK-aware scaled theta:
    // theta_i = (base_theta * scale_factor) ^ (-2i / head_dim)
    float exponent = (float)d_idx / (float)head_dim;
    float effective_theta = base_theta * scale_factor;
    float freq = 1.0f / powf(effective_theta, exponent);
    float angle = (float)pos * freq;

    float cos_val = cosf(angle);
    float sin_val = sinf(angle);

    // Read packed bits
    uint32_t q_word = q_packed_in[idx];
    uint32_t k_word = k_packed_in[idx];

    // Unpack, apply rotation in registers, and repack
    // 16 2-bit values per 32-bit word
    uint32_t q_res = 0;
    uint32_t k_res = 0;

    #pragma unroll
    for (int i = 0; i < 8; ++i) {
        // Pairs of 2-bit values (v0, v1)
        float q0 = (float)((q_word >> (i * 4)) & 0x3) - 1.5f;
        float q1 = (float)((q_word >> (i * 4 + 2)) & 0x3) - 1.5f;

        float k0 = (float)((k_word >> (i * 4)) & 0x3) - 1.5f;
        float k1 = (float)((k_word >> (i * 4 + 2)) & 0x3) - 1.5f;

        // Apply 2D Givens rotation:
        // [q0_rot] = [cos -sin] [q0]
        // [q1_rot]   [sin  cos] [q1]
        float q0_rot = q0 * cos_val - q1 * sin_val;
        float q1_rot = q0 * sin_val + q1 * cos_val;

        float k0_rot = k0 * cos_val - k1 * sin_val;
        float k1_rot = k0 * sin_val + k1 * cos_val;

        // Quantize back to 2-bit {0, 1, 2, 3}
        uint32_t q0_q = (uint32_t)fminf(fmaxf(roundf(q0_rot + 1.5f), 0.0f), 3.0f);
        uint32_t q1_q = (uint32_t)fminf(fmaxf(roundf(q1_rot + 1.5f), 0.0f), 3.0f);

        uint32_t k0_q = (uint32_t)fminf(fmaxf(roundf(k0_rot + 1.5f), 0.0f), 3.0f);
        uint32_t k1_q = (uint32_t)fminf(fmaxf(roundf(k1_rot + 1.5f), 0.0f), 3.0f);

        q_res |= (q0_q << (i * 4)) | (q1_q << (i * 4 + 2));
        k_res |= (k0_q << (i * 4)) | (k1_q << (i * 4 + 2));
    }

    q_packed_out[idx] = q_res;
    k_packed_out[idx] = k_res;
}

extern "C" void launch_fused_blackwell_bit_dynamic_rope(
    const uint32_t* q_in,
    const uint32_t* k_in,
    uint32_t* q_out,
    uint32_t* k_out,
    int seq_len,
    int num_heads,
    int head_dim,
    float base_theta,
    float scale_factor,
    cudaStream_t stream
) {
    int total_words = seq_len * num_heads * (head_dim / 16);
    int threads = 256;
    int blocks = (total_words + threads - 1) / threads;

    fused_blackwell_bit_dynamic_rope_kernel<<<blocks, threads, 0, stream>>>(
        q_in, k_in, q_out, k_out,
        seq_len, num_heads, head_dim,
        base_theta, scale_factor,
        num_heads * (head_dim / 16),
        head_dim / 16
    );
}
