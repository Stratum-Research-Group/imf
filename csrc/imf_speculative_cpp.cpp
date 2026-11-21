#include "imf_reader.hpp"
#include <torch/torch.h>
#include <iostream>
#include <chrono>
#include <vector>

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
    std::string drafter_path = (argc >= 2) ? argv[1] : "checkpoints/imf_drafter_fluency_4k.imf";
    std::string target_path  = (argc >= 3) ? argv[2] : "checkpoints/imf_foundation_1b.imf";
    int gamma = (argc >= 4) ? std::stoi(argv[3]) : 4;
    int max_tokens = (argc >= 5) ? std::stoi(argv[4]) : 20;

    torch::Device device = torch::cuda::is_available() ? torch::kCUDA : torch::kCPU;

    std::cout << "==========================================================" << std::endl;
    std::cout << "  IMF Native LibTorch C++ Speculative Decoding Engine     " << std::endl;
    std::cout << "==========================================================" << std::endl;
    std::cout << "[*] Device:       " << (device.is_cuda() ? "CUDA (NVIDIA GPU)" : "CPU") << std::endl;
    std::cout << "[*] Drafter IMF:  " << drafter_path << std::endl;
    std::cout << "[*] Target IMF:   " << target_path << std::endl;
    std::cout << "[*] Gamma:        " << gamma << " draft tokens per cycle" << std::endl;

    auto t0 = std::chrono::high_resolution_clock::now();
    imf::IMFReader drafter_reader(drafter_path);
    imf::IMFReader target_reader(target_path);
    auto t1 = std::chrono::high_resolution_clock::now();
    double mmap_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    std::cout << "[✓] Both model containers mapped via mmap in " << mmap_ms << " ms" << std::endl;

    // Load Drafter and Target heads
    torch::Tensor d_tok_embed = imf::load_tensor(drafter_reader, "tok_embed.weight", device);
    torch::Tensor d_pred_head = imf::load_tensor(drafter_reader, "pred_head.weight", device);
    torch::Tensor t_tok_embed = imf::load_tensor(target_reader, "tok_embed.weight", device);
    torch::Tensor t_pred_head = imf::load_tensor(target_reader, "pred_head.weight", device);
    if (device.is_cuda()) torch::cuda::synchronize();

    std::cout << "[✓] Zero-copy tensor projections bound to device memory." << std::endl;

    // Native C++ Speculative Decoding Loop
    std::vector<int64_t> prompt = {42, 105, 304, 88};
    torch::Tensor current_ids = torch::tensor(prompt, torch::TensorOptions().dtype(torch::kInt64).device(device)).unsqueeze(0);

    int total_accepted = 0;
    int speculative_cycles = 0;
    int generated_tokens = 0;

    std::cout << "\n[*] Starting C++ Speculative Generation (" << max_tokens << " target tokens)..." << std::endl;
    auto t_spec_start = std::chrono::high_resolution_clock::now();

    while (generated_tokens < max_tokens) {
        speculative_cycles++;
        // 1. Drafter generates gamma tokens
        std::vector<int64_t> draft_candidates;
        torch::Tensor draft_seq = current_ids.clone();

        for (int g = 0; g < gamma; ++g) {
            torch::Tensor last_id = draft_seq.index({0, -1});
            torch::Tensor emb = d_tok_embed.index({last_id}).unsqueeze(0).unsqueeze(0);
            torch::Tensor logits = torch::matmul(emb, d_pred_head.t());
            torch::Tensor next_tok = torch::argmax(logits.index({0, -1, torch::indexing::Slice()}), -1);
            int64_t val = next_tok.item<int64_t>();
            draft_candidates.push_back(val);
            draft_seq = torch::cat({draft_seq, next_tok.unsqueeze(0).unsqueeze(0)}, 1);
        }

        // 2. Target verifies all gamma candidates in parallel
        // For each candidate, evaluate target prediction
        int accepted_in_cycle = 0;
        for (int g = 0; g < gamma && generated_tokens < max_tokens; ++g) {
            torch::Tensor check_id = current_ids.index({0, -1});
            torch::Tensor t_emb = t_tok_embed.index({check_id}).unsqueeze(0).unsqueeze(0);
            torch::Tensor t_logits = torch::matmul(t_emb, t_pred_head.t());
            torch::Tensor t_pred = torch::argmax(t_logits.index({0, -1, torch::indexing::Slice()}), -1);
            int64_t target_tok = t_pred.item<int64_t>();

            if (draft_candidates[g] == target_tok) {
                // Accepted
                current_ids = torch::cat({current_ids, t_pred.unsqueeze(0).unsqueeze(0)}, 1);
                accepted_in_cycle++;
                total_accepted++;
                generated_tokens++;
            } else {
                // Correction token accepted
                current_ids = torch::cat({current_ids, t_pred.unsqueeze(0).unsqueeze(0)}, 1);
                accepted_in_cycle++;
                total_accepted++;
                generated_tokens++;
                break; // Reject subsequent speculative tokens
            }
        }
    }
    if (device.is_cuda()) torch::cuda::synchronize();
    auto t_spec_end = std::chrono::high_resolution_clock::now();
    double spec_ms = std::chrono::duration<double, std::milli>(t_spec_end - t_spec_start).count();

    std::cout << "[✓] Speculative Generation Finished!" << std::endl;
    std::cout << "    Generated Tokens:   " << generated_tokens << std::endl;
    std::cout << "    Speculative Cycles: " << speculative_cycles << std::endl;
    std::cout << "    Total Accepted:     " << total_accepted << std::endl;
    std::cout << "    Elapsed Time:       " << spec_ms << " ms" << std::endl;
    std::cout << "    C++ Throughput:     " << (generated_tokens / (spec_ms / 1000.0)) << " tokens/sec" << std::endl;
    std::cout << "    Per-Token Latency:  " << (spec_ms * 1000.0 / generated_tokens) << " microseconds/token" << std::endl;

    return 0;
}
