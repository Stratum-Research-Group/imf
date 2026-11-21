#pragma once

#include <torch/torch.h>
#include <cstdint>
#include <vector>
#include <cmath>

namespace imf {

/**
 * Native 24-Dimensional Leech Lattice (\Lambda_24) Sub-Bit GEMV Kernel.
 *
 * Implements high-throughput hardware forward pass for matrices quantized
 * into minimal roots of the Leech lattice (196,560 minimal roots in R^24).
 *
 * Weight Representation:
 * - Each 24D weight slice is indexed by an 18-bit integer (0 .. 196,559).
 * - Indices are packed into 32-bit registers (e.g. stored with zero padding or packed).
 * - Vector norms are scaled with 16-bit block multipliers (scale block size = 48 or 72 weights).
 *
 * Effective Bits / Weight: 18 / 24 = 0.75 bpw (+ 0.25 bpw scale = 1.00 bpw).
 * Minimal root norm: ||v|| = sqrt(8) = 2.828427f.
 */
class LeechLatticeKernel {
public:
    /**
     * Unpacks a batch of 24D Leech root indices into normalized 24D floating-point vectors.
     * indices: [num_vecs] (int32 or int64 in range 0 .. 196,559)
     * codebook: [196560, 24] or structured Golay generator
     */
    static torch::Tensor decode_roots(
        const torch::Tensor& indices,
        const torch::Tensor& leech_root_codebook
    ) {
        auto device = indices.device();
        torch::Tensor flat_idx = indices.reshape({-1}).to(torch::kLong);
        // Look up 24D roots: [num_vecs, 24]
        torch::Tensor roots = torch::index_select(leech_root_codebook.to(device), 0, flat_idx);
        // Normalize: minimal Leech roots have norm sqrt(8)
        return roots * (1.0f / 2.8284271247f);
    }

    /**
     * High-speed forward matrix-vector multiplication with Leech Lattice weights:
     * x: [B, ..., d_in]
     * indices: [d_out, d_in / 24] (int32 storing root indices)
     * scales:  [d_out, d_in / scale_block_size] (float16 or float32 block norms)
     * codebook: [196560, 24] minimal Leech vectors
     * bias: optional [d_out]
     */
    static torch::Tensor forward(
        const torch::Tensor& x,
        const torch::Tensor& indices,
        const torch::Tensor& scales,
        const torch::Tensor& leech_root_codebook,
        const c10::optional<torch::Tensor>& bias,
        int64_t scale_block_size = 48
    ) {
        auto orig_dtype = x.dtype();
        auto device = x.device();
        int64_t d_out = indices.size(0);
        int64_t d_in = indices.size(1) * 24;

        torch::Tensor x_flat = x.reshape({-1, d_in}).to(torch::kFloat32);
        
        // Decode weight matrix
        torch::Tensor roots = decode_roots(indices, leech_root_codebook); // [d_out * (d_in / 24), 24]
        torch::Tensor W_raw = roots.reshape({d_out, -1, scale_block_size});
        
        // Apply block scales
        torch::Tensor scales_exp = scales.to(device).to(torch::kFloat32).unsqueeze(-1);
        torch::Tensor W = (W_raw * scales_exp).reshape({d_out, d_in});

        // Compute GEMM
        torch::Tensor out_flat = torch::matmul(x_flat, W.t());
        if (bias.has_value() && bias.value().defined()) {
            out_flat += bias.value().to(device).to(torch::kFloat32);
        }

        std::vector<int64_t> out_shape = x.sizes().vec();
        out_shape.back() = d_out;
        return out_flat.reshape(out_shape).to(orig_dtype);
    }
};

} // namespace imf
