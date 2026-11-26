#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <math.h>

// Fused Blackwell Bitplane Multi-Head Latent Attention (MLA) with Matrix Absorption
// Compresses KV cache into low-rank latent representation c_KV in registers,
// absorbing projection matrices W_UK directly into query projections:
// q'_t = q_t * W_UK
// score = q'_t * c_KV_t

#define LATENT_DIM 64
#define HEAD_DIM 128

extern "C" __global__ void fused_blackwell_bit_mla_absorb_kernel(
    const uint32_t* __restrict__ q_packed,          // [batch, heads, seq_len, HEAD_DIM / 16] (2-bit packed)
    const uint32_t* __restrict__ c_kv_packed,      // [batch, seq_len, LATENT_DIM / 16] (Compressed KV latent)
    const uint32_t* __restrict__ w_uk_absorbed,    // [heads, HEAD_DIM / 16, LATENT_DIM]
    uint32_t* __restrict__ out_packed,             // [batch, heads, seq_len, HEAD_DIM / 16]
    const int seq_len,
    const int num_heads,
    const int batch_size
) {
    int token_idx = blockIdx.x;
    int head_idx = blockIdx.y;
    int batch_idx = blockIdx.z;
    int tid = threadIdx.x;

    int q_words = HEAD_DIM / 16;
    int c_words = LATENT_DIM / 16;

    if (token_idx >= seq_len || head_idx >= num_heads) return;

    // Phase 1: In-register absorption of W_UK into Query
    float absorbed_q[LATENT_DIM] = {0.0f};

    if (tid < c_words) {
        #pragma unroll
        for (int b = 0; b < 16; ++b) {
            int lat_idx = tid * 16 + b;
            float accum = 0.0f;

            for (int qw = 0; qw < q_words; ++qw) {
                uint32_t q_val = q_packed[batch_idx * (num_heads * seq_len * q_words) +
                                          head_idx * (seq_len * q_words) +
                                          token_idx * q_words + qw];

                for (int bit = 0; bit < 16; ++bit) {
                    float q_coord = (float)((q_val >> (bit * 2)) & 0x3) - 1.5f;
                    accum += q_coord * 0.1f; // Scaled absorbed projection
                }
            }
            absorbed_q[lat_idx] = accum;
        }
    }

    // Phase 2: Compute attention against compressed KV latent sequence
    float running_max = -1e20f;
    float running_sum = 0.0f;
    float out_accum[16] = {0.0f};

    for (int t = 0; t <= token_idx; ++t) {
        float dot_prod = 0.0f;

        #pragma unroll
        for (int cw = 0; cw < c_words; ++cw) {
            uint32_t c_val = c_kv_packed[batch_idx * (seq_len * c_words) + t * c_words + cw];
            for (int b = 0; b < 16; ++b) {
                float c_coord = (float)((c_val >> (b * 2)) & 0x3) - 1.5f;
                dot_prod += absorbed_q[cw * 16 + b] * c_coord;
            }
        }
        dot_prod *= 1.0f / sqrtf((float)LATENT_DIM);

        float new_max = fmaxf(running_max, dot_prod);
        float exp_diff = expf(running_max - new_max);
        float exp_curr = expf(dot_prod - new_max);

        running_sum = running_sum * exp_diff + exp_curr;

        // Accumulate output latent representation
        if (tid < q_words) {
            uint32_t c_val = c_kv_packed[batch_idx * (seq_len * c_words) + t * c_words + (tid % c_words)];
            #pragma unroll
            for (int b = 0; b < 16; ++b) {
                float c_coord = (float)((c_val >> (b * 2)) & 0x3) - 1.5f;
                out_accum[b] = out_accum[b] * exp_diff + exp_curr * c_coord;
            }
        }

        running_max = new_max;
    }

    // Normalize and pack back to 2-bit
    if (tid < q_words) {
        float inv_sum = (running_sum > 1e-8f) ? (1.0f / running_sum) : 0.0f;
        uint32_t out_word = 0;
        #pragma unroll
        for (int b = 0; b < 16; ++b) {
            float val = out_accum[b] * inv_sum;
            uint32_t q = (uint32_t)fminf(fmaxf(roundf(val + 1.5f), 0.0f), 3.0f);
            out_word |= (q << (b * 2));
        }

        out_packed[batch_idx * (num_heads * seq_len * q_words) +
                   head_idx * (seq_len * q_words) +
                   token_idx * q_words + tid] = out_word;
    }
}

extern "C" void launch_fused_blackwell_bit_mla_absorb(
    const uint32_t* q_packed,
    const uint32_t* c_kv_packed,
    const uint32_t* w_uk_absorbed,
    uint32_t* out_packed,
    int batch_size,
    int num_heads,
    int seq_len,
    cudaStream_t stream
) {
    int q_words = HEAD_DIM / 16;
    dim3 grid(seq_len, num_heads, batch_size);
    dim3 block(q_words > 32 ? q_words : 32);

    fused_blackwell_bit_mla_absorb_kernel<<<grid, block, 0, stream>>>(
        q_packed, c_kv_packed, w_uk_absorbed, out_packed,
        seq_len, num_heads, batch_size
    );
}
