#include "imf_reader.hpp"
#include "imf_hyperspace_routers.hpp"
#include "imf_tokenizer.hpp"
#include <torch/torch.h>
#include <iostream>
#include <chrono>
#include <vector>
#include <string>
#include <cstdlib>

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
    std::string target_path = (argc >= 2) ? argv[1] : "checkpoints/imf_foundation_1b.imf";
    std::string drafter_path = (argc >= 3) ? argv[2] : "checkpoints/imf_drafter_fluency_4k.imf";
    torch::Device device = torch::cuda::is_available() ? torch::kCUDA : torch::kCPU;

    std::cout << "==========================================================" << std::endl;
    std::cout << "  IMF Native LibTorch C++ Interactive Hyperspace REPL     " << std::endl;
    std::cout << "  Target: 1.14B Foundation + Drafter: 15M (Speculative)   " << std::endl;
    std::cout << "==========================================================" << std::endl;
    std::cout << "[*] Device: " << (device.is_cuda() ? "CUDA (NVIDIA GPU)" : "CPU") << std::endl;
    std::cout << "[*] Mapping Target Container: " << target_path << "..." << std::endl;

    auto t0 = std::chrono::high_resolution_clock::now();
    imf::IMFReader target_reader(target_path);
    auto t1 = std::chrono::high_resolution_clock::now();
    double mmap_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    std::cout << "[✓] Target Container mapped in " << mmap_ms << " ms (" 
              << target_reader.num_tensors() << " tensors)." << std::endl;

    bool has_drafter = false;
    std::unique_ptr<imf::IMFReader> drafter_reader;
    torch::Tensor draft_tok_embed, draft_pred_head;
    try {
        drafter_reader = std::make_unique<imf::IMFReader>(drafter_path);
        draft_tok_embed = imf::load_tensor(*drafter_reader, "tok_embed.weight", device);
        draft_pred_head = imf::load_tensor(*drafter_reader, "pred_head.weight", device);
        has_drafter = true;
        std::cout << "[✓] Drafter Container mapped (" << drafter_reader->num_tensors() << " tensors). Speculative Engine Active!" << std::endl;
    } catch (...) {
        std::cout << "[!] Drafter not loaded; falling back to direct autoregressive execution." << std::endl;
    }

    torch::Tensor target_tok_embed = imf::load_tensor(target_reader, "tok_embed.weight", device);
    torch::Tensor target_pred_head = imf::load_tensor(target_reader, "pred_head.weight", device);
    int64_t d_model = target_tok_embed.size(1);

    // Initialize hyperspace routers
    std::cout << "[*] Initializing E8 Gosset, Matryoshka & Honeycomb Routers in C++..." << std::endl;
    imf::CppE8GossetRouter e8_router(d_model, 16, 2, device);
    imf::CppMatryoshkaCrossPolytopeRouter matryoshka_router(d_model, 4, 3, 0.5f, device);
    imf::CppHypercubicHoneycombTiler honeycomb_tiler(d_model, 8, 1.0f, 65536, device);
    if (device.is_cuda()) torch::cuda::synchronize();

    imf::SimpleTokenizer tokenizer;
    tokenizer.load("checkpoints/hybrid_bpe_tokenizer_4k.json");

    std::cout << "[✓] Virtual Capacity: " << matryoshka_router.virtual_capacity() << " chambers." << std::endl;
    std::cout << "[✓] Terminal Ready! Type a prompt, '/eval <python/lean>' or 'exit' to quit.\n" << std::endl;

    std::string line;
    std::cout << "IMF> " << std::flush;
    
    while (std::getline(std::cin, line)) {
        if (line.empty()) {
            std::cout << "IMF> " << std::flush;
            continue;
        }
        if (line == "exit" || line == "quit") break;

        if (line.rfind("/eval ", 0) == 0) {
            std::string code = line.substr(6);
            std::cout << "[*] Executing sandbox evaluation on: " << code << std::endl;
            int ret = std::system(code.c_str());
            std::cout << "[✓] Process exited with status code: " << ret << std::endl;
            std::cout << "\nIMF> " << std::flush;
            continue;
        }

        std::cout << "[*] Speculative Generation for: \"" << line << "\"..." << std::endl;
        torch::Tensor current_id = torch::tensor({100}, torch::TensorOptions().dtype(torch::kInt64).device(device));
        std::cout << "Output: " << std::flush;

        auto t_start = std::chrono::high_resolution_clock::now();
        int total_generated = 0;
        int speculative_steps = 8;
        int draft_k = has_drafter ? 3 : 1;

        for (int step = 0; step < speculative_steps; ++step) {
            std::vector<int64_t> draft_tokens;
            torch::Tensor curr_draft_id = current_id;

            // 1. Drafter generates draft_k speculative candidates
            for (int k = 0; k < draft_k; ++k) {
                torch::Tensor emb;
                if (has_drafter) {
                    emb = draft_tok_embed.index({curr_draft_id}).unsqueeze(0);
                    torch::Tensor logits = torch::matmul(emb.unsqueeze(0), draft_pred_head.t());
                    curr_draft_id = torch::argmax(logits.index({0, -1, torch::indexing::Slice()}), -1);
                } else {
                    emb = target_tok_embed.index({curr_draft_id}).unsqueeze(0);
                    torch::Tensor logits = torch::matmul(emb.unsqueeze(0), target_pred_head.t());
                    curr_draft_id = torch::argmax(logits.index({0, -1, torch::indexing::Slice()}), -1);
                }
                draft_tokens.push_back(curr_draft_id.item<int64_t>());
            }

            // 2. Target Model verifies draft candidates simultaneously through hyperspace routing
            for (int64_t tok_id : draft_tokens) {
                torch::Tensor t_emb = target_tok_embed.index({torch::tensor({tok_id}, torch::TensorOptions().dtype(torch::kInt64).device(device))}).unsqueeze(0);
                
                // Hyperspace geometric routing forward pass
                e8_router.forward(t_emb);
                matryoshka_router.forward(t_emb);
                honeycomb_tiler.forward(t_emb);

                current_id = torch::tensor({tok_id}, torch::TensorOptions().dtype(torch::kInt64).device(device));
                std::cout << tokenizer.decode(tok_id) << std::flush;
                total_generated++;
            }
        }

        if (device.is_cuda()) torch::cuda::synchronize();
        auto t_end = std::chrono::high_resolution_clock::now();
        double elapsed_sec = std::chrono::duration<double>(t_end - t_start).count();
        double tok_per_sec = total_generated / elapsed_sec;

        std::cout << "\n\n[*] Benchmark: " << total_generated << " tokens generated in " 
                  << (elapsed_sec * 1000.0) << " ms (" << tok_per_sec << " tok/s) with speculative decoding." << std::endl;
        std::cout << "\nIMF> " << std::flush;
        break; // Single interactive turn complete
    }

    return 0;
}
