/*
 * csrc/fused_leech24_dequant.cu
 * Ultra-fast CUDA kernel for 24-Dimensional Leech Lattice (Lambda_24) Dequantization.
 * Used for the IMF-100B Leech MoPE architecture.
 * Decodes 24-dimensional vectors from uint16 codebook indices and fp16 scales
 * with unrolled 24-component register-level accumulation on NVIDIA RTX GPUs.
 */

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <torch/extension.h>

__global__ void fused_leech24_dequant_kernel(
    const uint16_t* __restrict__ indices,
    const half* __restrict__ scales,
    const float* __restrict__ codebook, // [684, 24]
    half* __restrict__ out,
    const int num_vectors
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= num_vectors) return;

    uint16_t c_idx = indices[idx];
    half scale = scales[idx];
    float f_scale = __half2float(scale);

    #pragma unroll
    for (int d = 0; d < 24; d++) {
        float root_val = codebook[c_idx * 24 + d];
        out[idx * 24 + d] = __float2half(root_val * f_scale);
    }
}

torch::Tensor fused_leech24_dequantize_cuda(
    torch::Tensor indices,
    torch::Tensor scales,
    torch::Tensor codebook
) {
    TORCH_CHECK(indices.is_cuda(), "indices must be on CUDA");
    TORCH_CHECK(scales.is_cuda(), "scales must be on CUDA");
    TORCH_CHECK(codebook.is_cuda(), "codebook must be on CUDA");

    int num_vectors = indices.numel();
    auto options = torch::TensorOptions().dtype(torch::kFloat16).device(indices.device());
    auto out = torch::empty({num_vectors * 24}, options);

    int block_size = 128;
    int num_blocks = (num_vectors + block_size - 1) / block_size;

    fused_leech24_dequant_kernel<<<num_blocks, block_size>>>(
        reinterpret_cast<const uint16_t*>(indices.data_ptr<int16_t>()),
        reinterpret_cast<const half*>(scales.data_ptr<at::Half>()),
        codebook.data_ptr<float>(),
        reinterpret_cast<half*>(out.data_ptr<at::Half>()),
        num_vectors
    );

    return out;
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("fused_leech24_dequantize", &fused_leech24_dequantize_cuda, "Fused Leech 24D Dequantizer (CUDA)");
}
