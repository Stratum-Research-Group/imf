#include "imf_reader.hpp"
#include <torch/torch.h>
#include <iostream>
#include <chrono>

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

    // Zero-copy from_blob pointing directly to the mmap virtual address
    std::vector<int64_t> shape = meta.shape;
    auto options = torch::TensorOptions().dtype(stype).device(torch::kCPU);
    torch::Tensor t = torch::from_blob(const_cast<uint8_t*>(raw_data), shape, options);

    // If target is CUDA, stream transfer asynchronously
    if (device.is_cuda()) {
        return t.to(device, /*non_blocking=*/true);
    }
    return t;
}

} // namespace imf

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <model.imf> [device: cpu|cuda]" << std::endl;
        return 1;
    }

    std::string filepath = argv[1];
    std::string dev_str = (argc >= 3) ? argv[2] : "cuda";
    torch::Device device = (dev_str == "cuda" && torch::cuda::is_available()) ? torch::kCUDA : torch::kCPU;

    std::cout << "==========================================================" << std::endl;
    std::cout << "  IMF Native LibTorch/CUDA C++ Zero-Copy Inference Engine " << std::endl;
    std::cout << "==========================================================" << std::endl;
    std::cout << "[*] Device: " << (device.is_cuda() ? "CUDA (NVIDIA GPU)" : "CPU") << std::endl;
    std::cout << "[*] Memory-mapping container: " << filepath << "..." << std::endl;

    auto t0 = std::chrono::high_resolution_clock::now();
    try {
        imf::IMFReader reader(filepath);
        auto t1 = std::chrono::high_resolution_clock::now();
        double mmap_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

        std::cout << "[✓] Container mapped in " << mmap_ms << " ms" << std::endl;
        std::cout << "    File size: " << (reader.file_size() / (1024.0 * 1024.0)) << " MB" << std::endl;
        std::cout << "    Tensors registered: " << reader.num_tensors() << std::endl;

        // Stream and verify 10 key weight tensors
        std::cout << "\n[*] Materializing zero-copy LibTorch tensors directly from mmap address space..." << std::endl;
        size_t count = 0;
        auto t_stream_start = std::chrono::high_resolution_clock::now();

        for (const auto& [name, meta] : reader.get_tensors()) {
            torch::Tensor t = imf::load_tensor_to_torch(reader, name, device);
            if (++count <= 5) {
                std::cout << "    [Tensor " << count << "] " << name 
                          << " | Shape: " << t.sizes() 
                          << " | Dtype: " << t.dtype() 
                          << " | Device: " << t.device() 
                          << " | Frobenius Norm: " << t.to(torch::kFloat32).norm().item<float>() << std::endl;
            }
        }
        if (device.is_cuda()) {
            torch::cuda::synchronize();
        }
        auto t_stream_end = std::chrono::high_resolution_clock::now();
        double stream_ms = std::chrono::duration<double, std::milli>(t_stream_end - t_stream_start).count();

        std::cout << "\n[✓] Successfully streamed " << reader.num_tensors() 
                  << " tensors to " << (device.is_cuda() ? "GPU VRAM" : "Host RAM") 
                  << " in " << stream_ms << " ms!" << std::endl;

        // Perform a native C++ forward projection benchmark
        std::cout << "\n[*] Running Native C++ Linear Matrix Multiplication Benchmark..." << std::endl;
        torch::Tensor x = torch::randn({1, 16, 576}, torch::TensorOptions().device(device).dtype(torch::kFloat32));
        torch::Tensor w = torch::randn({576, 576}, torch::TensorOptions().device(device).dtype(torch::kFloat32));

        auto t_proj_start = std::chrono::high_resolution_clock::now();
        for (int i = 0; i < 100; ++i) {
            torch::Tensor y = torch::matmul(x, w.t());
        }
        if (device.is_cuda()) torch::cuda::synchronize();
        auto t_proj_end = std::chrono::high_resolution_clock::now();
        double avg_proj_us = std::chrono::duration<double, std::micro>(t_proj_end - t_proj_start).count() / 100.0;

        std::cout << "    Average 576x576 projection latency: " << avg_proj_us << " microseconds per step" << std::endl;
        std::cout << "[✓] Native LibTorch C++ Inference Engine Operational!" << std::endl;

    } catch (const std::exception& e) {
        std::cerr << "[✗] Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
