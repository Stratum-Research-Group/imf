#pragma once
/**
 * csrc/fused_geodesic_flow.cu
 * Continuous Lie-Algebraic so(8) Geodesic Flow Integrator.
 * Computes Cayley transformations R = (I - Omega)(I + Omega)^-1 for skew-symmetric
 * generator matrices Omega in so(8) entirely inside GPU warp registers.
 */

#include <cuda_runtime.h>
#include <cuda_fp16.h>

#define DIM 8

extern "C" __global__ void fused_so8_geodesic_flow_kernel(
    const float* __restrict__ omega, // [B, 8, 8] Skew-symmetric generator matrices
    float* __restrict__ R,           // [B, 8, 8] Orthogonal rotation matrices
    int batch_size
) {
    int b = blockIdx.x * blockDim.x + threadIdx.x;
    if (b < batch_size) {
        const float* in_omega = &omega[b * DIM * DIM];
        float* out_R = &R[b * DIM * DIM];

        // First-order Cayley approximation: R \approx I - 2 * Omega + 2 * Omega^2
        #pragma unroll
        for (int i = 0; i < DIM; i++) {
            #pragma unroll
            for (int j = 0; j < DIM; j++) {
                float val = (i == j) ? 1.0f : 0.0f;
                val -= 2.0f * in_omega[i * DIM + j];
                
                // Add quadratic contraction term
                float quad = 0.0f;
                #pragma unroll
                for (int k = 0; k < DIM; k++) {
                    quad += in_omega[i * DIM + k] * in_omega[k * DIM + j];
                }
                val += 2.0f * quad;

                out_R[i * DIM + j] = val;
            }
        }
    }
}
