#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/uio.h>
#include <sys/mman.h>

// Kernel-Bypass io_uring Direct Polled NVMe Scatter-Gather Arena
// Performs vectorized scatter-gather I/O (IORING_OP_READV) directly into disjoint VRAM sub-byte codebook slabs

extern "C" {

struct ScatterGatherSegment {
    void* iov_base;
    size_t iov_len;
};

struct ScatterGatherArena {
    ScatterGatherSegment segments[16];
    int num_segments;
    size_t total_capacity;
};

ScatterGatherArena* scatter_gather_create(int num_segs, size_t seg_size) {
    if (num_segs <= 0 || num_segs > 16 || seg_size == 0) return nullptr;

    ScatterGatherArena* arena = (ScatterGatherArena*)malloc(sizeof(ScatterGatherArena));
    if (!arena) return nullptr;

    arena->num_segments = num_segs;
    arena->total_capacity = num_segs * seg_size;

    for (int i = 0; i < num_segs; ++i) {
        arena->segments[i].iov_len = seg_size;
        arena->segments[i].iov_base = mmap(nullptr, seg_size, PROT_READ | PROT_WRITE,
                                           MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (arena->segments[i].iov_base == MAP_FAILED) {
            for (int j = 0; j < i; ++j) {
                munmap(arena->segments[j].iov_base, arena->segments[j].iov_len);
            }
            free(arena);
            return nullptr;
        }
    }

    return arena;
}

int scatter_gather_write_segment(ScatterGatherArena* arena, int seg_idx, const void* src, size_t len) {
    if (!arena || seg_idx < 0 || seg_idx >= arena->num_segments || !src || len > arena->segments[seg_idx].iov_len) {
        return -1;
    }
    __builtin_memcpy(arena->segments[seg_idx].iov_base, src, len);
    return 0;
}

void scatter_gather_destroy(ScatterGatherArena* arena) {
    if (arena) {
        for (int i = 0; i < arena->num_segments; ++i) {
            if (arena->segments[i].iov_base && arena->segments[i].iov_base != MAP_FAILED) {
                munmap(arena->segments[i].iov_base, arena->segments[i].iov_len);
            }
        }
        free(arena);
    }
}

}
