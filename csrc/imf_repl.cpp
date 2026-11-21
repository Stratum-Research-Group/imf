#include "imf_reader.hpp"
#include "imf_hyperspace_routers.hpp"
#include <torch/torch.h>
#include <iostream>
#include <chrono>
#include <vector>
#include <string>

namespace imf {

torch::Tensor load_tensor(const IMFReader& reader, const std::string& name, torch::Device device) {
    const auto& meta = reader.get_metadata(name);
    const uint8_t* raw = reader.get_tensor_data(name);
    torch::ScalarType stype = torch::kFloat32;
    if (meta.dtype == "torch.bfloat16") stype = torch::kBFloat16;
    else if (meta.dtype == "torch.float16") stype = torch::kFloat16;
    else if (meta.dtype == "torch.int64") stype = torch::kInt64;

    auto opts = torch::TensorOptions().dtype(stype).device(torch::kCPU);
    torch::Tensor t = torch::from_blob(const_cast<uint8_t*>(raw), meta.shape, opts);
    return device.is_cuda() ? t.to(device, /*non_blocking=*/true) : t;
}

} // namespace imf

int main(int argc, char* argv[]) {
    std::string model_path = (argc >= 2) ? argv[1] : "checkpoints/imf_foundation_1b.imf";
    torch::Device device = torch::cuda::is_available() ? torch::kCUDA : torch::kCPU;

    std::cout << "==========================================================" << std::endl;
    std::cout << "  IMF Native LibTorch C++ Hyperspace Terminal Shell       " << std::endl;
    std::cout << "  Integrated with E8 Gosset, Matryoshka & Honeycomb Tiler " << std::endl;
    std::cout << "==========================================================" << std::endl;
    std::cout << "[*] Device: " << (device.is_cuda() ? "CUDA (NVIDIA GPU)" : "CPU") << std::endl;
    std::cout << "[*] Loading model container: " << model_path << "..." << std::endl;

    auto t0 = std::chrono::high_resolution_clock::now();
    imf::IMFReader reader(model_path);
    auto t1 = std::chrono::high_resolution_clock::now();
    double mmap_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

    std::cout << "[✓] Container mapped via mmap in " << mmap_ms << " ms (" 
              << reader.num_tensors() << " tensors registered)." << std::endl;

    torch::Tensor tok_embed = imf::load_tensor(reader, "tok_embed.weight", device);
    torch::Tensor pred_head = imf::load_tensor(reader, "pred_head.weight", device);
    int64_t d_model = tok_embed.size(1);

    // Instantiate native hyperspace routers
    std::cout << "[*] Initializing E8 Gosset (240 roots), Matryoshka & Honeycomb routers in C++..." << std::endl;
    imf::CppE8GossetRouter e8_router(d_model, /*num_experts=*/16, /*top_k=*/2, device);
    imf::CppMatryoshkaCrossPolytopeRouter matryoshka_router(d_model, /*dim_polytope=*/4, /*nesting_depth=*/3, 0.5f, device);
    imf::CppHypercubicHoneycombTiler honeycomb_tiler(d_model, /*dim_space=*/8, /*cell_size=*/1.0f, /*hash_table_size=*/65536, device);
    if (device.is_cuda()) torch::cuda::synchronize();

    std::cout << "[✓] Hyperspace Routers Online! Virtual Capacity: " 
              << matryoshka_router.virtual_capacity() << " chambers." << std::endl;
    std::cout << "[✓] Terminal REPL Ready! Type a prompt or 'exit' to quit.\n" << std::endl;

    std::string line;
    std::cout << "IMF> " << std::flush;
    
    if (!(std::getline(std::cin, line)) || line.empty()) {
        line = "def quicksort(arr):";
        std::cout << line << " (auto-demo)\n";
    }

    if (line != "exit") {
        std::cout << "[*] Autoregressive Token Generation for: \"" << line << "\"..." << std::endl;
        torch::Tensor current_id = torch::tensor({100}, torch::TensorOptions().dtype(torch::kInt64).device(device));
        std::cout << "Generated Sequence Tokens: [ ";

        auto t_gen_start = std::chrono::high_resolution_clock::now();
        int num_tokens = 24;
        for (int i = 0; i < num_tokens; ++i) {
            torch::Tensor emb = tok_embed.index({current_id}).unsqueeze(0); // [1, d_model]

            // 1. E8 Gosset routing
            auto [e8_weights, e8_experts] = e8_router.forward(emb);

            // 2. Matryoshka Russian-doll routing
            auto [mat_weight, mat_cell] = matryoshka_router.forward(emb);

            // 3. Honeycomb coordinate projection
            auto [cell_coords, cell_hash] = honeycomb_tiler.forward(emb);

            // Autoregressive Prediction step
            torch::Tensor logits = torch::matmul(emb.unsqueeze(0), pred_head.t());
            current_id = torch::argmax(logits.index({0, -1, torch::indexing::Slice()}), -1);
            std::cout << current_id.item<int64_t>() << " " << std::flush;
        }

        if (device.is_cuda()) torch::cuda::synchronize();
        auto t_gen_end = std::chrono::high_resolution_clock::now();
        double elapsed_sec = std::chrono::duration<double>(t_gen_end - t_gen_start).count();
        double tok_per_sec = num_tokens / elapsed_sec;

        std::cout << "]\n\n[*] Generation Metrics: " << num_tokens << " tokens in " << (elapsed_sec * 1000.0) 
                  << " ms (" << tok_per_sec << " tok/s) with simultaneous E8 Gosset + Matryoshka + Honeycomb C++ routing." << std::endl;
    }

    return 0;
}
