// csrc/fused_iouring_multishot_read_ringbuf.cpp
// ========================================================
// Production Linux 6.18 io_uring Multishot Buffer-Ring Ingestion Engine
// Implements zero-syscall streaming packet ingestion via IORING_OP_RECV_MULTISHOT
// and kernel-managed buffer selection rings (IOU_PBUF_RING).

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/mman.h>
#include <liburing.h>

extern "C" {

struct IOUringRingbufEngine {
    struct io_uring ring;
    struct io_uring_buf_ring* br;
    uint8_t* buffer_pool;
    unsigned int buf_count;
    unsigned int buf_size;
    int bgid;
    int is_initialized;
};

IOUringRingbufEngine* iouring_ringbuf_engine_init(
    unsigned int entries,
    unsigned int buf_count,
    unsigned int buf_size,
    int bgid
) {
    if (entries == 0) entries = 32;
    if (buf_count == 0) buf_count = 16;
    if (buf_size == 0) buf_size = 512;
    if (bgid < 0) bgid = 1;

    IOUringRingbufEngine* eng = (IOUringRingbufEngine*)calloc(1, sizeof(IOUringRingbufEngine));
    if (!eng) return nullptr;

    int ret = io_uring_queue_init(entries, &eng->ring, 0);
    if (ret < 0) {
        free(eng);
        return nullptr;
    }

    eng->buf_count = buf_count;
    eng->buf_size = buf_size;
    eng->bgid = bgid;

    // Allocate memory pool for buffers
    size_t pool_bytes = (size_t)buf_count * buf_size;
    eng->buffer_pool = (uint8_t*)aligned_alloc(4096, pool_bytes);
    if (!eng->buffer_pool) {
        io_uring_queue_exit(&eng->ring);
        free(eng);
        return nullptr;
    }
    memset(eng->buffer_pool, 0, pool_bytes);

    // Setup buffer ring via liburing
    eng->br = io_uring_setup_buf_ring(&eng->ring, buf_count, bgid, 0, &ret);
    if (!eng->br || ret < 0) {
        // Fallback or cleanup
        free(eng->buffer_pool);
        io_uring_queue_exit(&eng->ring);
        free(eng);
        return nullptr;
    }

    // Populate buffer ring
    for (unsigned int i = 0; i < buf_count; i++) {
        io_uring_buf_ring_add(
            eng->br,
            eng->buffer_pool + (size_t)i * buf_size,
            buf_size,
            i, // bid
            io_uring_buf_ring_mask(buf_count),
            i
        );
    }
    io_uring_buf_ring_advance(eng->br, buf_count);

    eng->is_initialized = 1;
    return eng;
}

int iouring_ringbuf_engine_submit_recv_multishot(
    IOUringRingbufEngine* eng,
    int socket_fd,
    uint64_t user_data
) {
    if (!eng || !eng->is_initialized || socket_fd < 0) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) return -2;

    io_uring_prep_recv_multishot(sqe, socket_fd, nullptr, 0, 0);
    sqe->flags |= IOSQE_BUFFER_SELECT;
    sqe->buf_group = eng->bgid;
    io_uring_sqe_set_data64(sqe, user_data);

    return 0;
}

int iouring_ringbuf_engine_submit(IOUringRingbufEngine* eng) {
    if (!eng || !eng->is_initialized) return -1;
    return io_uring_submit(&eng->ring);
}

int iouring_ringbuf_engine_wait_cqe(
    IOUringRingbufEngine* eng,
    int* out_res,
    uint32_t* out_flags,
    uint64_t* out_user_data,
    int* out_bid
) {
    if (!eng || !eng->is_initialized || !out_res || !out_flags || !out_user_data || !out_bid) {
        return -1;
    }

    struct io_uring_cqe* cqe = nullptr;
    int ret = io_uring_wait_cqe(&eng->ring, &cqe);
    if (ret < 0) return ret;

    *out_res = cqe->res;
    *out_flags = cqe->flags;
    *out_user_data = cqe->user_data;

    if (cqe->flags & IORING_CQE_F_BUFFER) {
        *out_bid = cqe->flags >> IORING_CQE_BUFFER_SHIFT;
    } else {
        *out_bid = -1;
    }

    io_uring_cqe_seen(&eng->ring, cqe);
    return 0;
}

uint8_t* iouring_ringbuf_engine_get_buf(IOUringRingbufEngine* eng, int bid) {
    if (!eng || !eng->is_initialized || bid < 0 || (unsigned int)bid >= eng->buf_count) {
        return nullptr;
    }
    return eng->buffer_pool + (size_t)bid * eng->buf_size;
}

void iouring_ringbuf_engine_recycle_buf(IOUringRingbufEngine* eng, int bid) {
    if (!eng || !eng->is_initialized || bid < 0 || (unsigned int)bid >= eng->buf_count) {
        return;
    }
    io_uring_buf_ring_add(
        eng->br,
        eng->buffer_pool + (size_t)bid * eng->buf_size,
        eng->buf_size,
        bid,
        io_uring_buf_ring_mask(eng->buf_count),
        0
    );
    io_uring_buf_ring_advance(eng->br, 1);
}

void iouring_ringbuf_engine_destroy(IOUringRingbufEngine* eng) {
    if (!eng) return;
    if (eng->is_initialized) {
        if (eng->br) {
            io_uring_free_buf_ring(&eng->ring, eng->br, eng->buf_count, eng->bgid);
            eng->br = nullptr;
        }
        if (eng->buffer_pool) {
            free(eng->buffer_pool);
            eng->buffer_pool = nullptr;
        }
        io_uring_queue_exit(&eng->ring);
        eng->is_initialized = 0;
    }
    free(eng);
}

}
