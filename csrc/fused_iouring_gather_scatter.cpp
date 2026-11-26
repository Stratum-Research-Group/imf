#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/uio.h>
#include <cstdlib>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cerrno>
#include <vector>

extern "C" {

struct GatherScatterContext {
    struct io_uring ring;
    int fd;
    size_t max_vectors;
    size_t chunk_size;
    std::vector<struct iovec> iov_list;
    std::vector<uint8_t*> buffer_pool;
    bool initialized;
};

GatherScatterContext* iouring_gather_scatter_init(
    const char* filepath,
    size_t num_vectors,
    size_t chunk_size,
    unsigned int queue_depth
) {
    if (!filepath || num_vectors == 0 || chunk_size == 0 || queue_depth == 0) return nullptr;

    GatherScatterContext* ctx = new GatherScatterContext();
    ctx->max_vectors = num_vectors;
    ctx->chunk_size = chunk_size;
    ctx->iov_list.resize(num_vectors);
    ctx->buffer_pool.resize(num_vectors);

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

    for (size_t i = 0; i < num_vectors; ++i) {
        int alloc_ret = posix_memalign((void**)&ctx->buffer_pool[i], 4096, chunk_size);
        if (alloc_ret != 0 || !ctx->buffer_pool[i]) {
            for (size_t j = 0; j < i; ++j) free(ctx->buffer_pool[j]);
            close(ctx->fd);
            io_uring_queue_exit(&ctx->ring);
            delete ctx;
            return nullptr;
        }
        ctx->iov_list[i].iov_base = ctx->buffer_pool[i];
        ctx->iov_list[i].iov_len = chunk_size;
    }

    ctx->initialized = true;
    return ctx;
}

int iouring_gather_scatter_read(
    GatherScatterContext* ctx,
    void** dst_buffers,
    size_t num_vectors,
    off_t file_offset
) {
    if (!ctx || !ctx->initialized || num_vectors > ctx->max_vectors) return -EINVAL;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&ctx->ring);
    if (!sqe) return -EBUSY;

    // Vectorized readv using scatter-gather IOV array
    io_uring_prep_readv(sqe, ctx->fd, ctx->iov_list.data(), num_vectors, file_offset);

    int ret = io_uring_submit_and_wait(&ctx->ring, 1);
    if (ret < 0) return ret;

    struct io_uring_cqe* cqe = nullptr;
    ret = io_uring_wait_cqe(&ctx->ring, &cqe);
    if (ret < 0) return ret;

    int bytes_transferred = cqe->res;
    io_uring_cqe_seen(&ctx->ring, cqe);

    if (bytes_transferred > 0 && dst_buffers) {
        for (size_t i = 0; i < num_vectors; ++i) {
            if (dst_buffers[i]) {
                std::memcpy(dst_buffers[i], ctx->buffer_pool[i], ctx->chunk_size);
            }
        }
    }

    return bytes_transferred;
}

void iouring_gather_scatter_close(GatherScatterContext* ctx) {
    if (!ctx) return;
    if (ctx->initialized) {
        for (size_t i = 0; i < ctx->max_vectors; ++i) {
            if (ctx->buffer_pool[i]) free(ctx->buffer_pool[i]);
        }
        if (ctx->fd >= 0) close(ctx->fd);
        io_uring_queue_exit(&ctx->ring);
    }
    delete ctx;
}

}
