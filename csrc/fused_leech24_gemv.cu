/*
 * csrc/fused_leech24_gemv.cu
 * Fused On-The-Fly Matrix-Vector Multiplication for 24-Dimensional Leech Lattice Quantization.
 * Used for the IMF-100B Leech MoPE architecture.
 * Multiplies y = W * x directly from quantized 24D Leech indices and scales
 * WITHOUT writing uncompressed FP16 weights to global VRAM.
 */

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <torch/extension.h>

__global__ void fused_leech24_gemv_kernel(
    const int16_t* __restrict__ indices, // [M, K/24]
    const half* __restrict__ scales,      // [M, K/24]
    const float* __restrict__ codebook,   // [684, 24]
    const half* __restrict__ vec_x,       // [K]
    half* __restrict__ vec_y,             // [M]
    const int M,
    const int K
) {
    int row = blockIdx.x * blockDim.x + threadIdx.x;
    if (row >= M) return;

    float acc = 0.0f;
    int num_vectors = K / 24;

    #pragma unroll 2
    for (int v = 0; v < num_vectors; v++) {
        int idx = row * num_vectors + v;
        int16_t c_idx = indices[idx];
        float s = __half2float(scales[idx]);

        #pragma unroll
        for (int d = 0; d < 24; d++) {
            float weight = codebook[c_idx * 24 + d] * s;
            float x_val = __half2float(vec_x[v * 24 + d]);
            acc += weight * x_val;
        }
    }

    vec_y[row] = __float2half(acc);
}

torch::Tensor fused_leech24_gemv_cuda(
    torch::Tensor indices,
    torch::Tensor scales,
    torch::Tensor codebook,
    torch::Tensor vec_x
) {
    TORCH_CHECK(indices.is_cuda() && scales.is_cuda() && codebook.is_cuda() && vec_x.is_cuda(), "Tensors must be on CUDA");

    int M = indices.size(0);
    int num_vectors = indices.size(1);
    int K = num_vectors * 24;

    auto options = torch::TensorOptions().dtype(torch::kFloat16).device(indices.device());
    auto vec_y = torch::empty({M}, options);

    int block_size = 128;
    int num_blocks = (M + block_size - 1) / block_size;

    fused_leech24_gemv_kernel<<<num_blocks, block_size>>>(
        indices.data_ptr<int16_t>(),
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
    m.def("fused_leech24_gemv", &fused_leech24_gemv_cuda, "Fused Leech 24D GEMV (CUDA)");
}
