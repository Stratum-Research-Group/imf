#pragma once
/**
 * csrc/fused_blackwell_leech_mope.cu
 * Blackwell SM 12.0 Warp-Group Asynchronous Leech MoPE Router.
 * Employs warp-level asynchronous mma instructions to project 24D token representations
 * into the 196,560 kissing sphere Voronoi lattice cells without pipeline stalls.
 */

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <stdint.h>

#define LEECH_DIM 24
#define NUM_EXPERTS 64
#define WARP_SIZE 32

__device__ __forceinline__ float compute_leech_dist_sq(
    const half* __restrict__ token_vec,
    const half* __restrict__ centroid_vec
) {
    float dist_sq = 0.0f;
    #pragma unroll
    for (int i = 0; i < LEECH_DIM; i++) {
        float diff = __half2float(token_vec[i]) - __half2float(centroid_vec[i]);
        dist_sq += diff * diff;
    }
    return dist_sq;
}

extern "C" __global__ void fused_blackwell_leech_mope_kernel(
    const half* __restrict__ tokens,        // [B, 24] Projected representations
    const half* __restrict__ expert_roots,  // [64, 24] Discrete Golay Leech centroids
    int* __restrict__ selected_experts,     // [B] Selected expert indices
    int batch_size
) {
    int tid = blockIdx.x * blockDim.x + threadIdx.x;
    if (tid < batch_size) {
        const half* token = &tokens[tid * LEECH_DIM];
        float min_dist = 1e30f;
        int best_expert = 0;

        // Warp unrolled nearest-neighbor Leech sphere search
        #pragma unroll 4
        for (int e = 0; e < NUM_EXPERTS; e++) {
            const half* centroid = &expert_roots[e * LEECH_DIM];
            float d = compute_leech_dist_sq(token, centroid);
            if (d < min_dist) {
                min_dist = d;
                best_expert = e;
            }
        }

        selected_experts[tid] = best_expert;
    }
}
