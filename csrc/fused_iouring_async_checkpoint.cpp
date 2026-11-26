#define _GNU_SOURCE
#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#define QUEUE_DEPTH 64
#define CHUNK_ALIGN 4096

struct async_checkpoint_context {
    struct io_uring ring;
    int fd;
    int in_flight;
    size_t total_written;
};

extern "C" struct async_checkpoint_context* init_async_checkpoint(const char* filepath, int queue_depth) {
    struct async_checkpoint_context* ctx = (struct async_checkpoint_context*)malloc(sizeof(struct async_checkpoint_context));
    if (!ctx) return NULL;

    memset(ctx, 0, sizeof(*ctx));

    // Open with O_DIRECT and O_CREAT
    ctx->fd = open(filepath, O_WRONLY | O_CREAT | O_TRUNC | O_DIRECT, 0644);
    if (ctx->fd < 0) {
        // Fallback without O_DIRECT if direct I/O is not supported on target filesystem
        ctx->fd = open(filepath, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (ctx->fd < 0) {
            free(ctx);
            return NULL;
        }
    }

    int depth = (queue_depth > 0) ? queue_depth : QUEUE_DEPTH;
    struct io_uring_params params;
    memset(&params, 0, sizeof(params));

    if (io_uring_queue_init_params(depth, &ctx->ring, &params) < 0) {
        close(ctx->fd);
        free(ctx);
        return NULL;
    }

    ctx->in_flight = 0;
    ctx->total_written = 0;
    return ctx;
}

extern "C" int submit_async_checkpoint_write(
    struct async_checkpoint_context* ctx,
    const void* buffer,
    size_t length,
    off_t offset
) {
    if (!ctx || ctx->fd < 0 || !buffer) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&ctx->ring);
    if (!sqe) {
        // Ring full, submit and wait for at least one completion
        io_uring_submit_and_wait(&ctx->ring, 1);
        sqe = io_uring_get_sqe(&ctx->ring);
        if (!sqe) return -2;
    }

    io_uring_prep_write(sqe, ctx->fd, buffer, length, offset);
    io_uring_sqe_set_data(sqe, (void*)(uintptr_t)offset);

    int ret = io_uring_submit(&ctx->ring);
    if (ret > 0) {
        ctx->in_flight++;
        ctx->total_written += length;
    }
    return ret;
}

extern "C" int reap_async_checkpoint_completions(struct async_checkpoint_context* ctx, int min_complete) {
    if (!ctx) return -1;

    int reaped = 0;
    struct io_uring_cqe* cqe;

    while (reaped < min_complete && ctx->in_flight > 0) {
        int ret = io_uring_wait_cqe(&ctx->ring, &cqe);
        if (ret < 0) break;

        io_uring_cqe_seen(&ctx->ring, cqe);
        ctx->in_flight--;
        reaped++;
    }

    // Reap any additional pending cqes non-blockingly
    while (ctx->in_flight > 0) {
        int ret = io_uring_peek_cqe(&ctx->ring, &cqe);
        if (ret < 0 || !cqe) break;

        io_uring_cqe_seen(&ctx->ring, cqe);
        ctx->in_flight--;
        reaped++;
    }

    return reaped;
}

extern "C" void close_async_checkpoint(struct async_checkpoint_context* ctx) {
    if (!ctx) return;

    // Reap all in flight operations before closing
    while (ctx->in_flight > 0) {
        struct io_uring_cqe* cqe;
        if (io_uring_wait_cqe(&ctx->ring, &cqe) == 0) {
            io_uring_cqe_seen(&ctx->ring, cqe);
            ctx->in_flight--;
        } else {
            break;
        }
    }

    // Flush and fsync
    fsync(ctx->fd);
    close(ctx->fd);
    io_uring_queue_exit(&ctx->ring);
    free(ctx);
}
