#define _GNU_SOURCE
#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#define ROLLBACK_QUEUE_DEPTH 64

struct checkpoint_rollback_engine {
    struct io_uring ring;
    int checkpoint_fd;
    int in_flight;
    size_t total_restored_bytes;
};

extern "C" struct checkpoint_rollback_engine* init_checkpoint_rollback_engine(const char* checkpoint_path, int depth) {
    struct checkpoint_rollback_engine* eng = (struct checkpoint_rollback_engine*)malloc(sizeof(struct checkpoint_rollback_engine));
    if (!eng) return NULL;
    memset(eng, 0, sizeof(*eng));

    eng->checkpoint_fd = open(checkpoint_path, O_RDWR | O_DIRECT);
    if (eng->checkpoint_fd < 0) {
        eng->checkpoint_fd = open(checkpoint_path, O_RDWR);
        if (eng->checkpoint_fd < 0) {
            free(eng);
            return NULL;
        }
    }

    int q_depth = (depth > 0) ? depth : ROLLBACK_QUEUE_DEPTH;
    struct io_uring_params params;
    memset(&params, 0, sizeof(params));

    if (io_uring_queue_init_params(q_depth, &eng->ring, &params) < 0) {
        close(eng->checkpoint_fd);
        free(eng);
        return NULL;
    }

    eng->in_flight = 0;
    eng->total_restored_bytes = 0;
    return eng;
}

extern "C" int submit_checkpoint_rollback_read(
    struct checkpoint_rollback_engine* eng,
    void* target_weights_buf,
    size_t length,
    off_t checkpoint_offset
) {
    if (!eng || eng->checkpoint_fd < 0 || !target_weights_buf) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) {
        io_uring_submit_and_wait(&eng->ring, 1);
        sqe = io_uring_get_sqe(&eng->ring);
        if (!sqe) return -2;
    }

    io_uring_prep_read(sqe, eng->checkpoint_fd, target_weights_buf, length, checkpoint_offset);
    io_uring_sqe_set_data(sqe, target_weights_buf);

    int ret = io_uring_submit(&eng->ring);
    if (ret > 0) {
        eng->in_flight++;
        eng->total_restored_bytes += length;
    }
    return ret;
}

extern "C" int reap_checkpoint_rollback_completions(struct checkpoint_rollback_engine* eng, int min_complete) {
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

extern "C" void close_checkpoint_rollback_engine(struct checkpoint_rollback_engine* eng) {
    if (!eng) return;
    reap_checkpoint_rollback_completions(eng, eng->in_flight);
    close(eng->checkpoint_fd);
    io_uring_queue_exit(&eng->ring);
    free(eng);
}

extern "C" int submit_checkpoint_rollback_write(struct checkpoint_rollback_engine* eng, const void* src_buf, size_t length, off_t file_offset) {
    if (!eng || !src_buf || length == 0) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) return -2;

    io_uring_prep_write(sqe, eng->checkpoint_fd, src_buf, length, file_offset);
    io_uring_sqe_set_data(sqe, (void*)src_buf);

    int ret = io_uring_submit(&eng->ring);
    if (ret > 0) {
        eng->in_flight++;
    }
    return ret;
}
