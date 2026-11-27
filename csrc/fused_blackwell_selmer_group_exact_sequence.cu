#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <math.h>
#include <stdio.h>
#include <stdint.h>

#define WARP_SIZE 32

// Device / Host helper for local Kummer obstruction computation
__host__ __device__ inline void compute_selmer_local_reduction(
    const float* local_cocycles,
    const float* local_kummer_bases,
    const float* padic_weights,
    float* kummer_projections,
    int num_places,
    float tolerance,
    float* out_sha_energy,
    float* out_admissibility
) {
    float total_sha = 0.0f;
    int is_admissible = 1;

    for (int p = 0; p < num_places; ++p) {
        float cocycle = local_cocycles[p];
        float base = local_kummer_bases[p];
        float weight = padic_weights[p];

        // Kummer projection: projection onto local image
        float proj = cocycle * base;
        kummer_projections[p] = proj;

        // Local obstruction norm: distance from Kummer subspace
        float diff = cocycle - proj;
        float local_norm_sq = diff * diff * weight;

        if (local_norm_sq > tolerance) {
            is_admissible = 0;
            total_sha += (local_norm_sq - tolerance);
        }
    }

    *out_sha_energy = total_sha;
    *out_admissibility = (is_admissible == 1 && total_sha < 1e-6f) ? 1.0f : 0.0f;
}

// Fused Blackwell SM 12.0 Kernel for Selmer Group Exact Sequence
__global__ void selmer_group_kernel(
    const float* __restrict__ local_cocycles,     // [B, num_places]
    const float* __restrict__ local_kummer_bases, // [B, num_places]
    const float* __restrict__ padic_weights,      // [num_places]
    float* __restrict__ kummer_projections,       // [B, num_places]
    float* __restrict__ selmer_admissibility,     // [B]
    float* __restrict__ sha_obstruction_energy,   // [B]
    int B,
    int num_places,
    float tolerance
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= B) return;

    const float* cocycles_ptr = local_cocycles + idx * num_places;
    const float* bases_ptr = local_kummer_bases + idx * num_places;
    float* proj_ptr = kummer_projections + idx * num_places;

    float sha_val = 0.0f;
    float adm_val = 0.0f;
    compute_selmer_local_reduction(
        cocycles_ptr, bases_ptr, padic_weights, proj_ptr,
        num_places, tolerance, &sha_val, &adm_val
    );

    sha_obstruction_energy[idx] = sha_val;
    selmer_admissibility[idx] = adm_val;
}

extern "C" {

int fused_blackwell_selmer_group_exact_sequence(
    const float* local_cocycles,
    const float* local_kummer_bases,
    const float* padic_weights,
    float* kummer_projections,
    float* selmer_admissibility,
    float* sha_obstruction_energy,
    int B,
    int num_places,
    float tolerance
) {
    if (!local_cocycles || !local_kummer_bases || !padic_weights ||
        !kummer_projections || !selmer_admissibility || !sha_obstruction_energy ||
        B <= 0 || num_places <= 0) {
        return -1;
    }

    cudaError_t err = cudaSuccess;
    int device_count = 0;
    err = cudaGetDeviceCount(&device_count);

    if (err == cudaSuccess && device_count > 0) {
        float *d_cocycles = nullptr, *d_bases = nullptr, *d_weights = nullptr;
        float *d_proj = nullptr, *d_adm = nullptr, *d_sha = nullptr;

        cudaMalloc(&d_cocycles, B * num_places * sizeof(float));
        cudaMalloc(&d_bases, B * num_places * sizeof(float));
        cudaMalloc(&d_weights, num_places * sizeof(float));
        cudaMalloc(&d_proj, B * num_places * sizeof(float));
        cudaMalloc(&d_adm, B * sizeof(float));
        cudaMalloc(&d_sha, B * sizeof(float));

        cudaMemcpy(d_cocycles, local_cocycles, B * num_places * sizeof(float), cudaMemcpyHostToDevice);
        cudaMemcpy(d_bases, local_kummer_bases, B * num_places * sizeof(float), cudaMemcpyHostToDevice);
        cudaMemcpy(d_weights, padic_weights, num_places * sizeof(float), cudaMemcpyHostToDevice);

        int threadsPerBlock = 256;
        int blocksPerGrid = (B + threadsPerBlock - 1) / threadsPerBlock;
        selmer_group_kernel<<<blocksPerGrid, threadsPerBlock>>>(
            d_cocycles, d_bases, d_weights, d_proj, d_adm, d_sha, B, num_places, tolerance
        );
        cudaDeviceSynchronize();

        cudaMemcpy(kummer_projections, d_proj, B * num_places * sizeof(float), cudaMemcpyDeviceToHost);
        cudaMemcpy(selmer_admissibility, d_adm, B * sizeof(float), cudaMemcpyDeviceToHost);
        cudaMemcpy(sha_obstruction_energy, d_sha, B * sizeof(float), cudaMemcpyDeviceToHost);

        cudaFree(d_cocycles);
        cudaFree(d_bases);
        cudaFree(d_weights);
        cudaFree(d_proj);
        cudaFree(d_adm);
        cudaFree(d_sha);
        return 0;
    }

    // CPU Fallback
    for (int i = 0; i < B; ++i) {
        const float* cocycles_ptr = local_cocycles + i * num_places;
        const float* bases_ptr = local_kummer_bases + i * num_places;
        float* proj_ptr = kummer_projections + i * num_places;

        float sha_val = 0.0f;
        float adm_val = 0.0f;
        compute_selmer_local_reduction(
            cocycles_ptr, bases_ptr, padic_weights, proj_ptr,
            num_places, tolerance, &sha_val, &adm_val
        );
        sha_obstruction_energy[i] = sha_val;
        selmer_admissibility[i] = adm_val;
    }
    return 0;
}

}
