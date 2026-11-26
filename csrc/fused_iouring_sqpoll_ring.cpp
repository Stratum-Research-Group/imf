#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <vector>
#include <stdexcept>
#include <cstring>
#include <cstdint>

// Direct SQPOLL Threaded Ring: A kernel thread continuously polls the submission
// queue (IORING_SETUP_SQPOLL), eliminating the need for application enter system calls (io_uring_enter).
// Ideal for continuous, ultra-low latency parameter streaming from NVMe storage.

extern "C" {

struct SQPollRingContext {
    struct io_uring ring;
    int is_initialized;
};

void* init_sqpoll_ring(uint32_t queue_depth, uint32_t idle_ms) {
    auto* ctx = new SQPollRingContext();
    memset(ctx, 0, sizeof(SQPollRingContext));

    struct io_uring_params params;
    memset(&params, 0, sizeof(params));
    params.flags = IORING_SETUP_SQPOLL;
    params.sq_thread_idle = idle_ms;

    int ret = io_uring_queue_init_params(queue_depth, &ctx->ring, &params);
    if (ret < 0) {
        // If SQPOLL lacks privileged CAP_SYS_NICE or kernel limit, fall back gracefully to standard ring
        ret = io_uring_queue_init(queue_depth, &ctx->ring, 0);
        if (ret < 0) {
            delete ctx;
            return nullptr;
        }
    }
    ctx->is_initialized = 1;
    return ctx;
}

int sqpoll_submit_read(
    void* handle,
    int fd,
    void* buf,
    size_t count,
    off_t offset,
    uint64_t user_data
) {
    if (!handle) return -1;
    auto* ctx = static_cast<SQPollRingContext*>(handle);

    struct io_uring_sqe* sqe = io_uring_get_sqe(&ctx->ring);
    if (!sqe) return -2;

    io_uring_prep_read(sqe, fd, buf, count, offset);
    sqe->user_data = user_data;

    // With SQPOLL active, kernel thread picks it up automatically.
    // Call submit without waiting for immediate ring kick.
    io_uring_submit(&ctx->ring);
    return 0;
}

int sqpoll_harvest_completion(void* handle, uint64_t* user_data, int* res) {
    if (!handle) return -1;
    auto* ctx = static_cast<SQPollRingContext*>(handle);

    struct io_uring_cqe* cqe = nullptr;
    int ret = io_uring_peek_cqe(&ctx->ring, &cqe);
    if (ret < 0 || !cqe) {
        return 0; // No completion available
    }

    if (user_data) *user_data = cqe->user_data;
    if (res) *res = cqe->res;

    io_uring_cqe_seen(&ctx->ring, cqe);
    return 1;
}

void close_sqpoll_ring(void* handle) {
    if (!handle) return;
    auto* ctx = static_cast<SQPollRingContext*>(handle);
    if (ctx->is_initialized) {
        io_uring_queue_exit(&ctx->ring);
    }
    delete ctx;
}

}
