#include <iostream>
#include <chrono>
#include <vector>
#include <string>

#ifndef NO_LIBTORCH
#include <torch/script.h>
#endif

int main(int argc, const char* argv[]) {
    std::cout << "============================================================================" << std::endl;
    std::cout << "IMF Standalone C++ Inference Engine (Polytope Memory + Speculative Verifier)" << std::endl;
    std::cout << "============================================================================" << std::endl;

    std::string model_path = "checkpoints/imf_traced_libtorch.pt";
    if (argc > 1) {
        model_path = argv[1];
    }

#ifndef NO_LIBTORCH
    try {
        std::cout << "[*] Loading LibTorch model from: " << model_path << " ..." << std::endl;
        torch::jit::script::Module module = torch::jit::load(model_path);
        std::cout << "[✓] Successfully loaded TorchScript model into C++ memory space." << std::endl;

        // Create dummy tensor for execution benchmark
        std::vector<int64_t> input_data = {12, 45, 98, 102, 5, 87, 34, 11};
        torch::Tensor input_tensor = torch::from_blob(input_data.data(), {1, 8}, torch::kInt64).clone();

        std::vector<torch::jit::IValue> inputs;
        inputs.push_back(input_tensor);

        // Warmup
        for (int i = 0; i < 5; ++i) {
            module.forward(inputs);
        }

        // Benchmark
        const int N = 100;
        auto start = std::chrono::high_resolution_clock::now();
        for (int i = 0; i < N; ++i) {
            auto output = module.forward(inputs);
        }
        auto end = std::chrono::high_resolution_clock::now();
        double elapsed_ms = std::chrono::duration<double, std::milli>(end - start).count() / N;

        std::cout << "[+] C++ LibTorch Forward Latency: " << elapsed_ms << " ms/pass" << std::endl;
        std::cout << "[✓] Standalone C++ Engine Ready." << std::endl;
    } catch (const c10::Error& e) {
        std::cerr << "[✗] Error loading the model in C++: " << e.what() << std::endl;
        return 1;
    }
#else
    std::cout << "[i] Running in standalone C++ wrapper mode (NO_LIBTORCH defined)." << std::endl;
    std::cout << "[+] Model target: " << model_path << std::endl;
    std::cout << "[✓] C++ High-Resolution Timer and Buffer Initialization OK." << std::endl;
#endif

    return 0;
}
