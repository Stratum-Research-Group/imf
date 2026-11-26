#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <cstring>
#include <cstdint>

// Direct io_uring Asynchronous Sync File Range DMA Engine
// Flushes fine-grained byte ranges to persistent NVMe blocks asynchronously via IORING_OP_SYNC_FILE_RANGE
// Completely avoids blocking the GPU execution stream with full-file fsync barriers.

static inline off_t len_or_zero(off_t n) { return n > 0 ? n : 0; }

extern "C" {

struct SyncRangeRingContext {
    struct io_uring ring;
    int is_initialized;
};

void* init_sync_range_ring(uint32_t queue_depth) {
    auto* ctx = new SyncRangeRingContext();
    memset(ctx, 0, sizeof(SyncRangeRingContext));

    int ret = io_uring_queue_init(queue_depth, &ctx->ring, 0);
    if (ret < 0) {
        delete ctx;
        return nullptr;
    }

    ctx->is_initialized = 1;
    return ctx;
}

int sync_range_submit(
    void* handle,
    int fd,
    off_t offset,
    off_t nbytes,
    unsigned int flags,
    uint64_t user_data
) {
    if (!handle) return -1;
    auto* ctx = static_cast<SyncRangeRingContext*>(handle);

    struct io_uring_sqe* sqe = io_uring_get_sqe(&ctx->ring);
    if (!sqe) return -2;

    io_uring_prep_sync_file_range(sqe, fd, len_or_zero(nbytes), offset, flags);
    sqe->user_data = user_data;

    return io_uring_submit(&ctx->ring);
}

int sync_range_harvest_completion(void* handle, uint64_t* user_data, int* res) {
    if (!handle) return -1;
    auto* ctx = static_cast<SyncRangeRingContext*>(handle);

    struct io_uring_cqe* cqe = nullptr;
    int ret = io_uring_peek_cqe(&ctx->ring, &cqe);
    if (ret < 0 || !cqe) return 0;

    if (user_data) *user_data = cqe->user_data;
    if (res) *res = cqe->res;

    io_uring_cqe_seen(&ctx->ring, cqe);
    return 1;
}

void close_sync_range_ring(void* handle) {
    if (!handle) return;
    auto* ctx = static_cast<SyncRangeRingContext*>(handle);
    if (ctx->is_initialized) {
        io_uring_queue_exit(&ctx->ring);
    }
    delete ctx;
}

}
