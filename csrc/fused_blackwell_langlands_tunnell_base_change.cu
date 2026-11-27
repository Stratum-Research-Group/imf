#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

/**
 * Blackwell SM 12.0 Kernel: Langlands-Tunnell Theorem & Cyclic Base Change for GL_2
 *
 * Implements high-throughput verification and computation of:
 * 1. Solvable Artin representation lifting: Projective image solvability invariant
 *    (e.g., tetrahedral A_4 of order 12, octahedral S_4 of order 24).
 * 2. Cyclic base change lift traces: Tr(Pi(Frob_w)) = Tr(pi(Frob_v^d)) for degree d = [K_w : F_v].
 * 3. Conductor transformation under cyclic base change:
 *    log(cond(Pi)) = d * log(cond(pi)) + 2 * log(disc(K/F)).
 */

#define WARP_SIZE 32
#define BLOCK_DIM 256

__global__ void fused_blackwell_langlands_tunnell_base_change_kernel(
    const float* __restrict__ base_traces,          // [batch_size, num_places] Tr(pi(Frob_v))
    const float* __restrict__ inertia_degrees,      // [batch_size, num_places] d_v = [K_w : F_v]
    const float* __restrict__ base_conductors,      // [batch_size] cond(pi)
    const float* __restrict__ relative_discriminants,// [batch_size] disc(K/F)
    const float* __restrict__ proj_image_orders,    // [batch_size] |P(Im(rho))|
    float* __restrict__ lifted_traces_out,          // [batch_size, num_places] Tr(Pi(Frob_w))
    float* __restrict__ lifted_conductors_log_out,  // [batch_size] log(cond(Pi))
    float* __restrict__ solvability_flags_out,      // [batch_size] 1.0 if solvable (12 or 24), else 0.0
    int batch_size,
    int num_places,
    int cyclic_degree
) {
    int b = blockIdx.x;
    if (b >= batch_size) return;

    int tid = threadIdx.x;

    // 1. Thread 0 evaluates projective image solvability and conductor lift
    if (tid == 0) {
        float order = proj_image_orders[b];
        // Solvable for tetrahedral (12) or octahedral (24) or dihedral (2n)
        bool is_solvable = (fabsf(order - 12.0f) < 0.1f) ||
                           (fabsf(order - 24.0f) < 0.1f) ||
                           (order > 0.0f && fmodf(order, 2.0f) < 0.1f && order <= 60.0f && fabsf(order - 60.0f) > 0.1f);
        solvability_flags_out[b] = is_solvable ? 1.0f : 0.0f;

        float c_base = base_conductors[b];
        float disc = relative_discriminants[b];
        if (c_base <= 0.0f) c_base = 1.0f;
        if (disc <= 0.0f) disc = 1.0f;

        // Base change conductor formula: cond(Pi) = cond(pi)^d * disc(K/F)^2
        // In log space: log(cond(Pi)) = d * log(cond(pi)) + 2.0 * log(disc(K/F))
        float log_cond_pi = (float)cyclic_degree * logf(c_base) + 2.0f * logf(disc);
        lifted_conductors_log_out[b] = log_cond_pi;
    }

    // 2. Vectorized evaluation of base change Frobenius traces across places
    // For GL_2: if eigenvalues are alpha, beta with alpha + beta = a_v and alpha * beta = 1:
    // For degree 1: trace = a_v
    // For degree 2: trace = alpha^2 + beta^2 = a_v^2 - 2
    // For degree 3: trace = alpha^3 + beta^3 = a_v^3 - 3*a_v
    for (int p = tid; p < num_places; p += BLOCK_DIM) {
        int idx = b * num_places + p;
        float a_v = base_traces[idx];
        float d_v = inertia_degrees[idx];
        int deg = (int)(d_v + 0.5f);
        if (deg <= 0) deg = 1;

        float lifted_tr = a_v;
        if (deg == 1) {
            lifted_tr = a_v;
        } else if (deg == 2) {
            lifted_tr = a_v * a_v - 2.0f;
        } else if (deg == 3) {
            lifted_tr = a_v * a_v * a_v - 3.0f * a_v;
        } else {
            // General degree d via recurrence: T_d(x)
            float t_prev = 2.0f; // T_0
            float t_curr = a_v;  // T_1
            for (int k = 2; k <= deg; ++k) {
                float t_next = a_v * t_curr - t_prev;
                t_prev = t_curr;
                t_curr = t_next;
            }
            lifted_tr = t_curr;
        }
        lifted_traces_out[idx] = lifted_tr;
    }
}

