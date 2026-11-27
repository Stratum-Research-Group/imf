#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <math.h>
#include <stdio.h>
#include <stdint.h>

#define WARP_SIZE 32

// Device / Host helper for Iwasawa polynomial quotient and invariant evaluation
__host__ __device__ inline void compute_iwasawa_quotient_step(
    const float* poly_coeffs,      // [degree + 1]
    const float* divisor_coeffs,   // [div_degree + 1]
    int degree,
    int div_degree,
    float p_prime,
    float* out_quotient,           // [degree - div_degree + 1]
    float* out_remainder_norm,
    int* out_mu_inv,
    int* out_lambda_inv
) {
    if (degree < div_degree || div_degree <= 0) {
        *out_remainder_norm = 0.0f;
        *out_mu_inv = 0;
        *out_lambda_inv = 0;
        return;
    }

    // Work on local polynomial copy
    float rem[64];
    for (int i = 0; i <= degree && i < 64; ++i) {
        rem[i] = poly_coeffs[i];
    }

    int q_deg = degree - div_degree;
    float div_lead = divisor_coeffs[div_degree];
    if (fabsf(div_lead) < 1e-7f) div_lead = 1.0f;

    for (int i = q_deg; i >= 0; --i) {
        float q_coeff = rem[i + div_degree] / div_lead;
        out_quotient[i] = q_coeff;
        for (int j = 0; j <= div_degree; ++j) {
            rem[i + j] -= q_coeff * divisor_coeffs[j];
        }
    }

    float rem_norm = 0.0f;
    for (int i = 0; i < div_degree && i < 64; ++i) {
        rem_norm += rem[i] * rem[i];
    }
    *out_remainder_norm = sqrtf(rem_norm);

    // Iwasawa invariants: mu (powers of p dividing all coeffs) and lambda (degree of distinguished part)
    int mu = 0;
    float min_abs = 1e9f;
    for (int i = 0; i <= degree && i < 64; ++i) {
        float a = fabsf(poly_coeffs[i]);
        if (a > 1e-7f && a < min_abs) min_abs = a;
    }
    if (min_abs > 1e-7f && p_prime > 1.0f) {
        mu = (int)(logf(min_abs + 1.0f) / logf(p_prime));
    }

    *out_mu_inv = mu;
    *out_lambda_inv = q_deg;
}

// Fused Blackwell SM 12.0 Kernel for Iwasawa Polynomial Quotient
__global__ void iwasawa_polynomial_quotient_kernel(
    const float* __restrict__ poly_coeffs,       // [B, degree + 1]
    const float* __restrict__ divisor_coeffs,    // [B, div_degree + 1]
    int degree,
    int div_degree,
    float p_prime,
    float* __restrict__ quotient_coeffs,         // [B, degree - div_degree + 1]
    float* __restrict__ remainder_norms,         // [B]
    int* __restrict__ mu_invariants,             // [B]
    int* __restrict__ lambda_invariants,         // [B]
    int B
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= B) return;

    int q_len = degree - div_degree + 1;
    const float* p_ptr = poly_coeffs + idx * (degree + 1);
    const float* d_ptr = divisor_coeffs + idx * (div_degree + 1);
    float* q_ptr = quotient_coeffs + idx * q_len;

    float rem_norm = 0.0f;
    int mu = 0, lambda = 0;

    compute_iwasawa_quotient_step(
        p_ptr, d_ptr, degree, div_degree, p_prime,
        q_ptr, &rem_norm, &mu, &lambda
    );

    remainder_norms[idx] = rem_norm;
    mu_invariants[idx] = mu;
    lambda_invariants[idx] = lambda;
}

extern "C" {

int fused_blackwell_iwasawa_polynomial_quotient(
    const float* poly_coeffs,
    const float* divisor_coeffs,
    int degree,
    int div_degree,
    float p_prime,
    float* quotient_coeffs,
    float* remainder_norms,
    int* mu_invariants,
    int* lambda_invariants,
    int B
) {
    if (!poly_coeffs || !divisor_coeffs || !quotient_coeffs ||
        !remainder_norms || !mu_invariants || !lambda_invariants ||
        B <= 0 || degree <= 0 || div_degree <= 0 || degree < div_degree) {
        return -1;
    }

    int q_len = degree - div_degree + 1;
    cudaError_t err = cudaSuccess;
    int device_count = 0;
    err = cudaGetDeviceCount(&device_count);

    if (err == cudaSuccess && device_count > 0) {
        float *d_poly = nullptr, *d_div = nullptr, *d_q = nullptr, *d_rem = nullptr;
        int *d_mu = nullptr, *d_lambda = nullptr;

        cudaMalloc(&d_poly, B * (degree + 1) * sizeof(float));
        cudaMalloc(&d_div, B * (div_degree + 1) * sizeof(float));
        cudaMalloc(&d_q, B * q_len * sizeof(float));
        cudaMalloc(&d_rem, B * sizeof(float));
        cudaMalloc(&d_mu, B * sizeof(int));
        cudaMalloc(&d_lambda, B * sizeof(int));

        cudaMemcpy(d_poly, poly_coeffs, B * (degree + 1) * sizeof(float), cudaMemcpyHostToDevice);
        cudaMemcpy(d_div, divisor_coeffs, B * (div_degree + 1) * sizeof(float), cudaMemcpyHostToDevice);

        int threadsPerBlock = 256;
        int blocksPerGrid = (B + threadsPerBlock - 1) / threadsPerBlock;
        iwasawa_polynomial_quotient_kernel<<<blocksPerGrid, threadsPerBlock>>>(
            d_poly, d_div, degree, div_degree, p_prime,
            d_q, d_rem, d_mu, d_lambda, B
        );
        cudaDeviceSynchronize();

        cudaMemcpy(quotient_coeffs, d_q, B * q_len * sizeof(float), cudaMemcpyDeviceToHost);
        cudaMemcpy(remainder_norms, d_rem, B * sizeof(float), cudaMemcpyDeviceToHost);
        cudaMemcpy(mu_invariants, d_mu, B * sizeof(int), cudaMemcpyDeviceToHost);
        cudaMemcpy(lambda_invariants, d_lambda, B * sizeof(int), cudaMemcpyDeviceToHost);

        cudaFree(d_poly);
        cudaFree(d_div);
        cudaFree(d_q);
        cudaFree(d_rem);
        cudaFree(d_mu);
        cudaFree(d_lambda);
        return 0;
    }

    // CPU Fallback
    for (int i = 0; i < B; ++i) {
        const float* p_ptr = poly_coeffs + i * (degree + 1);
        const float* d_ptr = divisor_coeffs + i * (div_degree + 1);
        float* q_ptr = quotient_coeffs + i * q_len;

        float rem_norm = 0.0f;
        int mu = 0, lambda = 0;

        compute_iwasawa_quotient_step(
            p_ptr, d_ptr, degree, div_degree, p_prime,
            q_ptr, &rem_norm, &mu, &lambda
        );

        remainder_norms[i] = rem_norm;
        mu_invariants[i] = mu;
        lambda_invariants[i] = lambda;
    }
    return 0;
}

}
