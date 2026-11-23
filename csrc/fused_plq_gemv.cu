/*
 * csrc/fused_plq_gemv.cu
 * Fused On-The-Fly Matrix-Vector Multiplication (Fused-PLQ-GEMV) for Polytope Lattice Quantization.
 * Computes y = W * x directly from quantized 8-dimensional E8 indices and scales
 * WITHOUT writing decompressed uncompressed weights to global VRAM.
 * Decodes the 8D root vector in GPU shared memory / register tiles.
 */

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <torch/extension.h>

// Tile dimensions: each warp computes an accumulation across a row slice
__global__ void fused_plq_gemv_kernel(
    const uint8_t* __restrict__ indices, // [M, K/8]
    const half* __restrict__ scales,      // [M, K/8]
    const float* __restrict__ codebook,   // [240, 8]
    const half* __restrict__ vec_x,       // [K]
    half* __restrict__ vec_y,             // [M]
    const int M,
    const int K
) {
    int row = blockIdx.x * blockDim.x + threadIdx.x;
    if (row >= M) return;

    float acc = 0.0f;
    int num_vectors = K / 8;

    #pragma unroll 4
    for (int v = 0; v < num_vectors; v++) {
        int idx = row * num_vectors + v;
        uint8_t c_idx = indices[idx];
        float s = __half2float(scales[idx]);

        // Accumulate 8 dimensions on the fly
        #pragma unroll
        for (int d = 0; d < 8; d++) {
            float weight = codebook[c_idx * 8 + d] * s;
            float x_val = __half2float(vec_x[v * 8 + d]);
            acc += weight * x_val;
        }
    }

    vec_y[row] = __float2half(acc);
}

torch::Tensor fused_plq_gemv_cuda(
    torch::Tensor indices,
    torch::Tensor scales,
    torch::Tensor codebook,
    torch::Tensor vec_x
) {
    TORCH_CHECK(indices.is_cuda() && scales.is_cuda() && codebook.is_cuda() && vec_x.is_cuda(), "All tensors must be on CUDA");
    
    int M = indices.size(0);
    int num_vectors = indices.size(1);
    int K = num_vectors * 8;

    auto options = torch::TensorOptions().dtype(torch::kFloat16).device(indices.device());
    auto vec_y = torch::empty({M}, options);

    int block_size = 256;
    int num_blocks = (M + block_size - 1) / block_size;

    fused_plq_gemv_kernel<<<num_blocks, block_size>>>(
        indices.data_ptr<uint8_t>(),
        reinterpret_cast<const half*>(scales.data_ptr<at::Half>()),
        codebook.data_ptr<float>(),
        reinterpret_cast<const half*>(vec_x.data_ptr<at::Half>()),
        reinterpret_cast<half*>(vec_y.data_ptr<at::Half>()),
        M,
        K
    );

    return vec_y;
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("fused_plq_gemv", &fused_plq_gemv_cuda, "Fused On-The-Fly PLQ GEMV (CUDA)");
}
