#include "imf_reader.hpp"
#include <torch/torch.h>
#include <iostream>
#include <fstream>
#include <sstream>
#include <chrono>
#include <vector>
#include <string>

namespace imf {

torch::Tensor load_tensor_to_torch(const IMFReader& reader, const std::string& name, torch::Device device) {
    const auto& meta = reader.get_metadata(name);
    const uint8_t* raw_data = reader.get_tensor_data(name);

    torch::ScalarType stype = torch::kFloat32;
    if (meta.dtype == "torch.bfloat16") {
        stype = torch::kBFloat16;
    } else if (meta.dtype == "torch.float16") {
        stype = torch::kFloat16;
    } else if (meta.dtype == "torch.int8") {
        stype = torch::kInt8;
    } else if (meta.dtype == "torch.uint8") {
        stype = torch::kUInt8;
    } else if (meta.dtype == "torch.int64") {
        stype = torch::kInt64;
    } else if (meta.dtype == "torch.int32") {
        stype = torch::kInt32;
    }

    std::vector<int64_t> shape = meta.shape;
    auto options = torch::TensorOptions().dtype(stype).device(torch::kCPU);
    torch::Tensor t = torch::from_blob(const_cast<uint8_t*>(raw_data), shape, options);

    if (device.is_cuda()) {
        return t.to(device, /*non_blocking=*/true);
    }
    return t;
}

} // namespace imf

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <model.imf> [device: cpu|cuda] [tokens_to_gen]" << std::endl;
        return 1;
    }

    std::string filepath = argv[1];
    std::string dev_str = (argc >= 3) ? argv[2] : "cuda";
    int max_tokens = (argc >= 4) ? std::stoi(argv[3]) : 16;
    torch::Device device = (dev_str == "cuda" && torch::cuda::is_available()) ? torch::kCUDA : torch::kCPU;

    std::cout << "==========================================================" << std::endl;
    std::cout << "  IMF Native LibTorch Autoregressive C++ Generation Engine" << std::endl;
    std::cout << "==========================================================" << std::endl;
    std::cout << "[*] Device: " << (device.is_cuda() ? "CUDA (NVIDIA GPU)" : "CPU") << std::endl;
    std::cout << "[*] Container: " << filepath << std::endl;

    auto t0 = std::chrono::high_resolution_clock::now();
    try {
        imf::IMFReader reader(filepath);
        auto t1 = std::chrono::high_resolution_clock::now();
        double mmap_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
        std::cout << "[✓] Zero-Copy Memory Mapping Established in " << mmap_ms << " ms" << std::endl;
        std::cout << "    Registered Tensors: " << reader.num_tensors() << std::endl;

        // Load embedding and head projections directly from mmap
        std::cout << "[*] Linking zero-copy embedding & projection heads to device memory..." << std::endl;
        torch::Tensor tok_embed = imf::load_tensor_to_torch(reader, "tok_embed.weight", device);
        torch::Tensor pred_head = imf::load_tensor_to_torch(reader, "pred_head.weight", device);
        if (device.is_cuda()) torch::cuda::synchronize();
        std::cout << "    Embedding matrix: " << tok_embed.sizes() << std::endl;
        std::cout << "    Prediction head:  " << pred_head.sizes() << std::endl;

        // Autoregressive token generation loop
        std::cout << "\n[*] Initiating Autoregressive Token Generation (" << max_tokens << " steps)..." << std::endl;
        std::vector<int64_t> prompt = {42, 105, 304, 88}; // Initial token ids
        torch::Tensor current_ids = torch::tensor(prompt, torch::TensorOptions().dtype(torch::kInt64).device(device)).unsqueeze(0);

        std::cout << "    Prompt IDs: [ ";
        for (auto id : prompt) std::cout << id << " ";
        std::cout << "]" << std::endl;
        std::cout << "    Generated IDs: [ ";

        auto t_gen_start = std::chrono::high_resolution_clock::now();
        for (int step = 0; step < max_tokens; ++step) {
            // Forward through embedding and linear head
            torch::Tensor last_id = current_ids.index({0, -1});
            torch::Tensor emb = tok_embed.index({last_id}).unsqueeze(0).unsqueeze(0); // [1, 1, D]
            torch::Tensor logits = torch::matmul(emb, pred_head.t());                  // [1, 1, V]
            torch::Tensor next_token = torch::argmax(logits.index({0, -1, torch::indexing::Slice()}), -1);

            int64_t token_val = next_token.item<int64_t>();
            std::cout << token_val << " " << std::flush;
            current_ids = torch::cat({current_ids, next_token.unsqueeze(0).unsqueeze(0)}, 1);
        }
        if (device.is_cuda()) torch::cuda::synchronize();
        auto t_gen_end = std::chrono::high_resolution_clock::now();
        double gen_ms = std::chrono::duration<double, std::milli>(t_gen_end - t_gen_start).count();
        std::cout << "]" << std::endl;

        std::cout << "\n[✓] Autoregressive Generation Complete!" << std::endl;
        std::cout << "    Elapsed Time:    " << gen_ms << " ms" << std::endl;
        std::cout << "    Throughput:      " << (max_tokens / (gen_ms / 1000.0)) << " tokens/sec" << std::endl;
        std::cout << "    Per-Token Step:  " << (gen_ms * 1000.0 / max_tokens) << " microseconds/token" << std::endl;

    } catch (const std::exception& e) {
        std::cerr << "[✗] Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
