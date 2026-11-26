// csrc/fused_iouring_epoll_eventfd_ring.cpp
// ========================================================
// Production Linux 6.18 io_uring Kernel Eventfd Direct Notification Ring Engine
// Binds an eventfd descriptor directly to the completion ring (io_uring_register_eventfd)
// for zero-latency wakeups of epoll loops and concurrent cognitive loop threads.

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/eventfd.h>
#include <liburing.h>

extern "C" {

struct IOUringEventfdRingEngine {
    struct io_uring ring;
    int event_fd;
    int is_eventfd_registered;
    int is_initialized;
    uint32_t queue_depth;
};

IOUringEventfdRingEngine* iouring_eventfd_ring_init(uint32_t queue_depth, int event_fd) {
    if (queue_depth == 0) queue_depth = 32;

    IOUringEventfdRingEngine* eng = (IOUringEventfdRingEngine*)calloc(1, sizeof(IOUringEventfdRingEngine));
    if (!eng) return nullptr;

    int ret = io_uring_queue_init(queue_depth, &eng->ring, 0);
    if (ret < 0) {
        free(eng);
        return nullptr;
    }

    eng->queue_depth = queue_depth;
    eng->is_initialized = 1;
    eng->event_fd = -1;
    eng->is_eventfd_registered = 0;

    if (event_fd >= 0) {
        ret = io_uring_register_eventfd(&eng->ring, event_fd);
        if (ret == 0) {
            eng->event_fd = event_fd;
            eng->is_eventfd_registered = 1;
        }
    }

    return eng;
}

int iouring_eventfd_ring_register_eventfd(IOUringEventfdRingEngine* eng, int event_fd) {
    if (!eng || !eng->is_initialized || event_fd < 0) return -1;
    if (eng->is_eventfd_registered) {
        io_uring_unregister_eventfd(&eng->ring);
        eng->is_eventfd_registered = 0;
        eng->event_fd = -1;
    }

    int ret = io_uring_register_eventfd(&eng->ring, event_fd);
    if (ret == 0) {
        eng->event_fd = event_fd;
        eng->is_eventfd_registered = 1;
        return 0;
    }
    return ret;
}

int iouring_eventfd_ring_unregister_eventfd(IOUringEventfdRingEngine* eng) {
    if (!eng || !eng->is_initialized || !eng->is_eventfd_registered) return -1;
    int ret = io_uring_unregister_eventfd(&eng->ring);
    eng->is_eventfd_registered = 0;
    eng->event_fd = -1;
    return ret;
}

int iouring_eventfd_ring_submit_nop(IOUringEventfdRingEngine* eng, uint64_t user_data) {
    if (!eng || !eng->is_initialized) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) return -2;

    io_uring_prep_nop(sqe);
    sqe->user_data = user_data;

    int ret = io_uring_submit(&eng->ring);
    return (ret >= 0) ? 0 : ret;
}

int iouring_eventfd_ring_submit_read(
    IOUringEventfdRingEngine* eng,
    int fd,
    void* buf,
    size_t len,
    uint64_t offset,
    uint64_t user_data
) {
    if (!eng || !eng->is_initialized || fd < 0 || !buf) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) return -2;

    io_uring_prep_read(sqe, fd, buf, len, offset);
    sqe->user_data = user_data;

    int ret = io_uring_submit(&eng->ring);
    return (ret >= 0) ? 0 : ret;
}

int iouring_eventfd_ring_reap(IOUringEventfdRingEngine* eng, int* out_res, uint64_t* out_user_data) {
    if (!eng || !eng->is_initialized || !out_res) return -1;

    struct io_uring_cqe* cqe = nullptr;
    int ret = io_uring_peek_cqe(&eng->ring, &cqe);
    if (ret != 0 || !cqe) {
        ret = io_uring_wait_cqe(&eng->ring, &cqe);
        if (ret < 0 || !cqe) return -2;
    }

    *out_res = cqe->res;
    if (out_user_data) {
        *out_user_data = cqe->user_data;
    }

    io_uring_cqe_seen(&eng->ring, cqe);
    return 0;
}

void iouring_eventfd_ring_free(IOUringEventfdRingEngine* eng) {
    if (!eng) return;
    if (eng->is_initialized) {
        if (eng->is_eventfd_registered) {
            io_uring_unregister_eventfd(&eng->ring);
            eng->is_eventfd_registered = 0;
        }
        io_uring_queue_exit(&eng->ring);
        eng->is_initialized = 0;
    }
    free(eng);
}

}
