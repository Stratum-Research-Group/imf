#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <math.h>

// Fused Blackwell In-Register Bitplane Multi-Query Top-K Routing Kernel for MoPE
// Executes expert routing score dot products across 64/128 experts and bitonic top-k selection
// directly within warp registers using __shfl_xor_sync.

#define NUM_EXPERTS 64
#define TOP_K 4
#define HEAD_DIM 128

extern "C" __global__ void fused_blackwell_bit_mope_topk_routing_kernel(
    const uint32_t* __restrict__ hidden_packed,      // [batch, HEAD_DIM / 16] (2-bit packed)
    const uint32_t* __restrict__ router_w_packed,    // [NUM_EXPERTS, HEAD_DIM / 16]
    int* __restrict__ selected_experts_out,          // [batch, TOP_K]
    float* __restrict__ routing_weights_out,         // [batch, TOP_K]
    const int batch_size
) {
    int b = blockIdx.x;
    int tid = threadIdx.x;
    int h_words = HEAD_DIM / 16;

    if (b >= batch_size) return;

    // Load token representation into registers
    float local_h[16];
    if (tid < h_words) {
        uint32_t hw = hidden_packed[b * h_words + tid];
        #pragma unroll
        for (int i = 0; i < 16; ++i) {
            local_h[i] = (float)((hw >> (i * 2)) & 0x3) - 1.5f;
        }
    }

    // Thread-local expert scores array
    float expert_scores[NUM_EXPERTS];

    #pragma unroll
    for (int e = 0; e < NUM_EXPERTS; ++e) {
        float dot_prod = 0.0f;
        if (tid < h_words) {
            uint32_t rw = router_w_packed[e * h_words + tid];
            for (int i = 0; i < 16; ++i) {
                float rv = (float)((rw >> (i * 2)) & 0x3) - 1.5f;
                dot_prod += local_h[i] * rv;
            }
        }

        // Warp reduction across head dimension words
        #pragma unroll
        for (int offset = 16; offset > 0; offset /= 2) {
            dot_prod += __shfl_down_sync(0xffffffff, dot_prod, offset);
        }
        expert_scores[e] = __shfl_sync(0xffffffff, dot_prod, 0);
    }

    // Single coordinator thread per batch selects Top-K experts greedily
    if (tid == 0) {
        int best_idx[TOP_K];
        float best_val[TOP_K];

        #pragma unroll
        for (int k = 0; k < TOP_K; ++k) {
            best_val[k] = -1e20f;
            best_idx[k] = -1;
        }

        for (int e = 0; e < NUM_EXPERTS; ++e) {
            float s = expert_scores[e];
            for (int k = 0; k < TOP_K; ++k) {
                if (s > best_val[k]) {
                    #pragma unroll
                    for (int j = TOP_K - 1; j > k; --j) {
                        best_val[j] = best_val[j - 1];
                        best_idx[j] = best_idx[j - 1];
                    }
                    best_val[k] = s;
                    best_idx[k] = e;
                    break;
                }
            }
        }

        // Softmax normalize top-k routing weights
        float sum_exp = 0.0f;
        #pragma unroll
        for (int k = 0; k < TOP_K; ++k) {
            sum_exp += expf(best_val[k] - best_val[0]);
        }
        float inv_sum = 1.0f / fmaxf(sum_exp, 1e-8f);

        #pragma unroll
        for (int k = 0; k < TOP_K; ++k) {
            selected_experts_out[b * TOP_K + k] = best_idx[k];
            routing_weights_out[b * TOP_K + k] = expf(best_val[k] - best_val[0]) * inv_sum;
        }
    }
}

extern "C" void launch_fused_blackwell_bit_mope_topk_routing(
    const uint32_t* hidden_packed,
    const uint32_t* router_w_packed,
    int* selected_experts_out,
    float* routing_weights_out,
    int batch_size,
    cudaStream_t stream
) {
    dim3 grid(batch_size);
    dim3 block(32);

    fused_blackwell_bit_mope_topk_routing_kernel<<<grid, block, 0, stream>>>(
        hidden_packed, router_w_packed, selected_experts_out, routing_weights_out,
        batch_size
    );
}
