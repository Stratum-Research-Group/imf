// csrc/fused_iouring_multishot_poll.cpp
// Linux 6.18 Kernel-Bypass: io_uring Multi-Shot Non-Blocking Polling Engine
// Uses IORING_POLL_ADD_MULTI (io_uring_prep_poll_multishot) for sub-microsecond
// event loop dispatch across persistent descriptor readiness triggers.

#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <poll.h>
#include <sys/types.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>

#define MULTISHOT_POLL_QUEUE_DEPTH 128

struct multishot_poll_engine {
    struct io_uring ring;
    int in_flight;
    int total_events_polled;
};

extern "C" struct multishot_poll_engine* init_multishot_poll_engine(int depth) {
    struct multishot_poll_engine* eng = (struct multishot_poll_engine*)malloc(sizeof(struct multishot_poll_engine));
    if (!eng) return NULL;
    memset(eng, 0, sizeof(*eng));

    int q_depth = (depth > 0) ? depth : MULTISHOT_POLL_QUEUE_DEPTH;
    struct io_uring_params params;
    memset(&params, 0, sizeof(params));

    if (io_uring_queue_init_params(q_depth, &eng->ring, &params) < 0) {
        free(eng);
        return NULL;
    }

    eng->in_flight = 0;
    eng->total_events_polled = 0;
    return eng;
}

extern "C" int arm_multishot_poll(
    struct multishot_poll_engine* eng,
    int fd,
    unsigned int poll_mask,
    uint64_t user_data
) {
    if (!eng || fd < 0) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) {
        io_uring_submit(&eng->ring);
        sqe = io_uring_get_sqe(&eng->ring);
        if (!sqe) return -EBUSY;
    }

    io_uring_prep_poll_multishot(sqe, fd, poll_mask);
    io_uring_sqe_set_data64(sqe, user_data);

    int ret = io_uring_submit(&eng->ring);
    if (ret < 0) return ret;

    eng->in_flight++;
    return 0;
}

extern "C" int cancel_multishot_poll(
    struct multishot_poll_engine* eng,
    uint64_t user_data
) {
    if (!eng) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) {
        io_uring_submit(&eng->ring);
        sqe = io_uring_get_sqe(&eng->ring);
        if (!sqe) return -EBUSY;
    }

    io_uring_prep_poll_remove(sqe, user_data);
    return io_uring_submit(&eng->ring);
}

extern "C" int wait_and_drain_poll_events(
    struct multishot_poll_engine* eng,
    uint64_t* out_user_data,
    int* out_revents,
    int max_events,
    int timeout_ms
) {
    if (!eng || max_events <= 0 || !out_user_data || !out_revents) return -1;

    struct __kernel_timespec ts;
    ts.tv_sec = timeout_ms / 1000;
    ts.tv_nsec = (timeout_ms % 1000) * 1000000LL;

    struct io_uring_cqe* cqe = NULL;
    int ret;
    if (timeout_ms >= 0) {
        ret = io_uring_wait_cqe_timeout(&eng->ring, &cqe, &ts);
    } else {
        ret = io_uring_wait_cqe(&eng->ring, &cqe);
    }

    if (ret < 0) {
        if (ret == -ETIME) return 0; // Timeout without events
        return ret;
    }

    int count = 0;
    unsigned head;
    io_uring_for_each_cqe(&eng->ring, head, cqe) {
        if (count < max_events) {
            out_user_data[count] = io_uring_cqe_get_data64(cqe);
            out_revents[count] = cqe->res;
            count++;
        }
    }
    io_uring_cq_advance(&eng->ring, count);

    eng->total_events_polled += count;
    return count;
}

extern "C" void free_multishot_poll_engine(struct multishot_poll_engine* eng) {
    if (!eng) return;
    io_uring_queue_exit(&eng->ring);
    free(eng);
}
