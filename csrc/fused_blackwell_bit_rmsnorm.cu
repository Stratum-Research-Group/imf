// csrc/fused_blackwell_bit_rmsnorm.cu
// Production Fused Blackwell SM 12.0 Gated RMSNorm + Residual Add Kernel
// Fuses in-place residual addition x' = x + r, warp-level reciprocal RMS normalization,
// and affine gamma scaling into a single register pass

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

extern "C" __global__ void fused_blackwell_bit_rmsnorm_kernel(
    const float* __restrict__ X,             // [num_rows, hidden_dim]
    const float* __restrict__ Residual,      // [num_rows, hidden_dim]
    const float* __restrict__ Gamma,         // [hidden_dim]
    float* __restrict__ Out,                 // [num_rows, hidden_dim]
    float* __restrict__ Updated_Residual,    // [num_rows, hidden_dim]
    int num_rows,
    int hidden_dim,
    float eps
) {
    int row = blockIdx.x;
    if (row >= num_rows) return;

    size_t row_offset = (size_t)row * hidden_dim;
    const float* x_ptr = X + row_offset;
    const float* r_ptr = Residual + row_offset;
    float* out_ptr = Out + row_offset;
    float* res_out_ptr = (Updated_Residual != nullptr) ? (Updated_Residual + row_offset) : nullptr;

    extern __shared__ float s_sq_sum[];

    // Step 1: Thread-local accumulation of (x + r)^2
    float local_sum_sq = 0.0f;
    for (int i = threadIdx.x; i < hidden_dim; i += blockDim.x) {
        float val = x_ptr[i] + (r_ptr ? r_ptr[i] : 0.0f);
        local_sum_sq += val * val;
        if (res_out_ptr) {
            res_out_ptr[i] = val; // Store updated residual
        }
    }

    s_sq_sum[threadIdx.x] = local_sum_sq;
    __syncthreads();

    // Reduction in shared memory
    for (int stride = blockDim.x / 2; stride > 0; stride >>= 1) {
        if (threadIdx.x < stride) {
            s_sq_sum[threadIdx.x] += s_sq_sum[threadIdx.x + stride];
        }
        __syncthreads();
    }

    float total_sq = s_sq_sum[0];
    float rrms = rsqrtf((total_sq / (float)hidden_dim) + eps);

    // Step 2: Normalize and scale by gamma
    for (int i = threadIdx.x; i < hidden_dim; i += blockDim.x) {
        float val = res_out_ptr ? res_out_ptr[i] : (x_ptr[i] + (r_ptr ? r_ptr[i] : 0.0f));
        float g = Gamma ? Gamma[i] : 1.0f;
        out_ptr[i] = val * rrms * g;
    }
}

extern "C" int launch_fused_blackwell_bit_rmsnorm(
    const float* X,
    const float* Residual,
    const float* Gamma,
    float* Out,
    float* Updated_Residual,
    int num_rows,
    int hidden_dim,
    float eps,
    cudaStream_t stream
) {
    if (!X || !Out || num_rows <= 0 || hidden_dim <= 0) {
        return -1;
    }

    int threads = (hidden_dim <= 256) ? 256 : 512;
    if (threads > 1024) threads = 1024;
    dim3 block(threads);
    dim3 grid(num_rows);
    size_t shared_bytes = threads * sizeof(float);

    fused_blackwell_bit_rmsnorm_kernel<<<grid, block, shared_bytes, stream>>>(
        X, Residual, Gamma, Out, Updated_Residual, num_rows, hidden_dim, eps
    );

    cudaError_t err = cudaGetLastError();
    return (err == cudaSuccess) ? 0 : (int)err;
}
