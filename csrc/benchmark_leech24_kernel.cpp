// csrc/benchmark_leech24_kernel.cpp
// Benchmarks the 24D Leech Lattice (Lambda_24) C++ Sub-Bit Kernel against Dense FP16 GEMM

#include <iostream>
#include <chrono>
#include <vector>
#include <torch/torch.h>
#include "imf_leech24_kernel.hpp"

int main() {
    std::cout << "===================================================================\n";
    std::cout << "  IMF 24D Leech Lattice (Lambda_24) C++ Sub-Bit Kernel Benchmark   \n";
    std::cout << "===================================================================\n";

    torch::Device device = torch::cuda::is_available() ? torch::kCUDA : torch::kCPU;
    std::cout << "[*] Execution Device: " << (device.is_cuda() ? "CUDA (NVIDIA GPU)" : "CPU") << "\n";

    int64_t B = 4;
    int64_t seq_len = 64;
    int64_t d_in = 8160;  // divisible by 24 (8160 / 24 = 340 vectors) and 48
    int64_t d_out = 8160;
    int64_t scale_block_size = 48;

    std::cout << "[*] Layer Shape: [" << d_out << ", " << d_in << "] (~66.58M params)\n";

    // Create synthetic Leech root codebook slice [1000, 24] for micro-benchmark
    // (Full 196,560 roots use identical memory lookup path)
    int64_t num_test_roots = 1000;
    torch::Tensor codebook = torch::randn({num_test_roots, 24}, torch::TensorOptions().device(device).dtype(torch::kFloat32));
    codebook = codebook / torch::norm(codebook, 2, -1, true) * 2.828427f;

    // Packed 18-bit indices stored as int32
    torch::Tensor indices = torch::randint(0, num_test_roots, {d_out, d_in / 24}, torch::TensorOptions().device(device).dtype(torch::kInt32));
    // Scales: 48 weights per scale
    torch::Tensor scales = torch::rand({d_out, d_in / scale_block_size}, torch::TensorOptions().device(device).dtype(torch::kFloat16)) + 0.1f;
    
    // Input activation
    torch::Tensor x = torch::randn({B, seq_len, d_in}, torch::TensorOptions().device(device).dtype(torch::kFloat16));

    // Warmup
    for (int i = 0; i < 5; ++i) {
        auto out = imf::LeechLatticeKernel::forward(x, indices, scales, codebook, c10::nullopt, scale_block_size);
        if (device.is_cuda()) torch::cuda::synchronize();
    }

    // Benchmark Leech Lattice Sub-Bit Kernel
    int num_runs = 50;
    auto start = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < num_runs; ++i) {
        auto out = imf::LeechLatticeKernel::forward(x, indices, scales, codebook, c10::nullopt, scale_block_size);
        if (device.is_cuda()) torch::cuda::synchronize();
    }
    auto end = std::chrono::high_resolution_clock::now();
    double leech_us = std::chrono::duration_cast<std::chrono::microseconds>(end - start).count() / (double)num_runs;

    // Benchmark Dense FP16 GEMM baseline
    torch::Tensor W_dense = torch::randn({d_out, d_in}, torch::TensorOptions().device(device).dtype(torch::kFloat16));
    torch::Tensor x_flat = x.reshape({-1, d_in});
    for (int i = 0; i < 5; ++i) {
        auto out_dense = torch::matmul(x_flat, W_dense.t());
        if (device.is_cuda()) torch::cuda::synchronize();
    }
    start = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < num_runs; ++i) {
        auto out_dense = torch::matmul(x_flat, W_dense.t());
        if (device.is_cuda()) torch::cuda::synchronize();
    }
    end = std::chrono::high_resolution_clock::now();
    double dense_us = std::chrono::duration_cast<std::chrono::microseconds>(end - start).count() / (double)num_runs;

    int64_t weight_bytes_fp16 = d_out * d_in * 2;
    // Leech: 18 bits / 24 weights = 0.75 bytes / weight (packed into 32-bit words) + scale (2 bytes / 48 weights)
    int64_t weight_bytes_leech = indices.numel() * 4 + scales.numel() * 2;

    std::cout << "\n--- Benchmark Results ---\n";
    std::cout << "  [Dense FP16 Baseline] Latency: " << dense_us << " us | Memory: " << (weight_bytes_fp16 / (1024.0 * 1024.0)) << " MB\n";
    std::cout << "  [Leech 24D Sub-Bit  ] Latency: " << leech_us << " us | Memory: " << (weight_bytes_leech / (1024.0 * 1024.0)) << " MB\n";
    std::cout << "  Compression Ratio:   " << (weight_bytes_fp16 / (double)weight_bytes_leech) << "x\n";
    std::cout << "  Speedup / Parity:    " << (dense_us / leech_us) << "x\n";
    std::cout << "===================================================================\n";

    return 0;
}
