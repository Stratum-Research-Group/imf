// csrc/fused_iouring_direct_reg_engine.cpp
// Linux 6.18 Kernel-Bypass: io_uring Ring-Mapped Direct Descriptors & Registered Buffers
// Bypasses file descriptor table lookups and kernel page pin translations via
// io_uring_register_files and io_uring_register_buffers (read_fixed / write_fixed).

#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/uio.h>
#include <sys/types.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>

#define DIRECT_REG_QUEUE_DEPTH 64

struct direct_reg_engine {
    struct io_uring ring;
    struct iovec reg_iov;
    void* buffer_base;
    size_t buffer_len;
    int num_registered_files;
    int in_flight;
};

extern "C" struct direct_reg_engine* init_direct_reg_engine(
    int depth,
    void* buffer,
    size_t buf_len,
    int* fds,
    int num_fds
) {
    if (!buffer || buf_len == 0 || !fds || num_fds <= 0) return NULL;

    struct direct_reg_engine* eng = (struct direct_reg_engine*)malloc(sizeof(struct direct_reg_engine));
    if (!eng) return NULL;
    memset(eng, 0, sizeof(*eng));

    int q_depth = (depth > 0) ? depth : DIRECT_REG_QUEUE_DEPTH;
    struct io_uring_params params;
    memset(&params, 0, sizeof(params));

    if (io_uring_queue_init_params(q_depth, &eng->ring, &params) < 0) {
        free(eng);
        return NULL;
    }

    // Register fixed buffer
    eng->reg_iov.iov_base = buffer;
    eng->reg_iov.iov_len = buf_len;
    eng->buffer_base = buffer;
    eng->buffer_len = buf_len;

    if (io_uring_register_buffers(&eng->ring, &eng->reg_iov, 1) < 0) {
        io_uring_queue_exit(&eng->ring);
        free(eng);
        return NULL;
    }

    // Register fixed files
    if (io_uring_register_files(&eng->ring, fds, num_fds) < 0) {
        io_uring_unregister_buffers(&eng->ring);
        io_uring_queue_exit(&eng->ring);
        free(eng);
        return NULL;
    }

    eng->num_registered_files = num_fds;
    eng->in_flight = 0;
    return eng;
}

extern "C" int submit_fixed_write(
    struct direct_reg_engine* eng,
    int file_idx,
    size_t buf_offset,
    size_t nbytes,
    off_t file_offset
) {
    if (!eng || file_idx < 0 || file_idx >= eng->num_registered_files) return -1;
    if (buf_offset + nbytes > eng->buffer_len) return -EINVAL;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) {
        io_uring_submit(&eng->ring);
        sqe = io_uring_get_sqe(&eng->ring);
        if (!sqe) return -EBUSY;
    }

    char* ptr = (char*)eng->buffer_base + buf_offset;
    io_uring_prep_write_fixed(sqe, file_idx, ptr, nbytes, file_offset, 0);
    sqe->flags |= IOSQE_FIXED_FILE;

    int ret = io_uring_submit(&eng->ring);
    if (ret < 0) return ret;

    eng->in_flight++;
    return 0;
}

extern "C" int submit_fixed_read(
    struct direct_reg_engine* eng,
    int file_idx,
    size_t buf_offset,
    size_t nbytes,
    off_t file_offset
) {
    if (!eng || file_idx < 0 || file_idx >= eng->num_registered_files) return -1;
    if (buf_offset + nbytes > eng->buffer_len) return -EINVAL;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) {
        io_uring_submit(&eng->ring);
        sqe = io_uring_get_sqe(&eng->ring);
        if (!sqe) return -EBUSY;
    }

    char* ptr = (char*)eng->buffer_base + buf_offset;
    io_uring_prep_read_fixed(sqe, file_idx, ptr, nbytes, file_offset, 0);
    sqe->flags |= IOSQE_FIXED_FILE;

    int ret = io_uring_submit(&eng->ring);
    if (ret < 0) return ret;

    eng->in_flight++;
    return 0;
}

extern "C" int wait_direct_completions(struct direct_reg_engine* eng, int min_complete) {
    if (!eng || min_complete <= 0) return -1;

    int completed = 0;
    while (completed < min_complete && eng->in_flight > 0) {
        struct io_uring_cqe* cqe = NULL;
        int ret = io_uring_wait_cqe(&eng->ring, &cqe);
        if (ret < 0) return ret;

        if (cqe->res < 0) {
            io_uring_cqe_seen(&eng->ring, cqe);
            return cqe->res;
        }

        io_uring_cqe_seen(&eng->ring, cqe);
        completed++;
        eng->in_flight--;
    }
    return completed;
}

extern "C" void close_direct_reg_engine(struct direct_reg_engine* eng) {
    if (!eng) return;
    io_uring_unregister_files(&eng->ring);
    io_uring_unregister_buffers(&eng->ring);
    io_uring_queue_exit(&eng->ring);
    free(eng);
}
