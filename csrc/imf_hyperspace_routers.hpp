#pragma once
/**
 * csrc/imf_hyperspace_routers.hpp
 * High-performance Native LibTorch C++ implementations for:
 * 1. MatryoshkaCrossPolytopeRouter (Russian-Doll Factorization in arbitrary D)
 * 2. E8GossetRouter (Optimal Kissing 240-root manifold on S^7)
 * 3. HypercubicHoneycombTiler (Infinite Z^D spatial memory navigation)
 */

#include <torch/torch.h>
#include <ATen/ops/linalg_qr.h>
#include <vector>
#include <cmath>
#include <iostream>

namespace imf {

// =========================================================================
// 1. E8 Gosset 4_21 Polytope (240 Roots on S^7)
// =========================================================================
inline torch::Tensor build_e8_roots_cpp(torch::Device device) {
    std::vector<float> roots;
    roots.reserve(240 * 8);

    // 112 roots: Permutations of (+-1, +-1, 0, 0, 0, 0, 0, 0)
    for (int i = 0; i < 8; ++i) {
        for (int j = i + 1; j < 8; ++j) {
            for (float s1 : {1.0f, -1.0f}) {
                for (float s2 : {1.0f, -1.0f}) {
                    std::vector<float> vec(8, 0.0f);
                    vec[i] = s1;
                    vec[j] = s2;
                    roots.insert(roots.end(), vec.begin(), vec.end());
                }
            }
        }
    }

    // 128 roots: (+-0.5, ..., +-0.5) with even count of negative signs
    for (int mask = 0; mask < 256; ++mask) {
        int neg_count = 0;
        std::vector<float> vec(8);
        for (int b = 0; b < 8; ++b) {
            if ((mask >> b) & 1) {
                vec[b] = -0.5f;
                neg_count++;
            } else {
                vec[b] = 0.5f;
            }
        }
        if (neg_count % 2 == 0) {
            roots.insert(roots.end(), vec.begin(), vec.end());
        }
    }

    auto opts = torch::TensorOptions().dtype(torch::kFloat32).device(torch::kCPU);
    torch::Tensor t = torch::from_blob(roots.data(), {240, 8}, opts).clone();
    t = torch::nn::functional::normalize(t, torch::nn::functional::NormalizeFuncOptions().p(2).dim(-1));
    return device.is_cuda() ? t.to(device) : t;
}

class CppE8GossetRouter {
public:
    int64_t d_model;
    int64_t num_experts;
    int64_t top_k;
    torch::Tensor proj_to_8d; // [8, d_model]
    torch::Tensor e8_roots;   // [240, 8]
    torch::Tensor root_to_expert; // [240]

    CppE8GossetRouter(int64_t d_model, int64_t num_experts = 16, int64_t top_k = 2, torch::Device device = torch::kCUDA)
        : d_model(d_model), num_experts(std::min<int64_t>(num_experts, 240)), top_k(top_k) {
        torch::NoGradGuard no_grad;
        torch::Tensor q = std::get<0>(at::linalg_qr(torch::randn({d_model, 8}, device)));
        proj_to_8d = q.t(); // [8, d_model]
        e8_roots = build_e8_roots_cpp(device);

        root_to_expert = torch::arange(240, torch::TensorOptions().dtype(torch::kInt64).device(device)) % num_experts;
    }

    // Forward routing pass returning top-k expert indices and weights
    std::pair<torch::Tensor, torch::Tensor> forward(const torch::Tensor& x) {
        // x: [B, d_model]
        torch::Tensor h8 = torch::matmul(x, proj_to_8d.t()); // [B, 8]
        h8 = torch::nn::functional::normalize(h8, torch::nn::functional::NormalizeFuncOptions().p(2).dim(-1));
        torch::Tensor e8_logits = torch::matmul(h8, e8_roots.t()) * (1.0f / std::sqrt(8.0f)); // [B, 240]

        // Expert cluster aggregation
        int64_t B = x.size(0);
        torch::Tensor expert_logits = torch::full({B, num_experts}, -1e9f, e8_logits.options());
        for (int64_t exp = 0; exp < num_experts; ++exp) {
            torch::Tensor mask = (root_to_expert == exp);
            expert_logits.index_put_({torch::indexing::Slice(), exp}, std::get<0>(e8_logits.index({"...", mask}).max(-1)));
        }

        auto topk_res = expert_logits.topk(top_k, -1);
        torch::Tensor topk_logits = std::get<0>(topk_res);
        torch::Tensor topk_indices = std::get<1>(topk_res);
        torch::Tensor topk_weights = torch::softmax(topk_logits, -1);
        return {topk_weights, topk_indices};
    }
};

// =========================================================================
// 2. Russian-Doll (Matryoshka) Cross-Polytope Router
// =========================================================================
class CppMatryoshkaCrossPolytopeRouter {
public:
    int64_t d_model;
    int64_t dim_polytope;
    int64_t nesting_depth;
    float scale_decay;
    std::vector<torch::Tensor> level_projections; // K elements of [2*D, d_model]
    std::vector<float> shell_scales;

