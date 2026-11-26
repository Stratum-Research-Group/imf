#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstring>
#include <cstdint>

// Direct io_uring Splice DMA Engine
// Pipes data directly between file descriptors using IORING_OP_SPLICE
// Bypasses user-space buffers by transferring pages directly through kernel pipe buffers.

extern "C" {

struct SpliceRingContext {
    struct io_uring ring;
    int pipe_fd[2];
    int is_initialized;
};

void* init_splice_ring(uint32_t queue_depth) {
    auto* ctx = new SpliceRingContext();
    memset(ctx, 0, sizeof(SpliceRingContext));

    if (pipe(ctx->pipe_fd) < 0) {
        delete ctx;
        return nullptr;
    }

    int ret = io_uring_queue_init(queue_depth, &ctx->ring, 0);
    if (ret < 0) {
        close(ctx->pipe_fd[0]);
        close(ctx->pipe_fd[1]);
        delete ctx;
        return nullptr;
    }

    ctx->is_initialized = 1;
    return ctx;
}

int splice_submit_file_to_pipe(
    void* handle,
    int in_fd,
    off_t in_offset,
    size_t len,
    uint64_t user_data
) {
    if (!handle) return -1;
    auto* ctx = static_cast<SpliceRingContext*>(handle);

    struct io_uring_sqe* sqe = io_uring_get_sqe(&ctx->ring);
    if (!sqe) return -2;

    io_uring_prep_splice(
        sqe,
        in_fd,
        in_offset,
        ctx->pipe_fd[1],
        -1, // pipe target offset ignored
        len,
        SPLICE_F_MOVE | SPLICE_F_NONBLOCK
    );
    sqe->user_data = user_data;

    return io_uring_submit(&ctx->ring);
}

int splice_harvest_completion(void* handle, uint64_t* user_data, int* res) {
    if (!handle) return -1;
    auto* ctx = static_cast<SpliceRingContext*>(handle);

    struct io_uring_cqe* cqe = nullptr;
    int ret = io_uring_peek_cqe(&ctx->ring, &cqe);
    if (ret < 0 || !cqe) return 0;

    if (user_data) *user_data = cqe->user_data;
    if (res) *res = cqe->res;

    io_uring_cqe_seen(&ctx->ring, cqe);
    return 1;
}

void close_splice_ring(void* handle) {
    if (!handle) return;
    auto* ctx = static_cast<SpliceRingContext*>(handle);
    if (ctx->is_initialized) {
        io_uring_queue_exit(&ctx->ring);
        close(ctx->pipe_fd[0]);
        close(ctx->pipe_fd[1]);
    }
    delete ctx;
}

}
