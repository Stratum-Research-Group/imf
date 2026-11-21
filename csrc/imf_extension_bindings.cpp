#include <torch/extension.h>
#include "imf_leech24_kernel.hpp"
#include "imf_subbit_kernel.hpp"

torch::Tensor leech24_forward_binding(
    const torch::Tensor& x,
    const torch::Tensor& indices,
    const torch::Tensor& scales,
    const torch::Tensor& leech_root_codebook,
    const c10::optional<torch::Tensor>& bias,
    int64_t scale_block_size
) {
    return imf::LeechLatticeKernel::forward(x, indices, scales, leech_root_codebook, bias, scale_block_size);
}

torch::Tensor leech24_decode_binding(
    const torch::Tensor& indices,
    const torch::Tensor& leech_root_codebook
) {
    return imf::LeechLatticeKernel::decode_roots(indices, leech_root_codebook);
}

torch::Tensor subbit_unpack_bitboard_binding(
    const torch::Tensor& packed,
    int64_t rank
) {
    return imf::SubBitLinearKernel::unpack_bitboard_torch(packed, rank);
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("leech24_forward", &leech24_forward_binding, "Leech 24D Fused Sub-Bit GEMV Forward");
    m.def("leech24_decode", &leech24_decode_binding, "Leech 24D Root Index Decoder");
    m.def("unpack_bitboard", &subbit_unpack_bitboard_binding, "Sub-Bit Bitboard Unpack Kernel");
}
