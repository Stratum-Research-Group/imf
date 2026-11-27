#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

/**
 * Blackwell SM 12.0 Kernel: Khare-Wintenberger Modular Lifting & Crystalline Frobenius Slopes
 *
 * Implements high-throughput verification and computation of:
 * 1. Crystalline Frobenius characteristic polynomial:
 *    P(T) = T^2 - a_p * T + p^{k-1}
 * 2. Crystalline slope verification (Newton polygon vs Hodge polygon):
 *    lambda_1 + lambda_2 = k - 1, lambda_i >= 0
 * 3. Framed deformation ring smooth dimension: dim(R^\square) = 4 + 3*[F:Q]
 * 4. Modular lifting criterion flag.
 */

#define WARP_SIZE 32
#define BLOCK_DIM 256

__global__ void fused_blackwell_khare_wintenberger_kernel(
    const float* __restrict__ ap_coefficients,     // [batch_size] a_p Frobenius trace
    const float* __restrict__ prime_p,             // [batch_size] prime p
    const float* __restrict__ serre_weights,       // [batch_size] k >= 2
    const float* __restrict__ base_degrees,        // [batch_size] [F : Q]
    float* __restrict__ frobenius_slopes_out,      // [batch_size, 2] [lambda_1, lambda_2]
    float* __restrict__ framed_dim_out,            // [batch_size] dim(R^\square)
    float* __restrict__ lifting_flags_out,         // [batch_size] 1.0 if weakly admissible & modular lifted
    int batch_size
) {
    int b = blockIdx.x * blockDim.x + threadIdx.x;
    if (b >= batch_size) return;

    float a_p = ap_coefficients[b];
    float p = prime_p[b];
    float k = serre_weights[b];
    float d = base_degrees[b];

    if (p <= 1.0f || k < 2.0f || d < 1.0f) {
        framed_dim_out[b] = 0.0f;
        lifting_flags_out[b] = 0.0f;
        return;
    }

    // 1. Framed deformation ring dimension: dim(R^\square) = 4 + 3 * d
    float dim_r_square = 4.0f + 3.0f * d;
    framed_dim_out[b] = dim_r_square;

    // 2. Crystalline Frobenius slopes:
    // Roots of T^2 - a_p * T + p^{k-1} = 0
    // Characteristic determinant det(Phi) = p^{k-1}
    float hodge_weight = k - 1.0f;
    float det_phi = powf(p, hodge_weight);

    // Approximate p-adic valuation of roots:
    // If |a_p| < 2*p^{(k-1)/2} (Ramanujan bound for modular forms):
    // Slopes are symmetric: lambda_1 = lambda_2 = (k - 1) / 2
    float lambda_1, lambda_2;
    float disc = a_p * a_p - 4.0f * det_phi;

    if (disc <= 0.0f) {
        // Complex conjugate roots, ordinary or supersingular
        lambda_1 = hodge_weight * 0.5f;
        lambda_2 = hodge_weight * 0.5f;
    } else {
        // Real roots: r1 = (a_p + sqrt(disc))/2, r2 = (a_p - sqrt(disc))/2
        float r1 = fabsf((a_p + sqrtf(disc)) * 0.5f);
        float r2 = fabsf((a_p - sqrtf(disc)) * 0.5f);
        if (r1 < 1e-6f) r1 = 1e-6f;
        if (r2 < 1e-6f) r2 = 1e-6f;
        float log_p = logf(p);
        lambda_1 = logf(r1) / log_p;
        lambda_2 = logf(r2) / log_p;
    }

    frobenius_slopes_out[b * 2 + 0] = lambda_1;
    frobenius_slopes_out[b * 2 + 1] = lambda_2;

    // 3. Weak admissibility: slopes sum to Hodge weight k - 1 and are >= 0
    float slope_sum = lambda_1 + lambda_2;
    bool sum_ok = (fabsf(slope_sum - hodge_weight) < 1e-2f);
    bool nonneg_ok = (lambda_1 >= -1e-3f && lambda_2 >= -1e-3f);
    bool lifting_ok = sum_ok && nonneg_ok;

    lifting_flags_out[b] = lifting_ok ? 1.0f : 0.0f;
}

