#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstring>
#include <cstdint>

// Direct io_uring Vectorized Truncation and Fallocate DMA Engine
// Bypasses synchronous filesystem stalls during KV cache eviction and model staging
// Uses IORING_OP_FALLOCATE to atomically allocate or punch holes in files asynchronously.

extern "C" {

struct FallocateRingContext {
    struct io_uring ring;
    int is_initialized;
};

void* init_fallocate_ring(uint32_t queue_depth) {
    auto* ctx = new FallocateRingContext();
    memset(ctx, 0, sizeof(FallocateRingContext));

    int ret = io_uring_queue_init(queue_depth, &ctx->ring, 0);
    if (ret < 0) {
        delete ctx;
        return nullptr;
    }

    ctx->is_initialized = 1;
    return ctx;
}

int fallocate_submit_punch_hole(
    void* handle,
    int fd,
    off_t offset,
    off_t len,
    uint64_t user_data
) {
    if (!handle) return -1;
    auto* ctx = static_cast<FallocateRingContext*>(handle);

    struct io_uring_sqe* sqe = io_uring_get_sqe(&ctx->ring);
    if (!sqe) return -2;

    // FALLOC_FL_PUNCH_HOLE | FALLOC_FL_KEEP_SIZE punches hole and frees blocks asynchronously
    io_uring_prep_fallocate(sqe, fd, FALLOC_FL_PUNCH_HOLE | FALLOC_FL_KEEP_SIZE, offset, len);
    sqe->user_data = user_data;

    return io_uring_submit(&ctx->ring);
}

int fallocate_harvest_completion(void* handle, uint64_t* user_data, int* res) {
    if (!handle) return -1;
    auto* ctx = static_cast<FallocateRingContext*>(handle);

    struct io_uring_cqe* cqe = nullptr;
    int ret = io_uring_peek_cqe(&ctx->ring, &cqe);
    if (ret < 0 || !cqe) return 0;

    if (user_data) *user_data = cqe->user_data;
    if (res) *res = cqe->res;

    io_uring_cqe_seen(&ctx->ring, cqe);
    return 1;
}

void close_fallocate_ring(void* handle) {
    if (!handle) return;
    auto* ctx = static_cast<FallocateRingContext*>(handle);
    if (ctx->is_initialized) {
        io_uring_queue_exit(&ctx->ring);
    }
    delete ctx;
}

}
