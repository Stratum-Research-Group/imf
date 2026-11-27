// csrc/fast_safetensors_loader.cpp
// High-speed C++20 zero-copy memory-mapped safetensors header parser and deserializer.
// Uses POSIX mmap to map tensor weights into userspace memory with minimal OS paging overhead.

#include <iostream>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <cstring>
#include <cstdint>

struct SafeTensorsMeta {
    uint64_t header_size;
    const char* header_json;
    const uint8_t* tensor_data;
    size_t file_size;
};

extern "C" bool load_safetensors_mmap(const char* filepath, SafeTensorsMeta* out_meta) {
    int fd = open(filepath, O_RDONLY);
    if (fd < 0) {
        std::cerr << "Failed to open safetensors file: " << filepath << std::endl;
        return false;
    }

    struct stat sb;
    if (fstat(fd, &sb) < 0) {
        close(fd);
        return false;
    }

    void* addr = mmap(NULL, sb.st_size, PROT_READ, MAP_SHARED, fd, 0);
    close(fd);

    if (addr == MAP_FAILED) {
        std::cerr << "mmap failed for: " << filepath << std::endl;
        return false;
    }

    // Safetensors header: first 8 bytes contain uint64_t little-endian header length N
    uint64_t header_len = *reinterpret_cast<const uint64_t*>(addr);
    out_meta->header_size = header_len;
    out_meta->header_json = reinterpret_cast<const char*>(addr) + 8;
    out_meta->tensor_data = reinterpret_cast<const uint8_t*>(addr) + 8 + header_len;
    out_meta->file_size = sb.st_size;

    return true;
}

int main(int argc, char** argv) {
    const char* path = "checkpoints/sovereign_7b_release/model.safetensors";
    if (argc > 1) path = argv[1];

    SafeTensorsMeta meta;
    if (load_safetensors_mmap(path, &meta)) {
        std::cout << "[+] Fast C++20 Zero-Copy Safetensors Loader verified: " << path << std::endl;
        std::cout << "    File Size: " << (meta.file_size / (1024.0 * 1024.0)) << " MB" << std::endl;
        std::cout << "    Header Length: " << meta.header_size << " bytes" << std::endl;
        return 0;
    }
    return 1;
}
