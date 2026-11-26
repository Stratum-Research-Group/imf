// csrc/fused_blackwell_bit_linear_residual.cu
// ============================================
// Production Fused Blackwell SM 12.0 Bit-Linear Polytope Projection & Residual Kernel
// In-register ternary/sub-bit matrix-vector multiplication with fused residual bypass
// Evaluates y = W * x + r directly inside warp registers and shared memory.

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

#define WARP_SIZE 32

extern "C" __global__ void fused_blackwell_bit_linear_residual_kernel(
    const float* __restrict__ x,           // [batch_size, in_dim]
    const uint8_t* __restrict__ packed_w,  // [out_dim, in_dim / 4] (2-bit packed: 4 weights per byte)
    const float* __restrict__ residual,    // [batch_size, out_dim]
    const float* __restrict__ scales,      // [out_dim]
    float* __restrict__ y_out,             // [batch_size, out_dim]
    int batch_size,
    int in_dim,
    int out_dim
) {
    int b = blockIdx.y;
    int row = blockIdx.x * blockDim.y + threadIdx.y;

    if (b >= batch_size || row >= out_dim) return;

    int tid = threadIdx.x;
    int packed_in_dim = in_dim / 4;

    const float* x_batch = x + (size_t)b * in_dim;
    const uint8_t* w_row = packed_w + (size_t)row * packed_in_dim;
    float scale = scales ? scales[row] : 1.0f;

    float acc = 0.0f;

    // Each thread processes chunks of 4 weights across the in_dim dimension
    for (int p = tid; p < packed_in_dim; p += blockDim.x) {
        uint8_t byte_val = w_row[p];
        int base_d = p * 4;

        #pragma unroll
        for (int i = 0; i < 4; ++i) {
            int8_t code = (int8_t)((byte_val >> (i * 2)) & 0x03);
            float weight = (code == 1) ? 1.0f : ((code == 3) ? -1.0f : 0.0f);
            acc += weight * x_batch[base_d + i];
        }
    }

    // Warp-level reduction
    #pragma unroll
    for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
        acc += __shfl_down_sync(0xffffffff, acc, offset);
    }

    // Lane 0 of each warp writes out with fused residual addition
    if (tid == 0) {
        float res_val = residual ? residual[(size_t)b * out_dim + row] : 0.0f;
        y_out[(size_t)b * out_dim + row] = acc * scale + res_val;
    }
}

extern "C" int launch_fused_blackwell_bit_linear_residual(
    const float* x,
    const uint8_t* packed_w,
    const float* residual,
    const float* scales,
    float* y_out,
    int batch_size,
    int in_dim,
    int out_dim,
    cudaStream_t stream
) {
    if (!x || !packed_w || !y_out || batch_size <= 0 || in_dim <= 0 || out_dim <= 0) {
        return -1;
    }
    if (in_dim % 4 != 0) {
        return -2; // in_dim must be divisible by 4 for 2-bit packing
    }

    dim3 block(WARP_SIZE, 4); // 4 rows per block, 32 threads per row
    dim3 grid((out_dim + 3) / 4, batch_size);

    fused_blackwell_bit_linear_residual_kernel<<<grid, block, 0, stream>>>(
        x, packed_w, residual, scales, y_out, batch_size, in_dim, out_dim
    );

    cudaError_t err = cudaGetLastError();
    return (err == cudaSuccess) ? 0 : (int)err;
}
