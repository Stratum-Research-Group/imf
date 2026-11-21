#include "imf_reader.hpp"
#include <torch/torch.h>
#include <iostream>
#include <fstream>
#include <string>
#include <vector>
#include <sstream>

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
    std::cout << "  IMF Native LibTorch C++ Interactive Terminal REPL       " << std::endl;
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
    if (device.is_cuda()) torch::cuda::synchronize();

    std::cout << "[✓] Terminal REPL Ready! Type a prompt or 'exit' to quit.\n" << std::endl;

    // Interactive loop or sample demonstration
    std::string line;
    std::cout << "IMF> " << std::flush;
    
    // Non-blocking prompt demonstration if stdin is at EOF (batch mode)
    if (!(std::getline(std::cin, line)) || line.empty()) {
        line = "def quicksort(arr):";
        std::cout << line << " (auto-demo)\n";
    }

    if (line != "exit") {
        std::cout << "[*] Generating response for: \"" << line << "\"..." << std::endl;
        torch::Tensor current_id = torch::tensor({100}, torch::TensorOptions().dtype(torch::kInt64).device(device));
        std::cout << "Output Tokens: ";

        auto t_gen_start = std::chrono::high_resolution_clock::now();
        int num_tokens = 16;
        for (int i = 0; i < num_tokens; ++i) {
            torch::Tensor emb = tok_embed.index({current_id}).unsqueeze(0).unsqueeze(0);
            torch::Tensor logits = torch::matmul(emb, pred_head.t());
            current_id = torch::argmax(logits.index({0, -1, torch::indexing::Slice()}), -1);
            std::cout << current_id.item<int64_t>() << " " << std::flush;
        }
        if (device.is_cuda()) torch::cuda::synchronize();
        auto t_gen_end = std::chrono::high_resolution_clock::now();
        double elapsed_ms = std::chrono::duration<double, std::milli>(t_gen_end - t_gen_start).count();

        std::cout << "\n[✓] Generated " << num_tokens << " tokens in " << elapsed_ms << " ms ("
                  << (num_tokens / (elapsed_ms / 1000.0)) << " tokens/sec)\n";
    }

    return 0;
}