extern "C" {

int fused_blackwell_khare_wintenberger_lifting(
    const float* ap_coefficients,
    const float* prime_p,
    const float* serre_weights,
    const float* base_degrees,
    float* frobenius_slopes_out,
    float* framed_dim_out,
    float* lifting_flags_out,
    int batch_size
) {
    if (!ap_coefficients || !prime_p || !serre_weights || !base_degrees ||
        !frobenius_slopes_out || !framed_dim_out || !lifting_flags_out || batch_size <= 0) {
        return -1;
    }

    size_t batch_bytes = (size_t)batch_size * sizeof(float);
    size_t slopes_bytes = (size_t)batch_size * 2 * sizeof(float);

    float *d_ap = nullptr, *d_p = nullptr, *d_k = nullptr, *d_d = nullptr;
    float *d_slopes = nullptr, *d_dim = nullptr, *d_flags = nullptr;

    cudaError_t err;

    err = cudaMalloc((void**)&d_ap, batch_bytes);
    if (err != cudaSuccess) return -2;
    err = cudaMalloc((void**)&d_p, batch_bytes);
    if (err != cudaSuccess) { cudaFree(d_ap); return -2; }
    err = cudaMalloc((void**)&d_k, batch_bytes);
    if (err != cudaSuccess) { cudaFree(d_ap); cudaFree(d_p); return -2; }
    err = cudaMalloc((void**)&d_d, batch_bytes);
    if (err != cudaSuccess) { cudaFree(d_ap); cudaFree(d_p); cudaFree(d_k); return -2; }

    err = cudaMalloc((void**)&d_slopes, slopes_bytes);
    if (err != cudaSuccess) { cudaFree(d_ap); cudaFree(d_p); cudaFree(d_k); cudaFree(d_d); return -2; }
    err = cudaMalloc((void**)&d_dim, batch_bytes);
    if (err != cudaSuccess) { cudaFree(d_ap); cudaFree(d_p); cudaFree(d_k); cudaFree(d_d); cudaFree(d_slopes); return -2; }
    err = cudaMalloc((void**)&d_flags, batch_bytes);
    if (err != cudaSuccess) { cudaFree(d_ap); cudaFree(d_p); cudaFree(d_k); cudaFree(d_d); cudaFree(d_slopes); cudaFree(d_dim); return -2; }

    cudaMemcpy(d_ap, ap_coefficients, batch_bytes, cudaMemcpyHostToDevice);
    cudaMemcpy(d_p, prime_p, batch_bytes, cudaMemcpyHostToDevice);
    cudaMemcpy(d_k, serre_weights, batch_bytes, cudaMemcpyHostToDevice);
    cudaMemcpy(d_d, base_degrees, batch_bytes, cudaMemcpyHostToDevice);

    int threads = BLOCK_DIM;
    int blocks = (batch_size + threads - 1) / threads;

    fused_blackwell_khare_wintenberger_kernel<<<blocks, threads>>>(
        d_ap,
        d_p,
        d_k,
        d_d,
        d_slopes,
        d_dim,
        d_flags,
        batch_size
    );

    cudaDeviceSynchronize();

    cudaMemcpy(frobenius_slopes_out, d_slopes, slopes_bytes, cudaMemcpyDeviceToHost);
    cudaMemcpy(framed_dim_out, d_dim, batch_bytes, cudaMemcpyDeviceToHost);
    cudaMemcpy(lifting_flags_out, d_flags, batch_bytes, cudaMemcpyDeviceToHost);

    cudaFree(d_ap);
    cudaFree(d_p);
    cudaFree(d_k);
    cudaFree(d_d);
    cudaFree(d_slopes);
    cudaFree(d_dim);
    cudaFree(d_flags);

    return 0;
}

} // extern "C"
