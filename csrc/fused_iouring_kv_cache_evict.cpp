#define _GNU_SOURCE
#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#define EVICT_QUEUE_DEPTH 64

struct kv_evict_engine {
    struct io_uring ring;
    int evict_fd;
    int in_flight;
    size_t total_evicted_bytes;
};

extern "C" struct kv_evict_engine* init_kv_evict_engine(const char* evict_swap_path, int depth) {
    struct kv_evict_engine* eng = (struct kv_evict_engine*)malloc(sizeof(struct kv_evict_engine));
    if (!eng) return NULL;
    memset(eng, 0, sizeof(*eng));

    // Open file with O_DIRECT and O_CREAT for zero-buffer-cache flushing
    eng->evict_fd = open(evict_swap_path, O_WRONLY | O_CREAT | O_DIRECT, 0644);
    if (eng->evict_fd < 0) {
        eng->evict_fd = open(evict_swap_path, O_WRONLY | O_CREAT, 0644);
        if (eng->evict_fd < 0) {
            free(eng);
            return NULL;
        }
    }

    int q_depth = (depth > 0) ? depth : EVICT_QUEUE_DEPTH;
    struct io_uring_params params;
    memset(&params, 0, sizeof(params));
    // SQPOLL kernel polling thread to eliminate user-to-kernel context switches
    params.flags = IORING_SETUP_SQPOLL;
    params.sq_thread_idle = 2000; // 2 seconds idle timeout

    if (io_uring_queue_init_params(q_depth, &eng->ring, &params) < 0) {
        // Fallback without SQPOLL if permissions/limits disallow kernel thread
        memset(&params, 0, sizeof(params));
        if (io_uring_queue_init_params(q_depth, &eng->ring, &params) < 0) {
            close(eng->evict_fd);
            free(eng);
            return NULL;
        }
    }

    eng->in_flight = 0;
    eng->total_evicted_bytes = 0;
    return eng;
}

extern "C" int submit_kv_page_eviction(
    struct kv_evict_engine* eng,
    const void* page_buffer,
    size_t length,
    off_t swap_offset
) {
    if (!eng || eng->evict_fd < 0 || !page_buffer) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) {
        io_uring_submit_and_wait(&eng->ring, 1);
        sqe = io_uring_get_sqe(&eng->ring);
        if (!sqe) return -2;
    }

    io_uring_prep_write(sqe, eng->evict_fd, page_buffer, length, swap_offset);
    io_uring_sqe_set_data(sqe, (void*)(uintptr_t)swap_offset);

    int ret = io_uring_submit(&eng->ring);
    if (ret > 0) {
        eng->in_flight++;
        eng->total_evicted_bytes += length;
    }
    return ret;
}

extern "C" int reap_kv_eviction_completions(struct kv_evict_engine* eng, int min_complete) {
    if (!eng) return -1;
    int reaped = 0;
    struct io_uring_cqe* cqe;

    while (reaped < min_complete && eng->in_flight > 0) {
        if (io_uring_wait_cqe(&eng->ring, &cqe) == 0) {
            io_uring_cqe_seen(&eng->ring, cqe);
            eng->in_flight--;
            reaped++;
        } else {
            break;
        }
    }

    while (eng->in_flight > 0) {
        if (io_uring_peek_cqe(&eng->ring, &cqe) == 0 && cqe) {
            io_uring_cqe_seen(&eng->ring, cqe);
            eng->in_flight--;
            reaped++;
        } else {
            break;
        }
    }

    return reaped;
}

extern "C" void close_kv_evict_engine(struct kv_evict_engine* eng) {
    if (!eng) return;
    reap_kv_eviction_completions(eng, eng->in_flight);
    fsync(eng->evict_fd);
    close(eng->evict_fd);
    io_uring_queue_exit(&eng->ring);
    free(eng);
}