extern "C" {

int fused_blackwell_langlands_tunnell_base_change(
    const float* base_traces,
    const float* inertia_degrees,
    const float* base_conductors,
    const float* relative_discriminants,
    const float* proj_image_orders,
    float* lifted_traces_out,
    float* lifted_conductors_log_out,
    float* solvability_flags_out,
    int batch_size,
    int num_places,
    int cyclic_degree
) {
    if (!base_traces || !inertia_degrees || !base_conductors ||
        !relative_discriminants || !proj_image_orders ||
        !lifted_traces_out || !lifted_conductors_log_out || !solvability_flags_out ||
        batch_size <= 0 || num_places <= 0 || cyclic_degree <= 0) {
        return -1;
    }

    size_t traces_size = (size_t)batch_size * num_places * sizeof(float);
    size_t batch_size_bytes = (size_t)batch_size * sizeof(float);

    float *d_base_traces = nullptr, *d_inertia = nullptr;
    float *d_base_conductors = nullptr, *d_rel_disc = nullptr, *d_orders = nullptr;
    float *d_lifted_traces = nullptr, *d_lifted_cond = nullptr, *d_solvability = nullptr;

    cudaError_t err;

    err = cudaMalloc((void**)&d_base_traces, traces_size);
    if (err != cudaSuccess) return -2;
    err = cudaMalloc((void**)&d_inertia, traces_size);
    if (err != cudaSuccess) { cudaFree(d_base_traces); return -2; }
    err = cudaMalloc((void**)&d_base_conductors, batch_size_bytes);
    if (err != cudaSuccess) { cudaFree(d_base_traces); cudaFree(d_inertia); return -2; }
    err = cudaMalloc((void**)&d_rel_disc, batch_size_bytes);
    if (err != cudaSuccess) { cudaFree(d_base_traces); cudaFree(d_inertia); cudaFree(d_base_conductors); return -2; }
    err = cudaMalloc((void**)&d_orders, batch_size_bytes);
    if (err != cudaSuccess) { cudaFree(d_base_traces); cudaFree(d_inertia); cudaFree(d_base_conductors); cudaFree(d_rel_disc); return -2; }

    err = cudaMalloc((void**)&d_lifted_traces, traces_size);
    if (err != cudaSuccess) { cudaFree(d_base_traces); cudaFree(d_inertia); cudaFree(d_base_conductors); cudaFree(d_rel_disc); cudaFree(d_orders); return -2; }
    err = cudaMalloc((void**)&d_lifted_cond, batch_size_bytes);
    if (err != cudaSuccess) { cudaFree(d_base_traces); cudaFree(d_inertia); cudaFree(d_base_conductors); cudaFree(d_rel_disc); cudaFree(d_orders); cudaFree(d_lifted_traces); return -2; }
    err = cudaMalloc((void**)&d_solvability, batch_size_bytes);
    if (err != cudaSuccess) { cudaFree(d_base_traces); cudaFree(d_inertia); cudaFree(d_base_conductors); cudaFree(d_rel_disc); cudaFree(d_orders); cudaFree(d_lifted_traces); cudaFree(d_lifted_cond); return -2; }

    cudaMemcpy(d_base_traces, base_traces, traces_size, cudaMemcpyHostToDevice);
    cudaMemcpy(d_inertia, inertia_degrees, traces_size, cudaMemcpyHostToDevice);
    cudaMemcpy(d_base_conductors, base_conductors, batch_size_bytes, cudaMemcpyHostToDevice);
    cudaMemcpy(d_rel_disc, relative_discriminants, batch_size_bytes, cudaMemcpyHostToDevice);
    cudaMemcpy(d_orders, proj_image_orders, batch_size_bytes, cudaMemcpyHostToDevice);

    dim3 grid(batch_size);
    dim3 block(BLOCK_DIM);

    fused_blackwell_langlands_tunnell_base_change_kernel<<<grid, block>>>(
        d_base_traces,
        d_inertia,
        d_base_conductors,
        d_rel_disc,
        d_orders,
        d_lifted_traces,
        d_lifted_cond,
        d_solvability,
        batch_size,
        num_places,
        cyclic_degree
    );

    cudaDeviceSynchronize();

    cudaMemcpy(lifted_traces_out, d_lifted_traces, traces_size, cudaMemcpyDeviceToHost);
    cudaMemcpy(lifted_conductors_log_out, d_lifted_cond, batch_size_bytes, cudaMemcpyDeviceToHost);
    cudaMemcpy(solvability_flags_out, d_solvability, batch_size_bytes, cudaMemcpyDeviceToHost);

    cudaFree(d_base_traces);
    cudaFree(d_inertia);
    cudaFree(d_base_conductors);
    cudaFree(d_rel_disc);
    cudaFree(d_orders);
    cudaFree(d_lifted_traces);
    cudaFree(d_lifted_cond);
    cudaFree(d_solvability);

    return 0;
}

} // extern "C"
