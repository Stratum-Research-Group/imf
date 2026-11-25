#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

// Kernel-Level Multi-Tier Direct-DMA Priority Queue
// Differentiates between High-Priority Attention KV Requests and Background Weight Prefetching

extern "C" {

enum DmaPriority {
    DMA_PRIORITY_LOW = 0,   // Background weight streaming
    DMA_PRIORITY_HIGH = 1   // Real-time KV cache paging
};

struct DmaQueueEntry {
    uint32_t request_id;
    DmaPriority priority;
    void* dst_buffer;
    size_t length;
};

struct DmaPriorityQueue {
    DmaQueueEntry entries[64];
    int count;
};

DmaPriorityQueue* dma_priority_queue_create() {
    DmaPriorityQueue* q = (DmaPriorityQueue*)malloc(sizeof(DmaPriorityQueue));
    if (q) {
        q->count = 0;
    }
    return q;
}

int dma_enqueue_request(DmaPriorityQueue* q, uint32_t req_id, DmaPriority prio, void* dst, size_t len) {
    if (!q || q->count >= 64) return -1;
    q->entries[q->count].request_id = req_id;
    q->entries[q->count].priority = prio;
    q->entries[q->count].dst_buffer = dst;
    q->entries[q->count].length = len;
    q->count++;
    return 0;
}

int dma_dispatch_highest_priority(DmaPriorityQueue* q, DmaQueueEntry* out_entry) {
    if (!q || q->count == 0 || !out_entry) return -1;

    // Scan for highest priority
    int best_idx = 0;
    for (int i = 1; i < q->count; ++i) {
        if (q->entries[i].priority > q->entries[best_idx].priority) {
            best_idx = i;
        }
    }

    *out_entry = q->entries[best_idx];

    // Shift remaining entries
    for (int i = best_idx; i < q->count - 1; ++i) {
        q->entries[i] = q->entries[i + 1];
    }
    q->count--;
    return 0;
}

void dma_priority_queue_destroy(DmaPriorityQueue* q) {
    if (q) free(q);
}

}
