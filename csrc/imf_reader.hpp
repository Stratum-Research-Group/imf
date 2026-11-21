#pragma once

#include <cstdint>
#include <string>
#include <vector>
#include <unordered_map>
#include <memory>
#include <stdexcept>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstring>
#include <iostream>

namespace imf {

constexpr uint32_t IMF_MAGIC = 0x494D4601; // "IMF\x01"
constexpr uint32_t IMF_VERSION = 1;

#pragma pack(push, 1)
struct IMFHeader {
    uint32_t magic;
    uint32_t version;
    uint64_t index_offset;
    uint64_t index_length;
    uint64_t data_offset;
    uint64_t data_length;
    uint32_t index_crc32;
    uint8_t  reserved[20];
};
#pragma pack(pop)
static_assert(sizeof(IMFHeader) == 64, "IMFHeader must be exactly 64 bytes");

struct TensorMetadata {
    std::string name;
    std::vector<int64_t> shape;
    std::string dtype;
    uint32_t encoding;
    uint64_t offset;
    uint64_t length;
    uint32_t checksum;
};

class IMFReader {
public:
    explicit IMFReader(const std::string& filepath) : filepath_(filepath) {
        fd_ = open(filepath.c_str(), O_RDONLY);
        if (fd_ < 0) {
            throw std::runtime_error("Failed to open IMF file: " + filepath);
        }

        struct stat sb;
        if (fstat(fd_, &sb) < 0) {
            close(fd_);
            throw std::runtime_error("Failed to stat IMF file: " + filepath);
        }
        file_size_ = sb.st_size;

        if (file_size_ < sizeof(IMFHeader)) {
            close(fd_);
            throw std::runtime_error("File smaller than 64-byte IMF header");
        }

        mmap_ptr_ = static_cast<uint8_t*>(mmap(nullptr, file_size_, PROT_READ, MAP_SHARED, fd_, 0));
        if (mmap_ptr_ == MAP_FAILED) {
            close(fd_);
            throw std::runtime_error("Failed to mmap IMF file");
        }

        parse_header();
        parse_index();
    }

    ~IMFReader() {
        if (mmap_ptr_ && mmap_ptr_ != MAP_FAILED) {
            munmap(mmap_ptr_, file_size_);
        }
        if (fd_ >= 0) {
            close(fd_);
        }
    }

    IMFReader(const IMFReader&) = delete;
    IMFReader& operator=(const IMFReader&) = delete;

    const std::unordered_map<std::string, TensorMetadata>& get_tensors() const {
        return tensors_;
    }

    bool has_tensor(const std::string& name) const {
        return tensors_.find(name) != tensors_.end();
    }

    const TensorMetadata& get_metadata(const std::string& name) const {
        auto it = tensors_.find(name);
        if (it == tensors_.end()) {
            throw std::runtime_error("Tensor not found: " + name);
        }
        return it->second;
    }

    const uint8_t* get_tensor_data(const std::string& name) const {
        const auto& meta = get_metadata(name);
        uint64_t abs_offset = header_.data_offset + meta.offset;
        if (abs_offset + meta.length > file_size_) {
            throw std::runtime_error("Tensor data out of bounds: " + name);
        }
        return mmap_ptr_ + abs_offset;
    }

    size_t num_tensors() const {
        return tensors_.size();
    }

    size_t file_size() const {
        return file_size_;
    }

private:
    void parse_header() {
        std::memcpy(&header_, mmap_ptr_, sizeof(IMFHeader));
        if (header_.magic != IMF_MAGIC) {
            throw std::runtime_error("Invalid IMF magic number");
        }
        if (header_.version != IMF_VERSION) {
            throw std::runtime_error("Unsupported IMF version: " + std::to_string(header_.version));
        }
    }

    void parse_index() {
        if (header_.index_offset + header_.index_length > file_size_) {
            throw std::runtime_error("Index exceeds file boundaries");
        }

        std::string json_str(
            reinterpret_cast<const char*>(mmap_ptr_ + header_.index_offset),
            header_.index_length
        );

        // Minimal high-speed JSON scanner for tensor records
        // Format: {"name": "...", "shape": [...], "dtype": "...", "encoding": ..., "offset": ..., "length": ..., "checksum": ...}
        size_t pos = 0;
        while ((pos = json_str.find("{\"name\":", pos)) != std::string::npos) {
            size_t end_pos = json_str.find("}", pos);
            if (end_pos == std::string::npos) break;

            std::string entry = json_str.substr(pos, end_pos - pos + 1);
            TensorMetadata meta;

            // Extract name
            size_t n_start = entry.find("\"name\": \"") + 9;
            size_t n_end = entry.find("\"", n_start);
            meta.name = entry.substr(n_start, n_end - n_start);

            // Extract dtype
            size_t d_start = entry.find("\"dtype\": \"");
            if (d_start != std::string::npos) {
                d_start += 10;
                size_t d_end = entry.find("\"", d_start);
                meta.dtype = entry.substr(d_start, d_end - d_start);
            }

            // Extract offset
            size_t off_start = entry.find("\"offset\": ");
            if (off_start != std::string::npos) {
                off_start += 10;
                meta.offset = std::stoull(entry.substr(off_start));
            }

            // Extract length
            size_t len_start = entry.find("\"length\": ");
            if (len_start != std::string::npos) {
                len_start += 10;
                meta.length = std::stoull(entry.substr(len_start));
            }

            // Extract shape
            size_t sh_start = entry.find("\"shape\": [");
            if (sh_start != std::string::npos) {
                sh_start += 10;
                size_t sh_end = entry.find("]", sh_start);
                std::string sh_str = entry.substr(sh_start, sh_end - sh_start);
                size_t c_pos = 0;
                while (c_pos < sh_str.size()) {
                    while (c_pos < sh_str.size() && (sh_str[c_pos] == ' ' || sh_str[c_pos] == ',')) c_pos++;
                    if (c_pos >= sh_str.size()) break;
                    size_t next_c = sh_str.find(',', c_pos);
                    if (next_c == std::string::npos) next_c = sh_str.size();
                    meta.shape.push_back(std::stoll(sh_str.substr(c_pos, next_c - c_pos)));
                    c_pos = next_c + 1;
                }
            }

            tensors_[meta.name] = meta;
            pos = end_pos + 1;
        }
    }

    std::string filepath_;
    int fd_ = -1;
    size_t file_size_ = 0;
    uint8_t* mmap_ptr_ = nullptr;
    IMFHeader header_{};
    std::unordered_map<std::string, TensorMetadata> tensors_;
};

} // namespace imf
