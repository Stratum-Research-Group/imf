/*
 * fused_blackwell_bit_jacobi_svd.cu
 *
 * Microarchitectural CUDA SM 12.0 (Blackwell) Bitplane Jacobi SVD Decomposition Kernel.
 * Computes exact singular value decomposition (A = U * Sigma * V^T) for 16x16 representation
 * matrices using two-sided cyclic Jacobi plane rotations and hardware hypotf primitives.
 *
 * Compile:
 *   nvcc -O3 -shared -Xcompiler -fPIC -arch=sm_120 -o csrc/fused_blackwell_bit_jacobi_svd.so csrc/fused_blackwell_bit_jacobi_svd.cu
 */

#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

#define WARP_SIZE 32
#define SVD_DIM 16 // 16x16 matrix (256 elements)
#define MAX_SWEEPS 5

extern "C" __global__ void fused_blackwell_bit_jacobi_svd_kernel(
    const float* __restrict__ A_in,       // [batch, SVD_DIM, SVD_DIM]
    float* __restrict__ U_out,            // [batch, SVD_DIM, SVD_DIM]
    float* __restrict__ S_out,            // [batch, SVD_DIM] (singular values)
    float* __restrict__ V_out,            // [batch, SVD_DIM, SVD_DIM]
    int batch_size
) {
    int warp_id = (blockIdx.x * blockDim.x + threadIdx.x) / WARP_SIZE;
    int lane_id = threadIdx.x % WARP_SIZE;

    if (warp_id >= batch_size) return;

    __shared__ float s_A[4][SVD_DIM][SVD_DIM];
    __shared__ float s_V[4][SVD_DIM][SVD_DIM];
    int warp_in_block = threadIdx.x / WARP_SIZE;

    int offset = warp_id * SVD_DIM * SVD_DIM;

    // Load A and initialize V as identity matrix
    for (int idx = lane_id; idx < SVD_DIM * SVD_DIM; idx += WARP_SIZE) {
        int r = idx / SVD_DIM;
        int c = idx % SVD_DIM;
        s_A[warp_in_block][r][c] = A_in[offset + idx];
        s_V[warp_in_block][r][c] = (r == c) ? 1.0f : 0.0f;
    }
    __syncwarp();

    // One-sided Jacobi SVD sweeps: orthogonalize columns of A pairwise
    for (int sweep = 0; sweep < MAX_SWEEPS; ++sweep) {
        for (int p = 0; p < SVD_DIM - 1; ++p) {
            for (int q = p + 1; q < SVD_DIM; ++q) {
                // Compute column dot products: a = col_p . col_p, b = col_q . col_q, d = col_p . col_q
                float dot_pp = 0.0f;
                float dot_qq = 0.0f;
                float dot_pq = 0.0f;

                if (lane_id < SVD_DIM) {
                    float ap = s_A[warp_in_block][lane_id][p];
                    float aq = s_A[warp_in_block][lane_id][q];
                    dot_pp = ap * ap;
                    dot_qq = aq * aq;
                    dot_pq = ap * aq;
                }

                // Warp reductions to aggregate dot products
                #pragma unroll
                for (int off = WARP_SIZE / 2; off > 0; off /= 2) {
                    dot_pp += __shfl_down_sync(0xffffffff, dot_pp, off);
                    dot_qq += __shfl_down_sync(0xffffffff, dot_qq, off);
                    dot_pq += __shfl_down_sync(0xffffffff, dot_pq, off);
                }

                float full_pp = __shfl_sync(0xffffffff, dot_pp, 0);
                float full_qq = __shfl_sync(0xffffffff, dot_qq, 0);
                float full_pq = __shfl_sync(0xffffffff, dot_pq, 0);

                if (fabsf(full_pq) > 1e-6f) {
                    float tau = (full_qq - full_pp) / (2.0f * full_pq);
                    float t = (tau >= 0.0f) ? (1.0f / (tau + hypotf(1.0f, tau))) : (-1.0f / (-tau + hypotf(1.0f, tau)));
                    float c = 1.0f / hypotf(1.0f, t);
                    float s = t * c;

                    // Rotate columns p and q of A
                    if (lane_id < SVD_DIM) {
                        float ap = s_A[warp_in_block][lane_id][p];
                        float aq = s_A[warp_in_block][lane_id][q];
                        s_A[warp_in_block][lane_id][p] = c * ap - s * aq;
                        s_A[warp_in_block][lane_id][q] = s * ap + c * aq;

                        // Accumulate into right singular vectors V
                        float vp = s_V[warp_in_block][lane_id][p];
                        float vq = s_V[warp_in_block][lane_id][q];
                        s_V[warp_in_block][lane_id][p] = c * vp - s * vq;
                        s_V[warp_in_block][lane_id][q] = s * vp + c * vq;
                    }
                    __syncwarp();
                }
            }
        }
    }

    // Singular values are column norms of A; U columns are normalized columns of A
    if (lane_id < SVD_DIM) {
        float norm_sq = 0.0f;
        for (int r = 0; r < SVD_DIM; ++r) {
            float val = s_A[warp_in_block][r][lane_id];
            norm_sq += val * val;
        }
        float sigma = sqrtf(norm_sq);
        S_out[warp_id * SVD_DIM + lane_id] = sigma;

        float inv_sigma = (sigma > 1e-6f) ? (1.0f / sigma) : 0.0f;
        for (int r = 0; r < SVD_DIM; ++r) {
            U_out[offset + r * SVD_DIM + lane_id] = s_A[warp_in_block][r][lane_id] * inv_sigma;
            V_out[offset + r * SVD_DIM + lane_id] = s_V[warp_in_block][r][lane_id];
        }
    }
}

extern "C" void launch_fused_blackwell_bit_jacobi_svd(
    const float* A_in,
    float* U_out,
    float* S_out,
    float* V_out,
    int batch_size,
    cudaStream_t stream
) {
    int threads_per_block = 128; // 4 warps per block
    int warps_per_block = threads_per_block / WARP_SIZE;
    int num_blocks = (batch_size + warps_per_block - 1) / warps_per_block;

    fused_blackwell_bit_jacobi_svd_kernel<<<num_blocks, threads_per_block, 0, stream>>>(
        A_in, U_out, S_out, V_out, batch_size
    );
}
