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

struct PolledCqeContext {
    struct io_uring ring;
    int fd;
    size_t buffer_size;
    uint8_t* raw_buffer;
    bool is_registered;
    bool initialized;
};

PolledCqeContext* iouring_cq_polling_init(const char* filepath, size_t buffer_size, unsigned int queue_depth) {
    if (!filepath || buffer_size == 0 || queue_depth == 0) return nullptr;

    PolledCqeContext* ctx = new PolledCqeContext();
    std::memset(ctx, 0, sizeof(PolledCqeContext));

    // Initialize io_uring ring with IOPOLL flag for busy-polling completions
    struct io_uring_params params;
    std::memset(&params, 0, sizeof(params));
    params.flags = IORING_SETUP_IOPOLL;

    int ret = io_uring_queue_init_params(queue_depth, &ctx->ring, &params);
    if (ret < 0) {
        // Fallback to standard queue if kernel/filesystem does not permit IOPOLL
        ret = io_uring_queue_init(queue_depth, &ctx->ring, 0);
        if (ret < 0) {
            delete ctx;
            return nullptr;
        }
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

    ctx->buffer_size = buffer_size;
    ctx->initialized = true;
    return ctx;
}

int iouring_cq_poll_read(PolledCqeContext* ctx, void* dst_data, size_t size, off_t offset) {
    if (!ctx || !ctx->initialized || size > ctx->buffer_size) return -EINVAL;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&ctx->ring);
    if (!sqe) return -EBUSY;

    io_uring_prep_read(sqe, ctx->fd, ctx->raw_buffer, size, offset);
    int ret = io_uring_submit(&ctx->ring);
    if (ret < 0) return ret;

    // Busy poll the completion queue directly without blocking sleep
    struct io_uring_cqe* cqe = nullptr;
    while (true) {
        ret = io_uring_peek_cqe(&ctx->ring, &cqe);
        if (ret == 0 && cqe != nullptr) {
            break;
        }
        // Poll kernel ring
        io_uring_get_events(&ctx->ring);
    }

    int res = cqe->res;
    io_uring_cqe_seen(&ctx->ring, cqe);

    if (res > 0 && dst_data) {
        std::memcpy(dst_data, ctx->raw_buffer, res);
    }
    return res;
}

void iouring_cq_polling_close(PolledCqeContext* ctx) {
    if (!ctx) return;
    if (ctx->initialized) {
        if (ctx->fd >= 0) close(ctx->fd);
        if (ctx->raw_buffer) free(ctx->raw_buffer);
        io_uring_queue_exit(&ctx->ring);
    }
    delete ctx;
}

}
