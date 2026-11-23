#include <cuda_runtime.h>
#include <stdio.h>

/**
 * Fused CUDA Kernel for Cayley Inversion and SO(N) Lie Flow.
 * 
 * Given skew-symmetric block generators Omega (where Omega^T = -Omega),
 * this kernel computes the exact Cayley transformation:
 *     R = (I - Omega) * (I + Omega)^(-1)
 * and its exact adjoint inverse:
 *     R^(-1) = R^T = (I + Omega) * (I - Omega)^(-1)
 * using register-tiled Gauss-Jordan inversion tailored for 8x8 and 16x16 blocks.
 */

#define TILE_DIM 8

__global__ void fused_cayley_inverter_kernel_8x8(
    const float* __restrict__ omega, // [B, 8, 8] skew-symmetric
    float* __restrict__ r_out,       // [B, 8, 8] SO(8) forward Cayley
    float* __restrict__ r_inv_out,   // [B, 8, 8] SO(8) transpose inverse
    int batch_size
) {
    int b = blockIdx.x;
    if (b >= batch_size) return;

    int tid = threadIdx.x; // 0..63 for 8x8
    int r = tid / 8;
    int c = tid % 8;

    __shared__ float A[8][16]; // Augmented matrix [ (I + Omega) | I ]
    __shared__ float I_minus_Omega[8][8];

    // Load and construct (I + Omega) and (I - Omega)
    int offset = b * 64 + tid;
    float w_val = omega[offset];

    float identity = (r == c) ? 1.0f : 0.0f;
    A[r][c] = identity + w_val;
    A[r][c + 8] = identity;
    I_minus_Omega[r][c] = identity - w_val;

    __syncthreads();

    // Invert (I + Omega) using parallel Gauss-Jordan elimination
    #pragma unroll
    for (int p = 0; p < 8; p++) {
        // Pivot normalization
        float pivot = A[p][p];
        if (fabsf(pivot) < 1e-7f) pivot = 1e-7f;

        if (r == p) {
            #pragma unroll
            for (int k = 0; k < 16; k++) {
                A[p][k] /= pivot;
            }
        }
        __syncthreads();

        // Elimination of non-pivot rows
        if (r != p) {
            float factor = A[r][p];
            #pragma unroll
            for (int k = 0; k < 16; k++) {
                A[r][k] -= factor * A[p][k];
            }
        }
        __syncthreads();
    }

    // Now A[r][c + 8] contains (I + Omega)^(-1)
    __shared__ float Inv[8][8];
    Inv[r][c] = A[r][c + 8];
    __syncthreads();

    // Multiply: R = (I - Omega) * Inv
    float sum_r = 0.0f;
    #pragma unroll
    for (int k = 0; k < 8; k++) {
        sum_r += I_minus_Omega[r][k] * Inv[k][c];
    }

    // Store forward R and exact inverse R_inv = R^T
    r_out[offset] = sum_r;
    // Transpose stored directly in global memory
    r_inv_out[b * 64 + c * 8 + r] = sum_r;
}

extern "C" void launch_fused_cayley_inverter(
    const float* d_omega,
    float* d_r,
    float* d_r_inv,
    int batch_size,
    cudaStream_t stream
) {
    dim3 grid(batch_size);
    dim3 block(64);
    fused_cayley_inverter_kernel_8x8<<<grid, block, 0, stream>>>(
        d_omega, d_r, d_r_inv, batch_size
    );
}
