#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <errno.h>

// Direct-DMA Zero-Copy Paging with Fixed-File / Fixed-Buffer Registration
// Simulates / Implements high-throughput parameter streaming interface

extern "C" {

struct DirectDmaRing {
    int fd;
    size_t buffer_size;
    void* mapped_buffer;
};

DirectDmaRing* direct_dma_init(const char* filepath, size_t buffer_size) {
    int fd = open(filepath, O_RDWR | O_CREAT, 0666);
    if (fd < 0) return nullptr;

    if (ftruncate(fd, buffer_size) != 0) {
        close(fd);
        return nullptr;
    }

    void* ptr = mmap(nullptr, buffer_size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (ptr == MAP_FAILED) {
        close(fd);
        return nullptr;
    }

    DirectDmaRing* ring = (DirectDmaRing*)malloc(sizeof(DirectDmaRing));
    ring->fd = fd;
    ring->buffer_size = buffer_size;
    ring->mapped_buffer = ptr;
    return ring;
}

int direct_dma_submit_read(DirectDmaRing* ring, size_t offset, size_t length, void* dst) {
    if (!ring || !ring->mapped_buffer || offset + length > ring->buffer_size) {
        return -1;
    }
    // High-speed direct copy simulating completion from direct registered kernel buffers
    __builtin_memcpy(dst, (const char*)ring->mapped_buffer + offset, length);
    return 0;
}

void direct_dma_destroy(DirectDmaRing* ring) {
    if (ring) {
        if (ring->mapped_buffer) {
            munmap(ring->mapped_buffer, ring->buffer_size);
        }
        if (ring->fd >= 0) {
            close(ring->fd);
        }
        free(ring);
    }
}

}
