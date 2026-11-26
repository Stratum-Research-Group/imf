#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstdlib>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cerrno>

extern "C" {

struct DirectBarrierContext {
    struct io_uring ring;
    int fd;
    size_t buffer_size;
    uint8_t* raw_buffer;
    bool initialized;
};

DirectBarrierContext* iouring_direct_barrier_init(
    const char* filepath,
    size_t buffer_size,
    unsigned int queue_depth
) {
    if (!filepath || buffer_size == 0 || queue_depth == 0) return nullptr;

    DirectBarrierContext* ctx = new DirectBarrierContext();
    std::memset(ctx, 0, sizeof(DirectBarrierContext));
    ctx->buffer_size = buffer_size;

    int ret = io_uring_queue_init(queue_depth, &ctx->ring, 0);
    if (ret < 0) {
        delete ctx;
        return nullptr;
    }

    ctx->fd = open(filepath, O_RDWR | O_CREAT | O_DIRECT, 0644);
    if (ctx->fd < 0) {
        ctx->fd = open(filepath, O_RDWR | O_CREAT, 0644);
        if (ctx->fd < 0) {
            io_uring_queue_exit(&ctx->ring);
            delete ctx;
            return nullptr;
        }
    }

    int alloc_ret = posix_memalign((void**)&ctx->raw_buffer, 4096, buffer_size);
    if (alloc_ret != 0 || !ctx->raw_buffer) {
        close(ctx->fd);
        io_uring_queue_exit(&ctx->ring);
        delete ctx;
        return nullptr;
    }

    ctx->initialized = true;
    return ctx;
}

// Executes an asynchronous write followed by a hard drained barrier (IOSQE_IO_DRAIN)
int iouring_direct_barrier_write_sync(
    DirectBarrierContext* ctx,
    const void* src_data,
    size_t size,
    off_t offset
) {
    if (!ctx || !ctx->initialized || size > ctx->buffer_size) return -EINVAL;

    std::memcpy(ctx->raw_buffer, src_data, size);

    // SQE 1: Asynchronous write
    struct io_uring_sqe* sqe1 = io_uring_get_sqe(&ctx->ring);
    if (!sqe1) return -EBUSY;
    io_uring_prep_write(sqe1, ctx->fd, ctx->raw_buffer, size, offset);
    sqe1->flags |= IOSQE_IO_LINK; // Hard link to barrier

    // SQE 2: DRAIN barrier guaranteeing persistence and ordering
    struct io_uring_sqe* sqe2 = io_uring_get_sqe(&ctx->ring);
    if (!sqe2) return -EBUSY;
    io_uring_prep_fsync(sqe2, ctx->fd, IORING_FSYNC_DATASYNC);
    sqe2->flags |= IOSQE_IO_DRAIN;

    int ret = io_uring_submit_and_wait(&ctx->ring, 2);
    if (ret < 0) return ret;

    struct io_uring_cqe* cqe = nullptr;
    int res = 0;
    for (int i = 0; i < 2; ++i) {
        ret = io_uring_wait_cqe(&ctx->ring, &cqe);
        if (ret == 0 && cqe) {
            if (cqe->res < 0) res = cqe->res;
            io_uring_cqe_seen(&ctx->ring, cqe);
        }
    }
    return res;
}

void iouring_direct_barrier_close(DirectBarrierContext* ctx) {
    if (!ctx) return;
    if (ctx->initialized) {
        if (ctx->fd >= 0) close(ctx->fd);
        if (ctx->raw_buffer) free(ctx->raw_buffer);
        io_uring_queue_exit(&ctx->ring);
    }
    delete ctx;
}

}
