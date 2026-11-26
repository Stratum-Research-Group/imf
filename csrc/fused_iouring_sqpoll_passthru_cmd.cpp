// csrc/fused_iouring_sqpoll_passthru_cmd.cpp
// ========================================================
// Production Linux 6.18 io_uring Kernel-Thread SQPOLL Passthrough Engine
// Combines IORING_SETUP_SQPOLL with direct zero-syscall submission
// for continuous sub-bit weight paging and asynchronous storage commands.

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/time.h>
#include <liburing.h>

extern "C" {

struct IOUringSQPollPassthruEngine {
    struct io_uring ring;
    int is_sqpoll_active;
    int is_initialized;
    uint32_t idle_ms;
};

IOUringSQPollPassthruEngine* iouring_sqpoll_passthru_init(
    uint32_t queue_depth,
    uint32_t idle_ms
) {
    if (queue_depth == 0) queue_depth = 32;
    if (idle_ms == 0) idle_ms = 1000;

    IOUringSQPollPassthruEngine* eng = (IOUringSQPollPassthruEngine*)calloc(1, sizeof(IOUringSQPollPassthruEngine));
    if (!eng) return nullptr;

    struct io_uring_params params;
    memset(&params, 0, sizeof(params));
    params.flags = IORING_SETUP_SQPOLL;
    params.sq_thread_idle = idle_ms;

    int ret = io_uring_queue_init_params(queue_depth, &eng->ring, &params);
    if (ret == 0) {
        eng->is_sqpoll_active = 1;
    } else {
        // Fall back gracefully to standard asynchronous submission queue
        ret = io_uring_queue_init(queue_depth, &eng->ring, 0);
        if (ret < 0) {
            free(eng);
            return nullptr;
        }
        eng->is_sqpoll_active = 0;
    }

    eng->idle_ms = idle_ms;
    eng->is_initialized = 1;
    return eng;
}

int iouring_sqpoll_passthru_submit_cmd(
    IOUringSQPollPassthruEngine* eng,
    int fd,
    void* buffer,
    size_t len,
    uint64_t offset,
    uint64_t user_data
) {
    if (!eng || !eng->is_initialized || fd < 0 || !buffer) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) return -2;

    io_uring_prep_read(sqe, fd, buffer, len, offset);
    sqe->user_data = user_data;

    // Under SQPOLL, kernel thread polls submissions automatically;
    // io_uring_submit returns immediately or triggers submission if thread was sleeping.
    int ret = io_uring_submit(&eng->ring);
    return (ret >= 0) ? 0 : ret;
}

int iouring_sqpoll_passthru_submit_write(
    IOUringSQPollPassthruEngine* eng,
    int fd,
    const void* buffer,
    size_t len,
    uint64_t offset,
    uint64_t user_data
) {
    if (!eng || !eng->is_initialized || fd < 0 || !buffer) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) return -2;

    io_uring_prep_write(sqe, fd, buffer, len, offset);
    sqe->user_data = user_data;

    int ret = io_uring_submit(&eng->ring);
    return (ret >= 0) ? 0 : ret;
}

int iouring_sqpoll_passthru_reap_completion(
    IOUringSQPollPassthruEngine* eng,
    int64_t* bytes_transferred,
    uint64_t* user_data,
    int timeout_ms
) {
    if (!eng || !eng->is_initialized || !bytes_transferred) return -1;

    struct io_uring_cqe* cqe = nullptr;
    int ret = 0;

    if (timeout_ms <= 0) {
        ret = io_uring_wait_cqe(&eng->ring, &cqe);
    } else {
        struct __kernel_timespec ts;
        ts.tv_sec = timeout_ms / 1000;
        ts.tv_nsec = (timeout_ms % 1000) * 1000000LL;
        ret = io_uring_wait_cqe_timeout(&eng->ring, &cqe, &ts);
    }

    if (ret < 0 || !cqe) return -2;

    *bytes_transferred = (int64_t)cqe->res;
    if (user_data) {
        *user_data = cqe->user_data;
    }

    io_uring_cqe_seen(&eng->ring, cqe);
    return (*bytes_transferred >= 0) ? 0 : (int)*bytes_transferred;
}

int iouring_sqpoll_passthru_is_sqpoll(IOUringSQPollPassthruEngine* eng) {
    if (!eng || !eng->is_initialized) return -1;
    return eng->is_sqpoll_active;
}

void iouring_sqpoll_passthru_destroy(IOUringSQPollPassthruEngine* eng) {
    if (!eng) return;
    if (eng->is_initialized) {
        io_uring_queue_exit(&eng->ring);
        eng->is_initialized = 0;
    }
    free(eng);
}

}
