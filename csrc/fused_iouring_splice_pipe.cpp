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

#define SPLICE_QUEUE_DEPTH 64

struct splice_engine {
    struct io_uring ring;
    int in_flight;
    size_t total_spliced_bytes;
};

extern "C" struct splice_engine* init_splice_engine(int depth) {
    struct splice_engine* eng = (struct splice_engine*)malloc(sizeof(struct splice_engine));
    if (!eng) return NULL;
    memset(eng, 0, sizeof(*eng));

    int q_depth = (depth > 0) ? depth : SPLICE_QUEUE_DEPTH;
    struct io_uring_params params;
    memset(&params, 0, sizeof(params));

    if (io_uring_queue_init_params(q_depth, &eng->ring, &params) < 0) {
        free(eng);
        return NULL;
    }

    eng->in_flight = 0;
    eng->total_spliced_bytes = 0;
    return eng;
}

extern "C" int create_splice_pipe(int pipe_fds[2]) {
    if (!pipe_fds) return -1;
    return pipe2(pipe_fds, O_NONBLOCK | O_CLOEXEC);
}

extern "C" int submit_file_to_pipe_splice(
    struct splice_engine* eng,
    int fd_in,
    off_t off_in,
    int pipe_out,
    size_t nbytes
) {
    if (!eng || fd_in < 0 || pipe_out < 0 || nbytes == 0) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) {
        io_uring_submit(&eng->ring);
        sqe = io_uring_get_sqe(&eng->ring);
        if (!sqe) return -EBUSY;
    }

    // Splice from file at off_in to pipe write-end (pipe off is -1)
    io_uring_prep_splice(sqe, fd_in, off_in, pipe_out, -1, nbytes, SPLICE_F_NONBLOCK);
    io_uring_sqe_set_data(sqe, (void*)(uintptr_t)1);
    eng->in_flight++;

    return io_uring_submit(&eng->ring);
}

extern "C" int submit_pipe_to_file_splice(
    struct splice_engine* eng,
    int pipe_in,
    int fd_out,
    off_t off_out,
    size_t nbytes
) {
    if (!eng || pipe_in < 0 || fd_out < 0 || nbytes == 0) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) {
        io_uring_submit(&eng->ring);
        sqe = io_uring_get_sqe(&eng->ring);
        if (!sqe) return -EBUSY;
    }

    // Splice from pipe read-end (pipe off is -1) to file at off_out
    io_uring_prep_splice(sqe, pipe_in, -1, fd_out, off_out, nbytes, SPLICE_F_NONBLOCK);
    io_uring_sqe_set_data(sqe, (void*)(uintptr_t)2);
    eng->in_flight++;

    return io_uring_submit(&eng->ring);
}

extern "C" int wait_splice_completions(struct splice_engine* eng, int min_complete) {
    if (!eng) return -1;
    int completed = 0;
    struct io_uring_cqe* cqe = NULL;

    while (eng->in_flight > 0 && completed < min_complete) {
        int ret = io_uring_wait_cqe(&eng->ring, &cqe);
        if (ret < 0) {
            break;
        }
        if (cqe->res > 0) {
            eng->total_spliced_bytes += cqe->res;
        }
        io_uring_cqe_seen(&eng->ring, cqe);
        eng->in_flight--;
        completed++;
    }
    return completed;
}

extern "C" void close_splice_engine(struct splice_engine* eng) {
    if (!eng) return;
    if (eng->in_flight > 0) {
        wait_splice_completions(eng, eng->in_flight);
    }
    io_uring_queue_exit(&eng->ring);
    free(eng);
}
