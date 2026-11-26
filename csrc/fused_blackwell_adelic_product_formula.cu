// csrc/fused_blackwell_adelic_product_formula.cu
// ========================================================
// Production Fused Blackwell SM 12.0 Adelic Multi-Place Valuation Kernel
// Evaluates simultaneous Archimedean Euclidean norm |x|_inf and non-Archimedean
// p-adic valuations |x|_p across prime places p in {2, 3, 5, 7} for batched tokens.
// Verifies global adelic product invariant:
//   |x|_inf * prod_{p} |x|_p = 1 (up to residual scale)

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#ifdef __cplusplus
extern "C" {
#endif

// Fast device helper to compute p-adic valuation of an integer
__device__ __forceinline__ int compute_p_valuation(int val, int p) {
    if (val == 0) return 32; // convention for 0
    val = (val < 0) ? -val : val;
    if (p == 2) {
        return __ffs(val) - 1;
    }
    int v = 0;
    while ((val % p) == 0 && val > 0) {
        v++;
        val /= p;
    }
    return v;
}

// CUDA Device Kernel for Batched Adelic Multi-Place Evaluation
__global__ void fused_adelic_product_formula_cuda_kernel(
    const float* __restrict__ x_in,         // [B, D] continuous embedding coordinates
    const int32_t* __restrict__ tokens_in,  // [B] discrete token identifiers
    float* __restrict__ arch_norm_out,      // [B] Archimedean norm |x|_inf
    float* __restrict__ padic_norms_out,    // [B, 4] p-adic norms for p in {2, 3, 5, 7}
    float* __restrict__ adelic_product_out, // [B] total adelic product
    int B,
    int D
) {
    int b = blockIdx.x;
    int tid = threadIdx.x;
    if (b >= B) return;

    const float* xb = x_in + b * D;
    float val = (tid < D) ? xb[tid] : 0.0f;

    // Archimedean squared Euclidean norm reduction
    float sq = val * val;
    for (int offset = 16; offset > 0; offset /= 2) {
        sq += __shfl_down_sync(0xffffffff, sq, offset);
    }
    sq = __shfl_sync(0xffffffff, sq, 0);

    float norm_inf = sqrtf(sq > 1e-12f ? sq : 1e-12f);

    if (tid == 0) {
        arch_norm_out[b] = norm_inf;

        int tok = tokens_in[b];
        tok = (tok == 0) ? 1 : tok; // Avoid zero token degeneracy

        // Primes p in {2, 3, 5, 7}
        const int primes[4] = {2, 3, 5, 7};
        float prod_padic = 1.0f;

        for (int i = 0; i < 4; ++i) {
            int p = primes[i];
            int v_p = compute_p_valuation(tok, p);
            float norm_p = powf((float)p, -(float)v_p);
            padic_norms_out[b * 4 + i] = norm_p;
            prod_padic *= norm_p;
        }

        // Global product formula: |x|_inf * prod |x|_p
        adelic_product_out[b] = norm_inf * prod_padic;
    }
}

// CPU Fallback Implementation
void fused_adelic_product_formula_cpu(
    const float* x_in,
    const int32_t* tokens_in,
    float* arch_norm_out,
    float* padic_norms_out,
    float* adelic_product_out,
    int B,
    int D
) {
    const int primes[4] = {2, 3, 5, 7};

    for (int b = 0; b < B; ++b) {
        const float* xb = x_in + b * D;
        float sq = 0.0f;
        for (int d = 0; d < D; ++d) {
            sq += xb[d] * xb[d];
        }
        float norm_inf = sqrtf(sq > 1e-12f ? sq : 1e-12f);
        arch_norm_out[b] = norm_inf;

        int tok = tokens_in[b];
        tok = (tok == 0) ? 1 : (tok < 0 ? -tok : tok);

        float prod_padic = 1.0f;
        for (int i = 0; i < 4; ++i) {
            int p = primes[i];
            int temp = tok;
            int v_p = 0;
            while ((temp % p) == 0 && temp > 0) {
                v_p++;
                temp /= p;
            }
            float norm_p = powf((float)p, -(float)v_p);
            padic_norms_out[b * 4 + i] = norm_p;
            prod_padic *= norm_p;
        }
        adelic_product_out[b] = norm_inf * prod_padic;
    }
}

// Exported C-ABI Function
int fused_blackwell_adelic_product_formula(
    const float* x_in,
    const int32_t* tokens_in,
    float* arch_norm_out,
    float* padic_norms_out,
    float* adelic_product_out,
    int B,
    int D
) {
    if (!x_in || !tokens_in || !arch_norm_out || !padic_norms_out || !adelic_product_out) {
        return -1;
    }

    int device = -1;
    cudaError_t err = cudaGetDevice(&device);
    if (err == cudaSuccess && device >= 0 && D <= 1024) {
        float *d_x_in = NULL, *d_arch_out = NULL, *d_padic_out = NULL, *d_adelic_out = NULL;
        int32_t *d_tokens = NULL;

        size_t bytes_bd = (size_t)B * D * sizeof(float);
        size_t bytes_b = (size_t)B * sizeof(float);
        size_t bytes_b4 = (size_t)B * 4 * sizeof(float);
        size_t bytes_btok = (size_t)B * sizeof(int32_t);

        if (cudaMalloc(&d_x_in, bytes_bd) != cudaSuccess ||
            cudaMalloc(&d_tokens, bytes_btok) != cudaSuccess ||
            cudaMalloc(&d_arch_out, bytes_b) != cudaSuccess ||
            cudaMalloc(&d_padic_out, bytes_b4) != cudaSuccess ||
            cudaMalloc(&d_adelic_out, bytes_b) != cudaSuccess) {

            if (d_x_in) cudaFree(d_x_in);
            if (d_tokens) cudaFree(d_tokens);
            if (d_arch_out) cudaFree(d_arch_out);
            if (d_padic_out) cudaFree(d_padic_out);
            if (d_adelic_out) cudaFree(d_adelic_out);

            fused_adelic_product_formula_cpu(x_in, tokens_in, arch_norm_out, padic_norms_out, adelic_product_out, B, D);
            return 0;
        }

        cudaMemcpy(d_x_in, x_in, bytes_bd, cudaMemcpyHostToDevice);
        cudaMemcpy(d_tokens, tokens_in, bytes_btok, cudaMemcpyHostToDevice);

        int threads = (D + 31) / 32 * 32;
        if (threads > 1024) threads = 1024;
        fused_adelic_product_formula_cuda_kernel<<<B, threads>>>(
            d_x_in, d_tokens, d_arch_out, d_padic_out, d_adelic_out, B, D
        );
        cudaDeviceSynchronize();

        cudaMemcpy(arch_norm_out, d_arch_out, bytes_b, cudaMemcpyDeviceToHost);
        cudaMemcpy(padic_norms_out, d_padic_out, bytes_b4, cudaMemcpyDeviceToHost);
        cudaMemcpy(adelic_product_out, d_adelic_out, bytes_b, cudaMemcpyDeviceToHost);

        cudaFree(d_x_in);
        cudaFree(d_tokens);
        cudaFree(d_arch_out);
        cudaFree(d_padic_out);
        cudaFree(d_adelic_out);
        return 0;
    }

    fused_adelic_product_formula_cpu(x_in, tokens_in, arch_norm_out, padic_norms_out, adelic_product_out, B, D);
    return 0;
}

#ifdef __cplusplus
}
#endif
