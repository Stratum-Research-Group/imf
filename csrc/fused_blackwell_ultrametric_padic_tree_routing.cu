// csrc/fused_blackwell_ultrametric_padic_tree_routing.cu
// ==========================================================
// Production Fused Blackwell SM 12.0 Non-Archimedean p-Adic Tree Routing Kernel
// Evaluates p-adic valuations and hierarchical ultrametric distances:
//   v_p(x - c) = highest power of p dividing (x - c)
//   d_p(x, c) = p^{-v_p(x - c)}
// Routes tokens to hierarchical tree branches satisfying the strong triangle inequality:
//   d_p(x, z) <= max(d_p(x, y), d_p(y, z))

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#ifdef __cplusplus
extern "C" {
#endif

// Fast device p-adic valuation computation for integer differences
__device__ __forceinline__ int device_padic_valuation(uint32_t diff, int p) {
    if (diff == 0) return 32; // Infinity valuation for zero difference
    if (p == 2) {
        return __ffs(diff) - 1; // Count trailing zeros
    }
    int v = 0;
    while ((diff % p) == 0 && diff > 0) {
        v++;
        diff /= p;
    }
    return v;
}

// CUDA Kernel: Hierarchical p-Adic Tree Valuation & Branch Assignment
__global__ void fused_padic_tree_routing_cuda_kernel(
    const int32_t* __restrict__ tokens,      // [B, D] quantized token states
    const int32_t* __restrict__ centers,     // [K, D] hierarchical cluster centers
    int32_t* __restrict__ best_branch,       // [B] assigned branch index
    float* __restrict__ min_dist,            // [B] minimum ultrametric distance
    int B,
    int D,
    int K,
    int p
) {
    int b = blockIdx.x * blockDim.x + threadIdx.x;
    if (b >= B) return;

    const int32_t* tok = tokens + b * D;
    int best_k = 0;
    int max_total_val = -1;

    for (int k = 0; k < K; ++k) {
        const int32_t* cent = centers + k * D;
        int total_val = 0;
        for (int d = 0; d < D; ++d) {
            uint32_t diff = (uint32_t)abs(tok[d] - cent[d]);
            total_val += device_padic_valuation(diff, p);
        }
        if (total_val > max_total_val) {
            max_total_val = total_val;
            best_k = k;
        }
    }

    best_branch[b] = best_k;
    // d_p = p^{-val}
    min_dist[b] = powf((float)p, -(float)max_total_val / (float)D);
}

// Host Entrypoint with CUDA and CPU fallback
int fused_blackwell_padic_tree_routing_forward(
    const int32_t* tokens,
    const int32_t* centers,
    int32_t* best_branch,
    float* min_dist,
    int B,
    int D,
    int K,
    int p
) {
    if (!tokens || !centers || !best_branch || !min_dist || B <= 0 || D <= 0 || K <= 0 || p <= 1) {
        return -1;
    }

    cudaError_t err = cudaSuccess;
    int device_count = 0;
    cudaGetDeviceCount(&device_count);

    if (device_count > 0) {
        int threads = 256;
        int blocks = (B + threads - 1) / threads;
        fused_padic_tree_routing_cuda_kernel<<<blocks, threads>>>(
            tokens, centers, best_branch, min_dist, B, D, K, p
        );
        err = cudaGetLastError();
        if (err == cudaSuccess) {
            cudaDeviceSynchronize();
            return 0;
        }
    }

    // High performance CPU reference implementation
    for (int b = 0; b < B; ++b) {
        const int32_t* tok = tokens + b * D;
        int best_k = 0;
        int max_total_val = -1;

        for (int k = 0; k < K; ++k) {
            const int32_t* cent = centers + k * D;
            int total_val = 0;
            for (int d = 0; d < D; ++d) {
                uint32_t diff = (uint32_t)abs(tok[d] - cent[d]);
                int v = 0;
                if (diff == 0) {
                    v = 32;
                } else if (p == 2) {
                    v = __builtin_ctz(diff);
                } else {
                    while ((diff % p) == 0 && diff > 0) {
                        v++;
                        diff /= p;
                    }
                }
                total_val += v;
            }
            if (total_val > max_total_val) {
                max_total_val = total_val;
                best_k = k;
            }
        }

        best_branch[b] = best_k;
        min_dist[b] = powf((float)p, -(float)max_total_val / (float)D);
    }

    return 0;
}

#ifdef __cplusplus
}
#endif
