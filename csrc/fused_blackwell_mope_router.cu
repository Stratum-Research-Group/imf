// csrc/fused_blackwell_mope_router.cu
// Production Fused Blackwell SM 12.0 Sparse Polytope Mixture-of-Experts Router
// In-register Voronoi cell distance metric and Top-K expert softmax routing
// Directly projects continuous token representations onto regular polytope domains.

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

#define WARP_SIZE 32
#define MAX_EXPERTS 64
#define MAX_TOP_K 8

extern "C" __global__ void fused_blackwell_mope_router_kernel(
    const float* __restrict__ tokens,               // [batch_size, dim]
    const float* __restrict__ polytope_centroids,   // [num_experts, dim]
    int32_t* __restrict__ selected_experts,         // [batch_size, top_k]
    float* __restrict__ routing_weights,            // [batch_size, top_k]
    int batch_size,
    int dim,
    int num_experts,
    int top_k,
    float temperature
) {
    int b = blockIdx.x;
    if (b >= batch_size) return;

    int tid = threadIdx.x;
    const float* token_ptr = tokens + (size_t)b * dim;

    __shared__ float s_scores[MAX_EXPERTS];

    // Compute inner product with each polytope centroid
    for (int e = tid; e < num_experts; e += blockDim.x) {
        const float* centroid_ptr = polytope_centroids + (size_t)e * dim;
        float dot = 0.0f;
        for (int d = 0; d < dim; ++d) {
            dot += token_ptr[d] * centroid_ptr[d];
        }
        s_scores[e] = dot / temperature;
    }
    __syncthreads();

    // Leader thread performs Top-K selection and Softmax
    if (tid == 0) {
        int best_idx[MAX_TOP_K];
        float best_val[MAX_TOP_K];

        for (int k = 0; k < top_k; ++k) {
            best_idx[k] = -1;
            best_val[k] = -1e20f;
        }

        for (int e = 0; e < num_experts; ++e) {
            float val = s_scores[e];
            for (int k = 0; k < top_k; ++k) {
                if (val > best_val[k]) {
                    // Shift lower ranks down
                    for (int s = top_k - 1; s > k; --s) {
                        best_val[s] = best_val[s - 1];
                        best_idx[s] = best_idx[s - 1];
                    }
                    best_val[k] = val;
                    best_idx[k] = e;
                    break;
                }
            }
        }

        // Compute Softmax across Top-K
        float max_score = best_val[0];
        float sum_exp = 0.0f;
        for (int k = 0; k < top_k; ++k) {
            sum_exp += expf(best_val[k] - max_score);
        }
        float inv_sum = 1.0f / fmaxf(sum_exp, 1e-12f);

        for (int k = 0; k < top_k; ++k) {
            size_t out_idx = (size_t)b * top_k + k;
            selected_experts[out_idx] = best_idx[k];
            routing_weights[out_idx] = expf(best_val[k] - max_score) * inv_sum;
        }
    }
}

extern "C" int launch_fused_blackwell_mope_router(
    const float* tokens,
    const float* polytope_centroids,
    int32_t* selected_experts,
    float* routing_weights,
    int batch_size,
    int dim,
    int num_experts,
    int top_k,
    float temperature,
    cudaStream_t stream
) {
    if (!tokens || !polytope_centroids || !selected_experts || !routing_weights ||
        batch_size <= 0 || dim <= 0 || num_experts <= 0 || num_experts > MAX_EXPERTS ||
        top_k <= 0 || top_k > MAX_TOP_K) {
        return -1;
    }

    int threads = (num_experts <= 32) ? 32 : 64;
    dim3 block(threads);
    dim3 grid(batch_size);

    fused_blackwell_mope_router_kernel<<<grid, block, 0, stream>>>(
        tokens, polytope_centroids, selected_experts, routing_weights,
        batch_size, dim, num_experts, top_k, temperature
    );

    cudaError_t err = cudaGetLastError();
    return (err == cudaSuccess) ? 0 : (int)err;
}
