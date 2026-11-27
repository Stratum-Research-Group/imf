#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <math.h>
#include <stdio.h>
#include <stdint.h>

#define WARP_SIZE 32

// Device / Host helper for local Tate duality pairing and cup product
__host__ __device__ inline void compute_tate_duality_step(
    const float* cocycle_a,      // [dim]
    const float* cocycle_b,      // [dim]
    int dim,
    float mod_m,
    float* out_pairing_val,
    float* out_isometry_norm
) {
    float inner_prod = 0.0f;
    for (int k = 0; k < dim; ++k) {
        inner_prod += cocycle_a[k] * cocycle_b[k];
    }

    // Cup product invariant modulo m
    float paired = fmodf(fabsf(inner_prod), mod_m);
    *out_pairing_val = paired;

    // Isometry preservation norm: ||a||^2 * ||b||^2 - (a . b)^2
    float norm_a_sq = 0.0f, norm_b_sq = 0.0f;
    for (int k = 0; k < dim; ++k) {
        norm_a_sq += cocycle_a[k] * cocycle_a[k];
        norm_b_sq += cocycle_b[k] * cocycle_b[k];
    }
    float det_gram = (norm_a_sq * norm_b_sq) - (inner_prod * inner_prod);
    *out_isometry_norm = (det_gram >= 0.0f) ? sqrtf(det_gram) : 0.0f;
}

// Fused Blackwell SM 12.0 Kernel for Tate Local Duality Pairing
__global__ void tate_duality_pairing_kernel(
    const float* __restrict__ cocycles_a,       // [B, dim]
    const float* __restrict__ cocycles_b,       // [B, dim]
    int dim,
    float mod_m,
    float* __restrict__ pairing_values,         // [B]
    float* __restrict__ isometry_norms,         // [B]
    float* __restrict__ non_degeneracy_flags,   // [B] (1.0 = non-degenerate, 0.0 = degenerate)
    int B
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= B) return;

    const float* a_ptr = cocycles_a + idx * dim;
    const float* b_ptr = cocycles_b + idx * dim;

    float p_val = 0.0f, iso_norm = 0.0f;
    compute_tate_duality_step(a_ptr, b_ptr, dim, mod_m, &p_val, &iso_norm);

    pairing_values[idx] = p_val;
    isometry_norms[idx] = iso_norm;
    non_degeneracy_flags[idx] = (iso_norm > 1e-5f || p_val > 1e-5f) ? 1.0f : 0.0f;
}

extern "C" {

int fused_blackwell_tate_duality_pairing(
    const float* cocycles_a,
    const float* cocycles_b,
    int dim,
    float mod_m,
    float* pairing_values,
    float* isometry_norms,
    float* non_degeneracy_flags,
    int B
) {
    if (!cocycles_a || !cocycles_b || !pairing_values ||
        !isometry_norms || !non_degeneracy_flags ||
        B <= 0 || dim <= 0 || mod_m <= 0.0f) {
        return -1;
    }

    cudaError_t err = cudaSuccess;
    int device_count = 0;
    err = cudaGetDeviceCount(&device_count);

    if (err == cudaSuccess && device_count > 0) {
        float *d_a = nullptr, *d_b = nullptr;
        float *d_pval = nullptr, *d_iso = nullptr, *d_nondeg = nullptr;

        cudaMalloc(&d_a, B * dim * sizeof(float));
        cudaMalloc(&d_b, B * dim * sizeof(float));
        cudaMalloc(&d_pval, B * sizeof(float));
        cudaMalloc(&d_iso, B * sizeof(float));
        cudaMalloc(&d_nondeg, B * sizeof(float));

        cudaMemcpy(d_a, cocycles_a, B * dim * sizeof(float), cudaMemcpyHostToDevice);
        cudaMemcpy(d_b, cocycles_b, B * dim * sizeof(float), cudaMemcpyHostToDevice);

        int threadsPerBlock = 256;
        int blocksPerGrid = (B + threadsPerBlock - 1) / threadsPerBlock;
        tate_duality_pairing_kernel<<<blocksPerGrid, threadsPerBlock>>>(
            d_a, d_b, dim, mod_m, d_pval, d_iso, d_nondeg, B
        );
        cudaDeviceSynchronize();

        cudaMemcpy(pairing_values, d_pval, B * sizeof(float), cudaMemcpyDeviceToHost);
        cudaMemcpy(isometry_norms, d_iso, B * sizeof(float), cudaMemcpyDeviceToHost);
        cudaMemcpy(non_degeneracy_flags, d_nondeg, B * sizeof(float), cudaMemcpyDeviceToHost);

        cudaFree(d_a);
        cudaFree(d_b);
        cudaFree(d_pval);
        cudaFree(d_iso);
        cudaFree(d_nondeg);
        return 0;
    }

    // CPU Fallback
    for (int i = 0; i < B; ++i) {
        const float* a_ptr = cocycles_a + i * dim;
        const float* b_ptr = cocycles_b + i * dim;
        float p_val = 0.0f, iso_norm = 0.0f;
        compute_tate_duality_step(a_ptr, b_ptr, dim, mod_m, &p_val, &iso_norm);
        pairing_values[i] = p_val;
        isometry_norms[i] = iso_norm;
        non_degeneracy_flags[i] = (iso_norm > 1e-5f || p_val > 1e-5f) ? 1.0f : 0.0f;
    }
    return 0;
}

}
