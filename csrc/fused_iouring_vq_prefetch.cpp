#define _GNU_SOURCE
#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#define PREFETCH_QUEUE_DEPTH 64

struct vq_prefetch_engine {
    struct io_uring ring;
    int fd;
    int in_flight;
    size_t total_prefetched;
};

extern "C" struct vq_prefetch_engine* init_vq_prefetch_engine(const char* weights_path, int queue_depth) {
    struct vq_prefetch_engine* eng = (struct vq_prefetch_engine*)malloc(sizeof(struct vq_prefetch_engine));
    if (!eng) return NULL;
    memset(eng, 0, sizeof(*eng));

    eng->fd = open(weights_path, O_RDONLY | O_DIRECT);
    if (eng->fd < 0) {
        eng->fd = open(weights_path, O_RDONLY);
        if (eng->fd < 0) {
            free(eng);
            return NULL;
        }
    }

    int depth = (queue_depth > 0) ? queue_depth : PREFETCH_QUEUE_DEPTH;
    struct io_uring_params params;
    memset(&params, 0, sizeof(params));

    if (io_uring_queue_init_params(depth, &eng->ring, &params) < 0) {
        close(eng->fd);
        free(eng);
        return NULL;
    }

    eng->in_flight = 0;
    eng->total_prefetched = 0;
    return eng;
}

extern "C" int submit_vq_weight_prefetch(
    struct vq_prefetch_engine* eng,
    void* pinned_dst_buffer,
    size_t length,
    off_t file_offset
) {
    if (!eng || eng->fd < 0 || !pinned_dst_buffer) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) {
        io_uring_submit_and_wait(&eng->ring, 1);
        sqe = io_uring_get_sqe(&eng->ring);
        if (!sqe) return -2;
    }

    io_uring_prep_read(sqe, eng->fd, pinned_dst_buffer, length, file_offset);
    io_uring_sqe_set_data(sqe, pinned_dst_buffer);

    int ret = io_uring_submit(&eng->ring);
    if (ret > 0) {
        eng->in_flight++;
        eng->total_prefetched += length;
    }
    return ret;
}

extern "C" int reap_vq_prefetch_completions(struct vq_prefetch_engine* eng, int min_complete) {
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

extern "C" void close_vq_prefetch_engine(struct vq_prefetch_engine* eng) {
    if (!eng) return;
    reap_vq_prefetch_completions(eng, eng->in_flight);
    close(eng->fd);
    io_uring_queue_exit(&eng->ring);
    free(eng);
}
