#include <liburing.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <cstdlib>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cerrno>

extern "C" {

struct ZeroCopySocketContext {
    struct io_uring ring;
    int sock_fd;
    size_t buffer_size;
    uint8_t* raw_buffer;
    bool is_registered;
    bool initialized;
};

ZeroCopySocketContext* iouring_zerocopy_socket_init(
    int sock_fd,
    size_t buffer_size,
    unsigned int queue_depth
) {
    if (sock_fd < 0 || buffer_size == 0 || queue_depth == 0) return nullptr;

    ZeroCopySocketContext* ctx = new ZeroCopySocketContext();
    std::memset(ctx, 0, sizeof(ZeroCopySocketContext));
    ctx->sock_fd = sock_fd;
    ctx->buffer_size = buffer_size;

    int ret = io_uring_queue_init(queue_depth, &ctx->ring, 0);
    if (ret < 0) {
        delete ctx;
        return nullptr;
    }

    int alloc_ret = posix_memalign((void**)&ctx->raw_buffer, 4096, buffer_size);
    if (alloc_ret != 0 || !ctx->raw_buffer) {
        io_uring_queue_exit(&ctx->ring);
        delete ctx;
        return nullptr;
    }

    ctx->initialized = true;
    return ctx;
}

int iouring_zerocopy_socket_send(
    ZeroCopySocketContext* ctx,
    const void* src_data,
    size_t size
) {
    if (!ctx || !ctx->initialized || size > ctx->buffer_size) return -EINVAL;

    std::memcpy(ctx->raw_buffer, src_data, size);

    struct io_uring_sqe* sqe = io_uring_get_sqe(&ctx->ring);
    if (!sqe) return -EBUSY;

    // Use sendzc if supported by kernel, otherwise standard send
    io_uring_prep_send_zc(sqe, ctx->sock_fd, ctx->raw_buffer, size, 0, 0);

    int ret = io_uring_submit_and_wait(&ctx->ring, 1);
    if (ret < 0) return ret;

    struct io_uring_cqe* cqe = nullptr;
    ret = io_uring_wait_cqe(&ctx->ring, &cqe);
    if (ret < 0) return ret;

    int res = cqe->res;
    io_uring_cqe_seen(&ctx->ring, cqe);
    return res;
}

int iouring_zerocopy_socket_recv(
    ZeroCopySocketContext* ctx,
    void* dst_data,
    size_t size
) {
    if (!ctx || !ctx->initialized || size > ctx->buffer_size) return -EINVAL;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&ctx->ring);
    if (!sqe) return -EBUSY;

    io_uring_prep_recv(sqe, ctx->sock_fd, ctx->raw_buffer, size, 0);

    int ret = io_uring_submit_and_wait(&ctx->ring, 1);
    if (ret < 0) return ret;

    struct io_uring_cqe* cqe = nullptr;
    ret = io_uring_wait_cqe(&ctx->ring, &cqe);
    if (ret < 0) return ret;

    int res = cqe->res;
    io_uring_cqe_seen(&ctx->ring, cqe);

    if (res > 0 && dst_data) {
        std::memcpy(dst_data, ctx->raw_buffer, res);
    }
    return res;
}

void iouring_zerocopy_socket_close(ZeroCopySocketContext* ctx) {
    if (!ctx) return;
    if (ctx->initialized) {
        if (ctx->raw_buffer) free(ctx->raw_buffer);
        io_uring_queue_exit(&ctx->ring);
    }
    delete ctx;
}

}
