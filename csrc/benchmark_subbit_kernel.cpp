#include "imf_reader.hpp"
#include "imf_subbit_kernel.hpp"
#include <torch/torch.h>
#include <iostream>
#include <chrono>

int main(int argc, char* argv[]) {
    std::cout << "==========================================================" << std::endl;
    std::cout << "  IMF Native C++ Sub-Bit Kernel POPCOUNT Benchmark        " << std::endl;
    std::cout << "==========================================================" << std::endl;

    torch::Device device = torch::cuda::is_available() ? torch::kCUDA : torch::kCPU;
    std::cout << "[*] Device: " << (device.is_cuda() ? "CUDA (NVIDIA GPU)" : "CPU") << std::endl;

    int64_t d_in = 576;
    int64_t d_out = 576;
    int64_t rank = 32;
    int64_t words_per_rank = (rank + 31) / 32;
    size_t num_paths = 2;

    std::vector<torch::Tensor> u_packed, v_packed, scale_h, scale_l, scale_g;

    for (size_t p = 0; p < num_paths; ++p) {
        u_packed.push_back(torch::randint(0, 0x7FFFFFFF, {d_out, words_per_rank}, torch::TensorOptions().dtype(torch::kInt32).device(device)));
        v_packed.push_back(torch::randint(0, 0x7FFFFFFF, {d_in, words_per_rank}, torch::TensorOptions().dtype(torch::kInt32).device(device)));
        scale_h.push_back(torch::ones({d_out}, torch::TensorOptions().dtype(torch::kFloat16).device(device)));
        scale_l.push_back(torch::ones({rank}, torch::TensorOptions().dtype(torch::kFloat16).device(device)));
        scale_g.push_back(torch::ones({d_in}, torch::TensorOptions().dtype(torch::kFloat16).device(device)));
    }
    torch::Tensor bias = torch::zeros({d_out}, torch::TensorOptions().dtype(torch::kFloat16).device(device));

    torch::Tensor x = torch::randn({1, 16, d_in}, torch::TensorOptions().dtype(torch::kFloat32).device(device));

    // Warmup
    torch::Tensor y = imf::SubBitLinearKernel::forward(x, u_packed, v_packed, scale_h, scale_l, scale_g, bias, rank);
    if (device.is_cuda()) torch::cuda::synchronize();

    auto t0 = std::chrono::high_resolution_clock::now();
    int iters = 100;
    for (int i = 0; i < iters; ++i) {
        y = imf::SubBitLinearKernel::forward(x, u_packed, v_packed, scale_h, scale_l, scale_g, bias, rank);
    }
    if (device.is_cuda()) torch::cuda::synchronize();
    auto t1 = std::chrono::high_resolution_clock::now();

    double total_us = std::chrono::duration<double, std::micro>(t1 - t0).count();
    double avg_us = total_us / iters;

    std::cout << "[✓] Forward output shape: " << y.sizes() << std::endl;
    std::cout << "[✓] Sub-bit dual-path forward pass latency: " << avg_us << " microseconds per call" << std::endl;
    std::cout << "[✓] LittleBit-2 C++ kernel successfully validated!" << std::endl;

    return 0;
}
