#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/uio.h>
#include <cstdlib>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cerrno>

extern "C" {

struct FixedBufferContext {
    struct io_uring ring;
    int fd;
    size_t buffer_size;
    uint8_t* raw_buffer;
    struct iovec iov;
    bool is_registered;
    bool initialized;
};

FixedBufferContext* iouring_fixed_buffer_init(const char* filepath, size_t buffer_size, unsigned int queue_depth) {
    if (!filepath || buffer_size == 0 || queue_depth == 0) return nullptr;

    FixedBufferContext* ctx = new FixedBufferContext();
    std::memset(ctx, 0, sizeof(FixedBufferContext));

    int ret = io_uring_queue_init(queue_depth, &ctx->ring, 0);
    if (ret < 0) {
        delete ctx;
        return nullptr;
    }

    ctx->fd = open(filepath, O_RDWR | O_CREAT | O_DIRECT, 0644);
    if (ctx->fd < 0) {
        // Fallback to non-O_DIRECT if filesystem does not support it
        ctx->fd = open(filepath, O_RDWR | O_CREAT, 0644);
        if (ctx->fd < 0) {
            io_uring_queue_exit(&ctx->ring);
            delete ctx;
            return nullptr;
        }
    }

    // Allocate page-aligned buffer for DMA zero-copy fixed buffer registration
    int alloc_ret = posix_memalign((void**)&ctx->raw_buffer, 4096, buffer_size);
    if (alloc_ret != 0 || !ctx->raw_buffer) {
        close(ctx->fd);
        io_uring_queue_exit(&ctx->ring);
        delete ctx;
        return nullptr;
    }

    ctx->buffer_size = buffer_size;
    ctx->iov.iov_base = ctx->raw_buffer;
    ctx->iov.iov_len = buffer_size;

    // Register fixed buffer with io_uring kernel ring
    ret = io_uring_register_buffers(&ctx->ring, &ctx->iov, 1);
    if (ret == 0) {
        ctx->is_registered = true;
    } else {
        ctx->is_registered = false;
    }

    ctx->initialized = true;
    return ctx;
}

int iouring_fixed_buffer_write(FixedBufferContext* ctx, const void* src_data, size_t size, off_t offset) {
    if (!ctx || !ctx->initialized || size > ctx->buffer_size) return -EINVAL;

    std::memcpy(ctx->raw_buffer, src_data, size);

    struct io_uring_sqe* sqe = io_uring_get_sqe(&ctx->ring);
    if (!sqe) return -EBUSY;

    if (ctx->is_registered) {
        // Use fixed buffer write opcode (IORING_OP_WRITE_FIXED)
        io_uring_prep_write_fixed(sqe, ctx->fd, ctx->raw_buffer, size, offset, 0);
    } else {
        io_uring_prep_write(sqe, ctx->fd, ctx->raw_buffer, size, offset);
    }

    int ret = io_uring_submit_and_wait(&ctx->ring, 1);
    if (ret < 0) return ret;

    struct io_uring_cqe* cqe;
    ret = io_uring_wait_cqe(&ctx->ring, &cqe);
    if (ret < 0) return ret;

    int res = cqe->res;
    io_uring_cqe_seen(&ctx->ring, cqe);
    return res;
}

int iouring_fixed_buffer_read(FixedBufferContext* ctx, void* dst_data, size_t size, off_t offset) {
    if (!ctx || !ctx->initialized || size > ctx->buffer_size) return -EINVAL;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&ctx->ring);
    if (!sqe) return -EBUSY;

    if (ctx->is_registered) {
        // Use fixed buffer read opcode (IORING_OP_READ_FIXED)
        io_uring_prep_read_fixed(sqe, ctx->fd, ctx->raw_buffer, size, offset, 0);
    } else {
        io_uring_prep_read(sqe, ctx->fd, ctx->raw_buffer, size, offset);
    }

    int ret = io_uring_submit_and_wait(&ctx->ring, 1);
    if (ret < 0) return ret;

    struct io_uring_cqe* cqe;
    ret = io_uring_wait_cqe(&ctx->ring, &cqe);
    if (ret < 0) return ret;

    int res = cqe->res;
    io_uring_cqe_seen(&ctx->ring, cqe);

    if (res > 0 && dst_data) {
        std::memcpy(dst_data, ctx->raw_buffer, res);
    }
    return res;
}

void iouring_fixed_buffer_close(FixedBufferContext* ctx) {
    if (!ctx) return;
    if (ctx->initialized) {
        if (ctx->is_registered) {
            io_uring_unregister_buffers(&ctx->ring);
        }
        if (ctx->fd >= 0) {
            close(ctx->fd);
        }
        if (ctx->raw_buffer) {
            free(ctx->raw_buffer);
        }
        io_uring_queue_exit(&ctx->ring);
    }
    delete ctx;
}

}
