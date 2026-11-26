#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstdlib>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cerrno>

extern "C" {

struct FallocateContext {
    struct io_uring ring;
    int fd;
    bool initialized;
};

FallocateContext* iouring_fallocate_init(const char* filepath, unsigned int queue_depth) {
    if (!filepath || queue_depth == 0) return nullptr;

    FallocateContext* ctx = new FallocateContext();
    std::memset(ctx, 0, sizeof(FallocateContext));

    int ret = io_uring_queue_init(queue_depth, &ctx->ring, 0);
    if (ret < 0) {
        delete ctx;
        return nullptr;
    }

    ctx->fd = open(filepath, O_RDWR | O_CREAT, 0644);
    if (ctx->fd < 0) {
        io_uring_queue_exit(&ctx->ring);
        delete ctx;
        return nullptr;
    }

    ctx->initialized = true;
    return ctx;
}

// Asynchronously punches a hole in the file (deallocating disk space)
int iouring_fallocate_punch_hole(FallocateContext* ctx, off_t offset, off_t len) {
    if (!ctx || !ctx->initialized || len <= 0) return -EINVAL;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&ctx->ring);
    if (!sqe) return -EBUSY;

    // FALLOC_FL_PUNCH_HOLE | FALLOC_FL_KEEP_SIZE = 0x02 | 0x01 = 0x03
    int mode = FALLOC_FL_PUNCH_HOLE | FALLOC_FL_KEEP_SIZE;
    io_uring_prep_fallocate(sqe, ctx->fd, mode, offset, len);

    int ret = io_uring_submit_and_wait(&ctx->ring, 1);
    if (ret < 0) return ret;

    struct io_uring_cqe* cqe = nullptr;
    ret = io_uring_wait_cqe(&ctx->ring, &cqe);
    if (ret < 0) return ret;

    int res = cqe->res;
    io_uring_cqe_seen(&ctx->ring, cqe);
    return res;
}

void iouring_fallocate_close(FallocateContext* ctx) {
    if (!ctx) return;
    if (ctx->initialized) {
        if (ctx->fd >= 0) close(ctx->fd);
        io_uring_queue_exit(&ctx->ring);
    }
    delete ctx;
}

}
