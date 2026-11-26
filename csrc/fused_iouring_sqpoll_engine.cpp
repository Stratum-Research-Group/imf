#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>

#define SQPOLL_QUEUE_DEPTH 64

struct sqpoll_engine {
    struct io_uring ring;
    int target_fd;
    int is_sqpoll;
    int in_flight;
    size_t total_transferred_bytes;
};

extern "C" struct sqpoll_engine* init_sqpoll_engine(const char* file_path, int depth) {
    struct sqpoll_engine* eng = (struct sqpoll_engine*)malloc(sizeof(struct sqpoll_engine));
    if (!eng) return NULL;
    memset(eng, 0, sizeof(*eng));

    eng->target_fd = open(file_path, O_RDWR | O_CREAT, 0644);
    if (eng->target_fd < 0) {
        free(eng);
        return NULL;
    }

    int q_depth = (depth > 0) ? depth : SQPOLL_QUEUE_DEPTH;
    struct io_uring_params params;
    memset(&params, 0, sizeof(params));

    // Attempt SQPOLL initialization for zero-syscall kernel worker polling
    params.flags |= IORING_SETUP_SQPOLL;
    params.sq_thread_idle = 2000; // 2 seconds idle timeout

    int ret = io_uring_queue_init_params(q_depth, &eng->ring, &params);
    if (ret == 0) {
        eng->is_sqpoll = 1;
    } else {
        // Fallback to standard low-latency ring if kernel SQPOLL privileges are restricted
        memset(&params, 0, sizeof(params));
        ret = io_uring_queue_init_params(q_depth, &eng->ring, &params);
        if (ret < 0) {
            close(eng->target_fd);
            free(eng);
            return NULL;
        }
        eng->is_sqpoll = 0;
    }

    eng->in_flight = 0;
    eng->total_transferred_bytes = 0;
    return eng;
}

extern "C" int is_sqpoll_active(struct sqpoll_engine* eng) {
    if (!eng) return -1;
    return eng->is_sqpoll;
}

extern "C" int submit_sqpoll_write(struct sqpoll_engine* eng, const void* buf, size_t count, off_t offset) {
    if (!eng || !buf || count == 0) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) {
        // Queue full, submit in-flight entries
        io_uring_submit(&eng->ring);
        sqe = io_uring_get_sqe(&eng->ring);
        if (!sqe) return -EBUSY;
    }

    io_uring_prep_write(sqe, eng->target_fd, buf, count, offset);
    io_uring_sqe_set_data(sqe, (void*)(uintptr_t)1);
    eng->in_flight++;

    // When SQPOLL is active, writing to the ring tail notifies the kernel thread automatically,
    // but io_uring_submit() checks if the thread needs waking.
    return io_uring_submit(&eng->ring);
}

extern "C" int submit_sqpoll_read(struct sqpoll_engine* eng, void* buf, size_t count, off_t offset) {
    if (!eng || !buf || count == 0) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) {
        io_uring_submit(&eng->ring);
        sqe = io_uring_get_sqe(&eng->ring);
        if (!sqe) return -EBUSY;
    }

    io_uring_prep_read(sqe, eng->target_fd, buf, count, offset);
    io_uring_sqe_set_data(sqe, (void*)(uintptr_t)2);
    eng->in_flight++;

    return io_uring_submit(&eng->ring);
}

extern "C" int wait_sqpoll_completions(struct sqpoll_engine* eng, int min_complete) {
    if (!eng) return -1;
    int completed = 0;
    struct io_uring_cqe* cqe = NULL;

    while (eng->in_flight > 0 && completed < min_complete) {
        int ret = io_uring_wait_cqe(&eng->ring, &cqe);
        if (ret < 0) {
            break;
        }
        if (cqe->res > 0) {
            eng->total_transferred_bytes += cqe->res;
        }
        io_uring_cqe_seen(&eng->ring, cqe);
        eng->in_flight--;
        completed++;
    }
    return completed;
}

extern "C" void close_sqpoll_engine(struct sqpoll_engine* eng) {
    if (!eng) return;
    if (eng->in_flight > 0) {
        wait_sqpoll_completions(eng, eng->in_flight);
    }
    io_uring_queue_exit(&eng->ring);
    if (eng->target_fd >= 0) {
        close(eng->target_fd);
    }
    free(eng);
}
