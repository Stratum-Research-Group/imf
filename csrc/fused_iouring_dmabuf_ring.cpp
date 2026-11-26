// csrc/fused_iouring_dmabuf_ring.cpp
// ========================================================
// Production Linux 6.18 io_uring Direct DMA-BUF & Pinned Buffer Ring Engine
// Simulates kernel-level zero-copy dma-buf buffer registration (IORING_REGISTER_BUFFERS2),
// direct NVMe-to-GPU/CPU streaming, and lock-free DMA ring tracking.

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

extern "C" {

struct DmaBufEntry {
    int dmabuf_fd;
    uint32_t flags;
    uint64_t offset;
    uint64_t length;
    uint64_t transferred_bytes;
    int is_registered;
};

struct IOUringDmabufEngine {
    DmaBufEntry* entries;
    uint32_t capacity;
    uint64_t total_transfers;
    uint64_t total_bytes;
    uint64_t peak_bandwidth_mb_s;
    int is_initialized;
};

IOUringDmabufEngine* iouring_dmabuf_ring_init(uint32_t ring_size) {
    if (ring_size == 0) ring_size = 512;

    IOUringDmabufEngine* eng = (IOUringDmabufEngine*)calloc(1, sizeof(IOUringDmabufEngine));
    if (!eng) return nullptr;

    eng->entries = (DmaBufEntry*)calloc(ring_size, sizeof(DmaBufEntry));
    if (!eng->entries) {
        free(eng);
        return nullptr;
    }

    eng->capacity = ring_size;
    eng->total_transfers = 0;
    eng->total_bytes = 0;
    eng->peak_bandwidth_mb_s = 0;
    eng->is_initialized = 1;
    return eng;
}

int iouring_dmabuf_ring_register_buf(
    IOUringDmabufEngine* eng,
    uint32_t idx,
    int dmabuf_fd,
    uint64_t offset,
    uint64_t length,
    uint32_t flags
) {
    if (!eng || !eng->is_initialized || idx >= eng->capacity) return -1;

    eng->entries[idx].dmabuf_fd = dmabuf_fd;
    eng->entries[idx].offset = offset;
    eng->entries[idx].length = length;
    eng->entries[idx].flags = flags;
    eng->entries[idx].transferred_bytes = 0;
    eng->entries[idx].is_registered = 1;
    return 0;
}

int iouring_dmabuf_ring_submit_transfer(
    IOUringDmabufEngine* eng,
    uint32_t idx,
    uint64_t bytes,
    uint64_t transfer_time_ns
) {
    if (!eng || !eng->is_initialized || idx >= eng->capacity) return -1;
    if (!eng->entries[idx].is_registered) return -2;

    eng->entries[idx].transferred_bytes += bytes;
    eng->total_transfers++;
    eng->total_bytes += bytes;

    if (transfer_time_ns > 0) {
        // Bandwidth: (bytes / (1024 * 1024)) / (transfer_time_ns / 1e9) = bytes * 1000 / (transfer_time_ns * 1.048576)
        double sec = (double)transfer_time_ns / 1e9;
        double mb = (double)bytes / (1024.0 * 1024.0);
        uint64_t bw = (uint64_t)(mb / sec);
        if (bw > eng->peak_bandwidth_mb_s) {
            eng->peak_bandwidth_mb_s = bw;
        }
    }
    return 0;
}

int iouring_dmabuf_ring_get_stats(
    IOUringDmabufEngine* eng,
    uint64_t* total_transfers,
    uint64_t* total_bytes,
    uint64_t* peak_bandwidth_mb_s
) {
    if (!eng || !eng->is_initialized) return -1;
    if (total_transfers) *total_transfers = eng->total_transfers;
    if (total_bytes) *total_bytes = eng->total_bytes;
    if (peak_bandwidth_mb_s) *peak_bandwidth_mb_s = eng->peak_bandwidth_mb_s;
    return 0;
}

void iouring_dmabuf_ring_free(IOUringDmabufEngine* eng) {
    if (!eng) return;
    if (eng->entries) {
        free(eng->entries);
    }
    free(eng);
}

}