    CppMatryoshkaCrossPolytopeRouter(int64_t d_model, int64_t dim_polytope = 4, int64_t nesting_depth = 3, float scale_decay = 0.5f, torch::Device device = torch::kCUDA)
        : d_model(d_model), dim_polytope(dim_polytope), nesting_depth(nesting_depth), scale_decay(scale_decay) {
        torch::NoGradGuard no_grad;
        int64_t num_polar = 2 * dim_polytope;

        for (int64_t k = 0; k < nesting_depth; ++k) {
            torch::Tensor q = std::get<0>(at::linalg_qr(torch::randn({d_model, dim_polytope}, device)));
            torch::Tensor basis = q.t(); // [dim_polytope, d_model]
            torch::Tensor vertices = torch::empty({num_polar, d_model}, torch::TensorOptions().dtype(torch::kFloat32).device(device));
            for (int64_t i = 0; i < dim_polytope; ++i) {
                vertices.index_put_({2 * i, torch::indexing::Slice()}, basis.index({i}));
                vertices.index_put_({2 * i + 1, torch::indexing::Slice()}, -basis.index({i}));
            }
            level_projections.push_back(vertices * std::pow(scale_decay, static_cast<float>(k)));
            shell_scales.push_back(std::pow(scale_decay, static_cast<float>(k)));
        }
    }

    int64_t virtual_capacity() const {
        return std::pow(std::pow(2, dim_polytope), nesting_depth);
    }

    // Hierarchical descent down Russian-doll shells
    std::pair<torch::Tensor, torch::Tensor> forward(const torch::Tensor& x) {
        int64_t N = x.size(0);
        torch::Tensor residual = x.clone();
        torch::Tensor accumulated_indices = torch::zeros({N}, torch::TensorOptions().dtype(torch::kInt64).device(x.device()));
        torch::Tensor path_log_probs = torch::zeros({N}, x.options());
        int64_t num_polar = 2 * dim_polytope;

        for (int64_t k = 0; k < nesting_depth; ++k) {
            torch::Tensor proj = level_projections[k];
            float scale = shell_scales[k];

            torch::Tensor norm_proj = torch::nn::functional::normalize(proj, torch::nn::functional::NormalizeFuncOptions().p(2).dim(-1));
            torch::Tensor norm_res = torch::nn::functional::normalize(residual, torch::nn::functional::NormalizeFuncOptions().p(2).dim(-1));

            torch::Tensor logits = torch::matmul(norm_res, norm_proj.t()) / std::sqrt(static_cast<float>(dim_polytope));
            torch::Tensor best_vertex = logits.argmax(-1); // [N]

            int64_t multiplier = std::pow(num_polar, nesting_depth - 1 - k);
            accumulated_indices = accumulated_indices + (best_vertex * multiplier);

            torch::Tensor probs = torch::softmax(logits, -1);
            torch::Tensor selected_probs = probs.gather(-1, best_vertex.unsqueeze(-1)).squeeze(-1); // [N]
            path_log_probs = path_log_probs + torch::log(selected_probs + 1e-9f);

            torch::Tensor chosen_vec = norm_proj.index({best_vertex}); // [N, d_model]
            torch::Tensor proj_len = (residual * chosen_vec).sum(-1, /*keepdim=*/true); // [N, 1]
            residual = residual - (chosen_vec * (scale * proj_len));
        }

        torch::Tensor weights = torch::exp(path_log_probs);
        return {weights, accumulated_indices};
    }
};

// =========================================================================
// 3. Hypercubic Honeycomb Spatial Tiler ({4, 3^(D-2), 4} in Z^D)
// =========================================================================
class CppHypercubicHoneycombTiler {
public:
    int64_t d_model;
    int64_t dim_space;
    float cell_size;
    int64_t hash_table_size;
    torch::Tensor proj_spatial; // [dim_space, d_model]
    torch::Tensor hash_coeffs;  // [dim_space]

    CppHypercubicHoneycombTiler(int64_t d_model, int64_t dim_space = 8, float cell_size = 1.0f, int64_t hash_table_size = 65536, torch::Device device = torch::kCUDA)
        : d_model(d_model), dim_space(dim_space), cell_size(cell_size), hash_table_size(hash_table_size) {
        torch::NoGradGuard no_grad;
        torch::Tensor q = std::get<0>(at::linalg_qr(torch::randn({d_model, dim_space}, device)));
        proj_spatial = q.t();

        std::vector<int64_t> primes = {73856093, 19349663, 83492791, 2654435761, 50331653, 982451653, 4393139, 389};
        while (primes.size() < static_cast<size_t>(dim_space)) {
            primes.push_back(primes.back() + 10007);
        }
        auto opts = torch::TensorOptions().dtype(torch::kInt64).device(device);
        hash_coeffs = torch::from_blob(primes.data(), {dim_space}, torch::TensorOptions().dtype(torch::kInt64)).clone().to(device);
    }

    // Tiles continuous activation x into discrete cell coordinates and hash keys
    std::pair<torch::Tensor, torch::Tensor> forward(const torch::Tensor& x) {
        torch::Tensor coords_continuous = torch::matmul(x, proj_spatial.t()) / cell_size; // [N, dim_space]
        torch::Tensor cell_coords = torch::floor(coords_continuous).to(torch::kInt64);     // [N, dim_space]
        torch::Tensor cell_hashes = torch::remainder((cell_coords * hash_coeffs).sum(-1), hash_table_size);
        return {cell_coords, cell_hashes};
    }
};

} // namespace imf
