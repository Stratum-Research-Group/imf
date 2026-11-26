#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <math.h>

// Fused Blackwell Bitplane Linear Attention with Recurrent State Retention
// Implements O(1) memory autoregressive retention: S_t = gamma * S_{t-1} + K_t^T * V_t
// and Out_t = Q_t * S_t directly in shared memory and registers with packed 2-bit tensors.

#define STATE_DIM 64 // head_dim

extern "C" __global__ void fused_blackwell_bit_linear_retention_kernel(
    const uint32_t* __restrict__ q_packed,   // [batch, heads, seq_len, head_dim / 16] (2-bit packed)
    const uint32_t* __restrict__ k_packed,   // [batch, heads, seq_len, head_dim / 16]
    const uint32_t* __restrict__ v_packed,   // [batch, heads, seq_len, head_dim / 16]
    uint32_t* __restrict__ out_packed,       // [batch, heads, seq_len, head_dim / 16]
    const float decay_gamma,                 // Recurrent retention decay factor in (0, 1)
    const int seq_len,
    const int num_heads,
    const int head_dim
) {
    int bh_idx = blockIdx.x; // batch * heads
    int tid = threadIdx.x;   // handles a slice of the head dimension
    int words_per_head = head_dim / 16;

    // Recurrent state tile stored in threadblock shared memory [STATE_DIM, STATE_DIM]
    __shared__ float smem_state[STATE_DIM][STATE_DIM];

    // Initialize state to zero
    for (int r = tid; r < STATE_DIM; r += blockDim.x) {
        #pragma unroll
        for (int c = 0; c < STATE_DIM; ++c) {
            smem_state[r][c] = 0.0f;
        }
    }
    __syncthreads();

    // Iterate sequentially over time steps t = 0 .. seq_len - 1
    for (int t = 0; t < seq_len; ++t) {
        // Unpack K_t and V_t in registers
        float local_k[16];
        float local_v[16];

        int word_idx = tid % words_per_head;
        uint32_t kw = k_packed[bh_idx * seq_len * words_per_head + t * words_per_head + word_idx];
        uint32_t vw = v_packed[bh_idx * seq_len * words_per_head + t * words_per_head + word_idx];

        #pragma unroll
        for (int b = 0; b < 16; ++b) {
            local_k[b] = (float)((kw >> (b * 2)) & 0x3) - 1.5f;
            local_v[b] = (float)((vw >> (b * 2)) & 0x3) - 1.5f;
        }

        // Update recurrent retention matrix: S_t = decay_gamma * S_{t-1} + K_t^T * V_t
        for (int r = tid; r < STATE_DIM; r += blockDim.x) {
            int r_word = r / 16;
            int r_bit = r % 16;
            float k_r = (float)(((k_packed[bh_idx * seq_len * words_per_head + t * words_per_head + r_word] >> (r_bit * 2)) & 0x3)) - 1.5f;

            #pragma unroll
            for (int c = 0; c < STATE_DIM; ++c) {
                int c_word = c / 16;
                int c_bit = c % 16;
                float v_c = (float)(((v_packed[bh_idx * seq_len * words_per_head + t * words_per_head + c_word] >> (c_bit * 2)) & 0x3)) - 1.5f;
                smem_state[r][c] = decay_gamma * smem_state[r][c] + k_r * v_c;
            }
        }
        __syncthreads();

        // Compute output: Out_t = Q_t * S_t
        if (tid < words_per_head) {
            uint32_t qw = q_packed[bh_idx * seq_len * words_per_head + t * words_per_head + tid];
            uint32_t out_word = 0;

            #pragma unroll
            for (int b = 0; b < 16; ++b) {
                int c_idx = tid * 16 + b;
                float accum = 0.0f;

                for (int r = 0; r < STATE_DIM; ++r) {
                    int r_word = r / 16;
                    int r_bit = r % 16;
                    float q_r = (float)(((q_packed[bh_idx * seq_len * words_per_head + t * words_per_head + r_word] >> (r_bit * 2)) & 0x3)) - 1.5f;
                    accum += q_r * smem_state[r][c_idx];
                }

                // Re-quantize to 2-bit
                uint32_t q_out = (uint32_t)fminf(fmaxf(roundf(accum * 0.05f + 1.5f), 0.0f), 3.0f);
                out_word |= (q_out << (b * 2));
            }
            out_packed[bh_idx * seq_len * words_per_head + t * words_per_head + tid] = out_word;
        }
        __syncthreads();
    }
}

extern "C" void launch_fused_blackwell_bit_linear_retention(
    const uint32_t* q_packed,
    const uint32_t* k_packed,
    const uint32_t* v_packed,
    uint32_t* out_packed,
    float decay_gamma,
    int batch_size,
    int num_heads,
    int seq_len,
    int head_dim,
    cudaStream_t stream
) {
    dim3 grid(batch_size * num_heads);
    dim3 block(64);

    fused_blackwell_bit_linear_retention_kernel<<<grid, block, 0, stream>>>(
        q_packed, k_packed, v_packed, out_packed,
        decay_gamma, seq_len, num_heads, head_dim
    );
}
