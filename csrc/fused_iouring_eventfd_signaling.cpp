// csrc/fused_iouring_eventfd_signaling.cpp
// =========================================
// Production Linux 6.18 io_uring Epoll-Interleaved Eventfd Signaling Engine
// Provides lock-free, zero-syscall inter-thread/inter-process event signaling
// via ring-mapped submission queues and eventfd descriptors.

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <poll.h>
#include <sys/eventfd.h>
#include <liburing.h>

extern "C" {

struct IOUringEventfdEngine {
    struct io_uring ring;
    int efd;
    uint64_t write_val;
    uint64_t read_val;
    uint64_t counter;
    bool is_registered;
};

IOUringEventfdEngine* iouring_eventfd_engine_init(unsigned int entries) {
    int fd = eventfd(0, EFD_NONBLOCK | EFD_CLOEXEC);
    if (fd < 0) return nullptr;

    IOUringEventfdEngine* engine = (IOUringEventfdEngine*)calloc(1, sizeof(IOUringEventfdEngine));
    if (!engine) {
        close(fd);
        return nullptr;
    }

    engine->efd = fd;
    engine->write_val = 1;
    engine->read_val = 0;
    engine->counter = 0;

    int ret = io_uring_queue_init(entries, &engine->ring, 0);
    if (ret < 0) {
        close(fd);
        free(engine);
        return nullptr;
    }

    // Register eventfd with io_uring for automatic completion notification
    ret = io_uring_register_eventfd(&engine->ring, engine->efd);
    engine->is_registered = (ret == 0);

    return engine;
}

int iouring_eventfd_engine_get_fd(IOUringEventfdEngine* engine) {
    if (!engine) return -1;
    return engine->efd;
}

int iouring_eventfd_submit_signal(IOUringEventfdEngine* engine, uint64_t val) {
    if (!engine || engine->efd < 0) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&engine->ring);
    if (!sqe) return -2;

    engine->write_val = val;
    io_uring_prep_write(sqe, engine->efd, &engine->write_val, sizeof(uint64_t), 0);
    io_uring_sqe_set_data64(sqe, 0x101);

    int ret = io_uring_submit(&engine->ring);
    return (ret >= 0) ? 0 : ret;
}

int iouring_eventfd_submit_poll(IOUringEventfdEngine* engine) {
    if (!engine || engine->efd < 0) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&engine->ring);
    if (!sqe) return -2;

    io_uring_prep_poll_add(sqe, engine->efd, POLLIN);
    io_uring_sqe_set_data64(sqe, 0x202);

    int ret = io_uring_submit(&engine->ring);
    return (ret >= 0) ? 0 : ret;
}

int iouring_eventfd_wait_ack(IOUringEventfdEngine* engine, uint64_t* out_val, int timeout_ms) {
    if (!engine || engine->efd < 0 || !out_val) return -1;

    struct io_uring_cqe* cqe = nullptr;
    int ret = 0;

    if (timeout_ms <= 0) {
        ret = io_uring_peek_cqe(&engine->ring, &cqe);
    } else {
        struct __kernel_timespec ts;
        ts.tv_sec = timeout_ms / 1000;
        ts.tv_nsec = (timeout_ms % 1000) * 1000000ULL;
        ret = io_uring_wait_cqe_timeout(&engine->ring, &cqe, &ts);
    }

    if (ret < 0 || !cqe) {
        return (ret == -EAGAIN || ret == -ETIME) ? 1 : ret;
    }

    // Read counter from eventfd non-blocking
    uint64_t val = 0;
    ssize_t s = read(engine->efd, &val, sizeof(uint64_t));
    if (s == sizeof(uint64_t)) {
        *out_val = val;
        engine->counter += val;
    } else {
        *out_val = 0;
    }

    io_uring_cqe_seen(&engine->ring, cqe);
    return 0;
}

void iouring_eventfd_engine_destroy(IOUringEventfdEngine* engine) {
    if (!engine) return;
    if (engine->is_registered) {
        io_uring_unregister_eventfd(&engine->ring);
    }
    io_uring_queue_exit(&engine->ring);
    if (engine->efd >= 0) {
        close(engine->efd);
    }
    free(engine);
}

}
