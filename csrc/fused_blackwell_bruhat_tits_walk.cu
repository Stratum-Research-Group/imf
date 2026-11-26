// csrc/fused_blackwell_bruhat_tits_walk.cu
// ===================================================
// Production Fused Blackwell SM 12.0 Bruhat-Tits Building Paging & Tree-Walk Kernel
// Evaluates affine Coxeter reflections and apartment retractions across
// polysimplicial chambers in Bruhat-Tits buildings B(G, Q_p).
//
// Affine root hyperplane: H_{alpha, c} = {x in R^D : <alpha, x> = c}
// Affine reflection: s_{alpha, c}(x) = x - 2 * (<x, alpha> - c) / (<alpha, alpha>) * alpha
// Chamber crossing updates the combinatorial apartment chamber index.

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#ifdef __cplusplus
extern "C" {
#endif

// CUDA Device Kernel for Batched Bruhat-Tits Apartment Walking
__global__ void fused_bruhat_tits_walk_cuda_kernel(
    const float* __restrict__ x_in,         // [B, D] input position in apartment
    const float* __restrict__ v_in,         // [B, D] direction / token velocity
    const float* __restrict__ affine_roots, // [K, D] affine root normals
    const float* __restrict__ offsets,      // [K] scalar offsets c_k
    const float* __restrict__ root_sq,      // [K] <alpha_k, alpha_k>
    float* __restrict__ x_out,              // [B, D] updated position
    float* __restrict__ v_out,              // [B, D] updated direction
    int* __restrict__ chamber_ids,          // [B] updated combinatorial chamber index
    int B,
    int D,
    int K,
    float step_size
) {
    int b = blockIdx.x;
    int tid = threadIdx.x;
    if (b >= B) return;

    const float* xb = x_in + b * D;
    const float* vb = v_in + b * D;
    float* x_out_b = x_out + b * D;
    float* v_out_b = v_out + b * D;

    float pos = (tid < D) ? xb[tid] : 0.0f;
    float dir = (tid < D) ? vb[tid] : 0.0f;

    // Step forward along direction
    pos += dir * step_size;

    int chamber_mask = chamber_ids[b];

    // Evaluate facet crossings across affine root hyperplanes
    for (int k = 0; k < K; ++k) {
        const float* rk = affine_roots + k * D;
        float r_sq = root_sq[k];
        float c_k = offsets[k];

        float dot_val = 0.0f;
        if (tid < D) {
            dot_val = rk[tid] * pos;
        }

        // Warp reduction
        for (int offset = 16; offset > 0; offset /= 2) {
            dot_val += __shfl_down_sync(0xffffffff, dot_val, offset);
        }

        // Broadcast dot product from lane 0
        dot_val = __shfl_sync(0xffffffff, dot_val, 0);

        // Check if point has crossed the affine wall H_{alpha, c}
        float dist_to_wall = dot_val - c_k;
        if (dist_to_wall < 0.0f) {
            // Reflect direction and clamp/retract position back into sector
            float scale = 2.0f * dist_to_wall / (r_sq > 1e-7f ? r_sq : 1.0f);
            if (tid < D) {
                pos -= scale * rk[tid];
                dir -= (2.0f * (rk[tid] * dir) / (r_sq > 1e-7f ? r_sq : 1.0f)) * rk[tid];
            }
            if (tid == 0) {
                chamber_mask ^= (1 << (k % 31));
            }
        }
    }

    if (tid < D) {
        x_out_b[tid] = pos;
        v_out_b[tid] = dir;
    }
    if (tid == 0) {
        chamber_ids[b] = chamber_mask;
    }
}

// Host CPU Fallback Implementation
void fused_bruhat_tits_walk_cpu(
    const float* x_in,
    const float* v_in,
    const float* affine_roots,
    const float* offsets,
    const float* root_sq,
    float* x_out,
    float* v_out,
    int* chamber_ids,
    int B,
    int D,
    int K,
    float step_size
) {
    for (int b = 0; b < B; ++b) {
        const float* xb = x_in + b * D;
        const float* vb = v_in + b * D;
        float* x_out_b = x_out + b * D;
        float* v_out_b = v_out + b * D;

        for (int d = 0; d < D; ++d) {
            x_out_b[d] = xb[d] + vb[d] * step_size;
            v_out_b[d] = vb[d];
        }

        int mask = chamber_ids[b];

        for (int k = 0; k < K; ++k) {
            const float* rk = affine_roots + k * D;
            float r_sq = root_sq[k];
            float c_k = offsets[k];

            float dot_val = 0.0f;
            float dir_dot = 0.0f;
            for (int d = 0; d < D; ++d) {
                dot_val += rk[d] * x_out_b[d];
                dir_dot += rk[d] * v_out_b[d];
            }

            float dist = dot_val - c_k;
            if (dist < 0.0f) {
                float denom = (r_sq > 1e-7f) ? r_sq : 1.0f;
                float scale = 2.0f * dist / denom;
                float dir_scale = 2.0f * dir_dot / denom;
                for (int d = 0; d < D; ++d) {
                    x_out_b[d] -= scale * rk[d];
                    v_out_b[d] -= dir_scale * rk[d];
                }
                mask ^= (1 << (k % 31));
            }
        }
        chamber_ids[b] = mask;
    }
}

// C-ABI Exported Entrypoint
int fused_blackwell_bruhat_tits_walk(
    const float* x_in,
    const float* v_in,
    const float* affine_roots,
    const float* offsets,
    const float* root_sq,
    float* x_out,
    float* v_out,
    int* chamber_ids,
    int B,
    int D,
    int K,
    float step_size
) {
    if (!x_in || !v_in || !affine_roots || !offsets || !root_sq || !x_out || !v_out || !chamber_ids) {
        return -1;
    }

    int device = -1;
    cudaError_t err = cudaGetDevice(&device);
    if (err == cudaSuccess && device >= 0 && D <= 1024) {
        float *d_x_in = NULL, *d_v_in = NULL, *d_roots = NULL, *d_offsets = NULL, *d_root_sq = NULL;
        float *d_x_out = NULL, *d_v_out = NULL;
        int *d_chambers = NULL;

        size_t bytes_bd = (size_t)B * D * sizeof(float);
        size_t bytes_kd = (size_t)K * D * sizeof(float);
        size_t bytes_k = (size_t)K * sizeof(float);
        size_t bytes_b_int = (size_t)B * sizeof(int);

        if (cudaMalloc(&d_x_in, bytes_bd) != cudaSuccess ||
            cudaMalloc(&d_v_in, bytes_bd) != cudaSuccess ||
            cudaMalloc(&d_roots, bytes_kd) != cudaSuccess ||
            cudaMalloc(&d_offsets, bytes_k) != cudaSuccess ||
            cudaMalloc(&d_root_sq, bytes_k) != cudaSuccess ||
            cudaMalloc(&d_x_out, bytes_bd) != cudaSuccess ||
            cudaMalloc(&d_v_out, bytes_bd) != cudaSuccess ||
            cudaMalloc(&d_chambers, bytes_b_int) != cudaSuccess) {
            
            if (d_x_in) cudaFree(d_x_in);
            if (d_v_in) cudaFree(d_v_in);
            if (d_roots) cudaFree(d_roots);
            if (d_offsets) cudaFree(d_offsets);
            if (d_root_sq) cudaFree(d_root_sq);
            if (d_x_out) cudaFree(d_x_out);
            if (d_v_out) cudaFree(d_v_out);
            if (d_chambers) cudaFree(d_chambers);

            fused_bruhat_tits_walk_cpu(x_in, v_in, affine_roots, offsets, root_sq, x_out, v_out, chamber_ids, B, D, K, step_size);
            return 0;
        }

        cudaMemcpy(d_x_in, x_in, bytes_bd, cudaMemcpyHostToDevice);
        cudaMemcpy(d_v_in, v_in, bytes_bd, cudaMemcpyHostToDevice);
        cudaMemcpy(d_roots, affine_roots, bytes_kd, cudaMemcpyHostToDevice);
        cudaMemcpy(d_offsets, offsets, bytes_k, cudaMemcpyHostToDevice);
        cudaMemcpy(d_root_sq, root_sq, bytes_k, cudaMemcpyHostToDevice);
        cudaMemcpy(d_chambers, chamber_ids, bytes_b_int, cudaMemcpyHostToDevice);

        int threads = (D + 31) / 32 * 32;
        if (threads > 1024) threads = 1024;
        fused_bruhat_tits_walk_cuda_kernel<<<B, threads>>>(
            d_x_in, d_v_in, d_roots, d_offsets, d_root_sq,
            d_x_out, d_v_out, d_chambers,
            B, D, K, step_size
        );
        cudaDeviceSynchronize();

        cudaMemcpy(x_out, d_x_out, bytes_bd, cudaMemcpyDeviceToHost);
        cudaMemcpy(v_out, d_v_out, bytes_bd, cudaMemcpyDeviceToHost);
        cudaMemcpy(chamber_ids, d_chambers, bytes_b_int, cudaMemcpyDeviceToHost);

        cudaFree(d_x_in);
        cudaFree(d_v_in);
        cudaFree(d_roots);
        cudaFree(d_offsets);
        cudaFree(d_root_sq);
        cudaFree(d_x_out);
        cudaFree(d_v_out);
        cudaFree(d_chambers);
        return 0;
    }

    fused_bruhat_tits_walk_cpu(x_in, v_in, affine_roots, offsets, root_sq, x_out, v_out, chamber_ids, B, D, K, step_size);
    return 0;
}

#ifdef __cplusplus
}
#endif
