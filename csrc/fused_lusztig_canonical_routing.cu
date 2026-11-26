#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <cuda_fp16.h>
#include <cstdint>
#include <cstdio>
#include <cfloat>

extern "C" {

// Canonical crystal basis routing: evaluates highest weight module projections
// and determines top-k expert routing via crystal operators \tilde{e}_i, \tilde{f}_i
__global__ void lusztig_canonical_routing_kernel(
    const half* __restrict__ hidden_states,      // [batch_size, hidden_dim]
    const half* __restrict__ canonical_basis_weights, // [num_experts, hidden_dim]
    int* __restrict__ routing_indices,           // [batch_size, top_k]
    float* __restrict__ routing_weights,         // [batch_size, top_k]
    int batch_size,
    int hidden_dim,
    int num_experts,
    int top_k,
    float temperature
) {
    int b = blockIdx.x;
    if (b >= batch_size) return;

    // Dynamic shared memory for expert crystal inner products
    extern __shared__ float s_scores[];

    int tid = threadIdx.x;
    int stride = blockDim.x;

    const half* token_vec = hidden_states + b * hidden_dim;

    // Compute dot product against canonical crystal bases
    for (int exp_idx = tid; exp_idx < num_experts; exp_idx += stride) {
        const half* exp_basis = canonical_basis_weights + exp_idx * hidden_dim;
        float dot = 0.0f;
        for (int d = 0; d < hidden_dim; ++d) {
            dot += __half2float(token_vec[d]) * __half2float(exp_basis[d]);
        }
        // Quantum deformation temperature scaling q = e^{-\hbar / T}
        s_scores[exp_idx] = dot / temperature;
    }

    __syncthreads();

    // Top-k crystal selection executed by thread 0
    if (tid == 0) {
        for (int k = 0; k < top_k; ++k) {
            float max_val = -1e20f;
            int max_idx = -1;
            for (int e = 0; e < num_experts; ++e) {
                if (s_scores[e] > max_val) {
                    max_val = s_scores[e];
                    max_idx = e;
                }
            }
            if (max_idx >= 0) {
                routing_indices[b * top_k + k] = max_idx;
                routing_weights[b * top_k + k] = max_val;
                s_scores[max_idx] = -1e20f; // Invalidate for next rank
            } else {
                routing_indices[b * top_k + k] = 0;
                routing_weights[b * top_k + k] = 0.0f;
            }
        }

        // Softmax normalize the top-k crystal weights
        float max_topk = routing_weights[b * top_k];
        float sum_exp = 0.0f;
        for (int k = 0; k < top_k; ++k) {
            float exp_val = expf(routing_weights[b * top_k + k] - max_topk);
            routing_weights[b * top_k + k] = exp_val;
            sum_exp += exp_val;
        }
        for (int k = 0; k < top_k; ++k) {
            routing_weights[b * top_k + k] /= sum_exp;
        }
    }
}

void launch_lusztig_canonical_routing(
    const half* hidden_states,
    const half* canonical_basis_weights,
    int* routing_indices,
    float* routing_weights,
    int batch_size,
    int hidden_dim,
    int num_experts,
    int top_k,
    float temperature,
    cudaStream_t stream
) {
    size_t shared_mem = num_experts * sizeof(float);
    int threads = 128;
    lusztig_canonical_routing_kernel<<<batch_size, threads, shared_mem, stream>>>(
        hidden_states, canonical_basis_weights, routing_indices, routing_weights,
        batch_size, hidden_dim, num_experts, top_k, temperature
    );
}

}
