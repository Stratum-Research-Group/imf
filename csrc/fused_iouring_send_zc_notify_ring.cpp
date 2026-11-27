// csrc/fused_iouring_send_zc_notify_ring.cpp
// ========================================================
// Production Linux 6.18 io_uring Zero-Copy Send with Notification Ring Engine
// Simulates kernel-level zero-copy socket transmission (IORING_OP_SEND_ZC)
// and asynchronous NIC DMA completion notifications (IORING_RECVSEND_NOTIF_FLUSH).

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

extern "C" {

struct SendZcBufferSlot {
    void* buf_addr;
    uint64_t buf_len;
    uint64_t pending_bytes;
    int is_registered;
    int has_notification;
};

struct IOUringSendZcEngine {
    SendZcBufferSlot* slots;
    uint32_t capacity;
    uint64_t total_sends;
    uint64_t total_bytes;
    uint64_t total_notifs;
    int is_initialized;
};

IOUringSendZcEngine* iouring_send_zc_notify_init(uint32_t capacity) {
    if (capacity == 0) capacity = 128;

    IOUringSendZcEngine* eng = (IOUringSendZcEngine*)calloc(1, sizeof(IOUringSendZcEngine));
    if (!eng) return nullptr;

    eng->slots = (SendZcBufferSlot*)calloc(capacity, sizeof(SendZcBufferSlot));
    if (!eng->slots) {
        free(eng);
        return nullptr;
    }

    eng->capacity = capacity;
    eng->total_sends = 0;
    eng->total_bytes = 0;
    eng->total_notifs = 0;
    eng->is_initialized = 1;
    return eng;
}

int iouring_send_zc_register_buf(
    IOUringSendZcEngine* eng,
    uint32_t slot_idx,
    void* buf_addr,
    uint64_t buf_len
) {
    if (!eng || !eng->is_initialized || slot_idx >= eng->capacity || !buf_addr) return -1;

    eng->slots[slot_idx].buf_addr = buf_addr;
    eng->slots[slot_idx].buf_len = buf_len;
    eng->slots[slot_idx].pending_bytes = 0;
    eng->slots[slot_idx].is_registered = 1;
    eng->slots[slot_idx].has_notification = 0;
    return 0;
}

int iouring_send_zc_submit_send(
    IOUringSendZcEngine* eng,
    uint32_t slot_idx,
    uint64_t bytes,
    uint32_t flags
) {
    if (!eng || !eng->is_initialized || slot_idx >= eng->capacity) return -1;
    if (!eng->slots[slot_idx].is_registered) return -2;

    eng->slots[slot_idx].pending_bytes += bytes;
    eng->slots[slot_idx].has_notification = 1;
    eng->total_sends++;
    eng->total_bytes += bytes;
    return 0;
}

int iouring_send_zc_flush_notifs(
    IOUringSendZcEngine* eng,
    uint32_t* completed_count
) {
    if (!eng || !eng->is_initialized) return -1;

    uint32_t count = 0;
    for (uint32_t i = 0; i < eng->capacity; ++i) {
        if (eng->slots[i].is_registered && eng->slots[i].has_notification) {
            eng->slots[i].has_notification = 0;
            eng->slots[i].pending_bytes = 0;
            count++;
            eng->total_notifs++;
        }
    }

    if (completed_count) *completed_count = count;
    return 0;
}

int iouring_send_zc_get_stats(
    IOUringSendZcEngine* eng,
    uint64_t* total_sends,
    uint64_t* total_bytes,
    uint64_t* total_notifs
) {
    if (!eng || !eng->is_initialized) return -1;
    if (total_sends) *total_sends = eng->total_sends;
    if (total_bytes) *total_bytes = eng->total_bytes;
    if (total_notifs) *total_notifs = eng->total_notifs;
    return 0;
}

void iouring_send_zc_free(IOUringSendZcEngine* eng) {
    if (!eng) return;
    if (eng->slots) {
        free(eng->slots);
    }
    free(eng);
}

}
