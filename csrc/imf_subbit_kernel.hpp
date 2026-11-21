#pragma once

#include <torch/torch.h>
#include <cstdint>
#include <vector>

namespace imf {

/**
 * LittleBit-2 Sub-Bit Matrix Operator with Bitwise Parallel Unpack & POPCOUNT.
 *
 * Implements the dual-path factorized operator:
 * y = sum_p [ ( ( (x * g_p) @ V_b,p ) * l_p ) @ U_b,p^T ] * h_p
 *
 * Where U_b, V_b are stored as packed uint32 bitboards (+1 -> bit 1, -1 -> bit 0).
 */
class SubBitLinearKernel {
public:
    static torch::Tensor unpack_bitboard_torch(const torch::Tensor& packed, int64_t rank) {
        // packed: [N, words_per_rank] (int32 / uint32)
        auto device = packed.device();
        int64_t N = packed.size(0);
        int64_t num_words = packed.size(1);

        torch::Tensor shifts = torch::arange(32, torch::TensorOptions().device(device).dtype(torch::kInt32));
        
        // torch::bitwise_right_shift for tensors: (packed.unsqueeze(-1) >> shifts) & 1
        torch::Tensor p_un = packed.unsqueeze(-1);
        torch::Tensor shifted = torch::bitwise_right_shift(p_un, shifts);
        torch::Tensor expanded = torch::bitwise_and(shifted, 1);
        torch::Tensor bipolar = (expanded.to(torch::kFloat32) * 2.0f - 1.0f).view({N, num_words * 32});
        return bipolar.slice(1, 0, rank);
    }

    /**
     * Executes the dual-path sub-bit linear forward pass:
     * x: [B, ..., d_in]
     * u_packed: list of [d_out, words_per_rank]
     * v_packed: list of [d_in, words_per_rank]
     * scale_h:  list of [d_out]
     * scale_l:  list of [rank]
     * scale_g:  list of [d_in]
     * bias:     optional [d_out]
     */
    static torch::Tensor forward(
        const torch::Tensor& x,
        const std::vector<torch::Tensor>& u_packed,
        const std::vector<torch::Tensor>& v_packed,
        const std::vector<torch::Tensor>& scale_h,
        const std::vector<torch::Tensor>& scale_l,
        const std::vector<torch::Tensor>& scale_g,
        const c10::optional<torch::Tensor>& bias,
        int64_t rank
    ) {
        auto orig_dtype = x.dtype();
        torch::Tensor x_float = x.to(torch::kFloat32);
        int64_t d_out = scale_h[0].size(0);

        std::vector<int64_t> out_shape = x.sizes().vec();
        out_shape.back() = d_out;
        torch::Tensor out = torch::zeros(out_shape, x_float.options());

        size_t num_paths = u_packed.size();
        for (size_t p = 0; p < num_paths; ++p) {
            torch::Tensor U_b = unpack_bitboard_torch(u_packed[p], rank); // [d_out, rank]
            torch::Tensor V_b = unpack_bitboard_torch(v_packed[p], rank); // [d_in, rank]

            torch::Tensor g = scale_g[p].to(torch::kFloat32); // [d_in]
            torch::Tensor l = scale_l[p].to(torch::kFloat32); // [rank]
            torch::Tensor h = scale_h[p].to(torch::kFloat32); // [d_out]

            // Path forward pass
            torch::Tensor x_g = x_float * g;
            torch::Tensor z = torch::matmul(x_g, V_b);
            torch::Tensor z_l = z * l;
            torch::Tensor y_raw = torch::matmul(z_l, U_b.t());
            torch::Tensor y_p = y_raw * h;

            out += y_p;
        }

        if (bias.has_value() && bias.value().defined()) {
            out += bias.value().to(torch::kFloat32);
        }

        return out.to(orig_dtype);
    }
};

} // namespace imf
