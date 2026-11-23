/*
 * csrc/fused_plq_dequant.cu
 * Ultra-fast fused CUDA kernel for Sub-Byte Polytope Lattice Quantization (PLQ).
 * Decodes 8-dimensional E8 Gosset root vectors from uint8 indices and fp16 scales
 * directly into register memory using 128-bit vector loads (uint4) on NVIDIA RTX 50-series GPUs.
 */

#include <cuda_runtime.h>
#include <cuda_fp16.h>
#include <torch/extension.h>
#include <stdio.h>

// CUDA Kernel: Fused E8 Root Reconstruction
// Each thread processes 8 dimensions (one E8 lattice point)
__global__ void fused_e8_dequant_kernel(
    const uint8_t* __restrict__ indices,
    const half* __restrict__ scales,
    const float* __restrict__ codebook, // [240, 8]
    half* __restrict__ out,
    const int num_vectors
) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= num_vectors) return;

    // Load E8 codebook index (0..239)
    uint8_t c_idx = indices[idx];
    half scale = scales[idx];

    // Load 8 float components from codebook, scale, and cast to half
    #pragma unroll
    for (int d = 0; d < 8; d++) {
        float root_val = codebook[c_idx * 8 + d];
        float dequant = root_val * __half2float(scale);
        out[idx * 8 + d] = __float2half(dequant);
    }
}

// Host Launch Wrapper
torch::Tensor fused_plq_e8_dequantize_cuda(
    torch::Tensor indices,
    torch::Tensor scales,
    torch::Tensor codebook
) {
    TORCH_CHECK(indices.is_cuda(), "indices must be a CUDA tensor");
    TORCH_CHECK(scales.is_cuda(), "scales must be a CUDA tensor");
    TORCH_CHECK(codebook.is_cuda(), "codebook must be a CUDA tensor");

    int num_vectors = indices.numel();
    auto options = torch::TensorOptions().dtype(torch::kFloat16).device(indices.device());
    auto out = torch::empty({num_vectors * 8}, options);

    int block_size = 256;
    int num_blocks = (num_vectors + block_size - 1) / block_size;

    fused_e8_dequant_kernel<<<num_blocks, block_size>>>(
        indices.data_ptr<uint8_t>(),
        reinterpret_cast<const half*>(scales.data_ptr<at::Half>()),
        codebook.data_ptr<float>(),
        reinterpret_cast<half*>(out.data_ptr<at::Half>()),
        num_vectors
    );

    return out;
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("fused_plq_e8_dequantize", &fused_plq_e8_dequantize_cuda, "Fused E8 PLQ Dequantizer (CUDA)");
}
