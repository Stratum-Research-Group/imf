#include "imf_reader.hpp"
#include <iostream>
#include <chrono>

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <model.imf>" << std::endl;
        return 1;
    }

    std::string filepath = argv[1];
    std::cout << "[*] IMF C++ Zero-Copy Engine opening: " << filepath << "..." << std::endl;

    auto t0 = std::chrono::high_resolution_clock::now();
    try {
        imf::IMFReader reader(filepath);
        auto t1 = std::chrono::high_resolution_clock::now();
        double elapsed_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

        std::cout << "[✓] File mapped successfully!" << std::endl;
        std::cout << "    File Size:      " << (reader.file_size() / (1024.0 * 1024.0)) << " MB" << std::endl;
        std::cout << "    Tensors Mapped: " << reader.num_tensors() << std::endl;
        std::cout << "    Cold-Start Mmap Time: " << elapsed_ms << " ms" << std::endl;

        // Verify sample tensor pointer access
        size_t sample_count = 0;
        for (const auto& [name, meta] : reader.get_tensors()) {
            const uint8_t* data = reader.get_tensor_data(name);
            if (data == nullptr) {
                std::cerr << "Error: Null pointer for tensor " << name << std::endl;
                return 1;
            }
            if (++sample_count <= 5) {
                std::cout << "    [Tensor " << sample_count << "] " << name << " | Dtype: " << meta.dtype
                          << " | Length: " << meta.length << " bytes | Memory Addr: " << (void*)data << std::endl;
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "[✗] Error: " << e.what() << std::endl;
        return 1;
    }

    return 0;
}
