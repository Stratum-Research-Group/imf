#define _GNU_SOURCE
#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#define RING_DEPTH 64

struct zero_copy_splice_ring {
    struct io_uring ring;
    int pipe_in;
    int pipe_out;
    int in_flight;
};

extern "C" struct zero_copy_splice_ring* init_zero_copy_splice_ring(int depth) {
    struct zero_copy_splice_ring* zc = (struct zero_copy_splice_ring*)malloc(sizeof(struct zero_copy_splice_ring));
    if (!zc) return NULL;
    memset(zc, 0, sizeof(*zc));

    int pipefd[2];
    if (pipe2(pipefd, O_NONBLOCK | O_DIRECT) < 0) {
        if (pipe(pipefd) < 0) {
            free(zc);
            return NULL;
        }
    }
    zc->pipe_in = pipefd[1];
    zc->pipe_out = pipefd[0];

    int q_depth = (depth > 0) ? depth : RING_DEPTH;
    struct io_uring_params params;
    memset(&params, 0, sizeof(params));

    if (io_uring_queue_init_params(q_depth, &zc->ring, &params) < 0) {
        close(zc->pipe_in);
        close(zc->pipe_out);
        free(zc);
        return NULL;
    }

    zc->in_flight = 0;
    return zc;
}

extern "C" int submit_spliced_transfer(
    struct zero_copy_splice_ring* zc,
    int fd_src,
    off_t off_src,
    int fd_dst,
    off_t off_dst,
    size_t length
) {
    if (!zc || fd_src < 0 || fd_dst < 0) return -1;

    // Stage 1: Splice fd_src -> pipe_in
    struct io_uring_sqe* sqe1 = io_uring_get_sqe(&zc->ring);
    if (!sqe1) {
        io_uring_submit_and_wait(&zc->ring, 1);
        sqe1 = io_uring_get_sqe(&zc->ring);
        if (!sqe1) return -2;
    }
    io_uring_prep_splice(sqe1, fd_src, off_src, zc->pipe_in, -1, length, SPLICE_F_MOVE);
    sqe1->flags |= IOSQE_IO_LINK; // Enforce sequential execution before next stage

    // Stage 2: Splice pipe_out -> fd_dst
    struct io_uring_sqe* sqe2 = io_uring_get_sqe(&zc->ring);
    if (!sqe2) {
        io_uring_submit_and_wait(&zc->ring, 1);
        sqe2 = io_uring_get_sqe(&zc->ring);
        if (!sqe2) return -3;
    }
    io_uring_prep_splice(sqe2, zc->pipe_out, -1, fd_dst, off_dst, length, SPLICE_F_MOVE);

    int ret = io_uring_submit(&zc->ring);
    if (ret > 0) {
        zc->in_flight += 2;
    }
    return ret;
}

extern "C" int reap_spliced_completions(struct zero_copy_splice_ring* zc, int min_complete) {
    if (!zc) return -1;
    int reaped = 0;
    struct io_uring_cqe* cqe;

    while (reaped < min_complete && zc->in_flight > 0) {
        if (io_uring_wait_cqe(&zc->ring, &cqe) == 0) {
            io_uring_cqe_seen(&zc->ring, cqe);
            zc->in_flight--;
            reaped++;
        } else {
            break;
        }
    }

    while (zc->in_flight > 0) {
        if (io_uring_peek_cqe(&zc->ring, &cqe) == 0 && cqe) {
            io_uring_cqe_seen(&zc->ring, cqe);
            zc->in_flight--;
            reaped++;
        } else {
            break;
        }
    }
    return reaped;
}

extern "C" void close_zero_copy_splice_ring(struct zero_copy_splice_ring* zc) {
    if (!zc) return;
    reap_spliced_completions(zc, zc->in_flight);
    close(zc->pipe_in);
    close(zc->pipe_out);
    io_uring_queue_exit(&zc->ring);
    free(zc);
}
