// csrc/fused_blackwell_swiglu_mlp.cu
// ===================================
// Production Fused Blackwell SM 12.0 SwiGLU Gated MLP Kernel
// High-throughput vectorized Swish-gated linear unit:
// y = (gate * sigmoid(beta * gate)) * up + residual
// Uses 128-bit float4 memory transactions and fast device math.

#include <cuda_runtime.h>
#include <device_launch_parameters.h>
#include <stdint.h>
#include <stdio.h>
#include <math.h>

__device__ __forceinline__ float silu_activate(float g, float beta) {
    return g / (1.0f + __expf(-beta * g));
}

extern "C" __global__ void fused_blackwell_swiglu_mlp_kernel(
    const float* __restrict__ gate,     // [batch_size, hidden_dim]
    const float* __restrict__ up,       // [batch_size, hidden_dim]
    const float* __restrict__ residual, // [batch_size, hidden_dim] (optional, can be null)
    float* __restrict__ y_out,          // [batch_size, hidden_dim]
    size_t total_elements,
    float beta
) {
    size_t idx = ((size_t)blockIdx.x * blockDim.x + threadIdx.x) * 4;
    if (idx >= total_elements) return;

    // Vectorized 128-bit float4 loads
    if (idx + 3 < total_elements) {
        float4 g4 = *reinterpret_cast<const float4*>(gate + idx);
        float4 u4 = *reinterpret_cast<const float4*>(up + idx);
        float4 r4 = {0.0f, 0.0f, 0.0f, 0.0f};
        if (residual) {
            r4 = *reinterpret_cast<const float4*>(residual + idx);
        }

        float4 out4;
        out4.x = silu_activate(g4.x, beta) * u4.x + r4.x;
        out4.y = silu_activate(g4.y, beta) * u4.y + r4.y;
        out4.z = silu_activate(g4.z, beta) * u4.z + r4.z;
        out4.w = silu_activate(g4.w, beta) * u4.w + r4.w;

        *reinterpret_cast<float4*>(y_out + idx) = out4;
    } else {
        // Scalar boundary handling
        for (size_t i = 0; i < 4 && (idx + i) < total_elements; ++i) {
            float g = gate[idx + i];
            float u = up[idx + i];
            float r = residual ? residual[idx + i] : 0.0f;
            y_out[idx + i] = silu_activate(g, beta) * u + r;
        }
    }
}

extern "C" int launch_fused_blackwell_swiglu_mlp(
    const float* gate,
    const float* up,
    const float* residual,
    float* y_out,
    int batch_size,
    int hidden_dim,
    float beta,
    cudaStream_t stream
) {
    if (!gate || !up || !y_out || batch_size <= 0 || hidden_dim <= 0) {
        return -1;
    }

    size_t total_elements = (size_t)batch_size * hidden_dim;
    int threads = 256;
    size_t elements_per_block = (size_t)threads * 4;
    size_t blocks = (total_elements + elements_per_block - 1) / elements_per_block;

    fused_blackwell_swiglu_mlp_kernel<<<blocks, threads, 0, stream>>>(
        gate, up, residual, y_out, total_elements, beta
    );

    cudaError_t err = cudaGetLastError();
    return (err == cudaSuccess) ? 0 : (int)err;
}
