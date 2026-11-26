#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <math.h>

// Fused Blackwell Bitplane Gated-Linear Recurrent Unit (G-LRU) Kernel
// Executes h_t = diag(Lambda) * h_{t-1} + (1 - |Lambda|) * (x_t * g_t)
// with packed 2-bit tensors in registers and shared memory.

#define HIDDEN_DIM 128

__device__ __forceinline__ float sigmoid_poly_fast(float x) {
    float z = fminf(fmaxf(x, -6.0f), 6.0f);
    return 0.5f + 0.197f * z - 0.004f * z * z * z;
}

extern "C" __global__ void fused_blackwell_bit_glru_kernel(
    const uint32_t* __restrict__ x_packed,      // [batch, seq_len, HIDDEN_DIM / 16] (2-bit packed)
    const uint32_t* __restrict__ gate_packed,   // [batch, seq_len, HIDDEN_DIM / 16]
    const float* __restrict__ lambda_diag,      // [HIDDEN_DIM] diagonal decay rates in (0, 1)
    uint32_t* __restrict__ out_packed,          // [batch, seq_len, HIDDEN_DIM / 16]
    const int seq_len,
    const int batch_size
) {
    int b = blockIdx.x;
    int tid = threadIdx.x;
    int words_per_token = HIDDEN_DIM / 16;

    if (b >= batch_size || tid >= words_per_token) return;

    // Recurrent hidden state vector in thread registers
    float h_state[16] = {0.0f};

    // Sequential recurrence over time steps t = 0 .. seq_len - 1
    for (int t = 0; t < seq_len; ++t) {
        uint32_t xw = x_packed[b * (seq_len * words_per_token) + t * words_per_token + tid];
        uint32_t gw = gate_packed[b * (seq_len * words_per_token) + t * words_per_token + tid];

        uint32_t out_word = 0;

        #pragma unroll
        for (int i = 0; i < 16; ++i) {
            int d_idx = tid * 16 + i;
            float xv = (float)((xw >> (i * 2)) & 0x3) - 1.5f;
            float gv = (float)((gw >> (i * 2)) & 0x3) - 1.5f;

            float gate_factor = sigmoid_poly_fast(gv);
            float input_modulated = xv * gate_factor;

            float lam = lambda_diag[d_idx];
            float decay_comp = 1.0f - fabsf(lam);

            // G-LRU update step: h_t = Lambda * h_{t-1} + (1 - |Lambda|) * (x_t * g_t)
            h_state[i] = lam * h_state[i] + decay_comp * input_modulated;

            // Output projection and re-quantization to 2-bit
            uint32_t q = (uint32_t)fminf(fmaxf(roundf(h_state[i] + 1.5f), 0.0f), 3.0f);
            out_word |= (q << (i * 2));
        }

        out_packed[b * (seq_len * words_per_token) + t * words_per_token + tid] = out_word;
    }
}

extern "C" void launch_fused_blackwell_bit_glru(
    const uint32_t* x_packed,
    const uint32_t* gate_packed,
    const float* lambda_diag,
    uint32_t* out_packed,
    int batch_size,
    int seq_len,
    cudaStream_t stream
) {
    int words_per_token = HIDDEN_DIM / 16;
    dim3 grid(batch_size);
    dim3 block(words_per_token);

    fused_blackwell_bit_glru_kernel<<<grid, block, 0, stream>>>(
        x_packed, gate_packed, lambda_diag, out_packed,
        seq_len, batch_size
    );
}
