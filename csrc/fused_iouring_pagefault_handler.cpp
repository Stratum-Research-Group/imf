#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <linux/userfaultfd.h>
#include <cstdlib>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cerrno>

extern "C" {

struct PageFaultHandlerContext {
    struct io_uring ring;
    int uffd;
    int storage_fd;
    size_t page_size;
    uint8_t* staging_buffer;
    bool initialized;
};

PageFaultHandlerContext* iouring_pagefault_handler_init(
    const char* storage_path,
    size_t page_size,
    unsigned int queue_depth
) {
    if (!storage_path || page_size == 0 || queue_depth == 0) return nullptr;

    PageFaultHandlerContext* ctx = new PageFaultHandlerContext();
    std::memset(ctx, 0, sizeof(PageFaultHandlerContext));
    ctx->page_size = page_size;

    int ret = io_uring_queue_init(queue_depth, &ctx->ring, 0);
    if (ret < 0) {
        delete ctx;
        return nullptr;
    }

    ctx->storage_fd = open(storage_path, O_RDONLY | O_DIRECT, 0644);
    if (ctx->storage_fd < 0) {
        ctx->storage_fd = open(storage_path, O_RDONLY, 0644);
        if (ctx->storage_fd < 0) {
            io_uring_queue_exit(&ctx->ring);
            delete ctx;
            return nullptr;
        }
    }

    // Initialize userfaultfd
    ctx->uffd = syscall(__NR_userfaultfd, O_CLOEXEC | O_NONBLOCK);
    if (ctx->uffd < 0) {
        // Fallback gracefully if kernel requires CAP_SYS_PTRACE
        ctx->uffd = -1;
    }

    int alloc_ret = posix_memalign((void**)&ctx->staging_buffer, 4096, page_size);
    if (alloc_ret != 0 || !ctx->staging_buffer) {
        if (ctx->uffd >= 0) close(ctx->uffd);
        close(ctx->storage_fd);
        io_uring_queue_exit(&ctx->ring);
        delete ctx;
        return nullptr;
    }

    ctx->initialized = true;
    return ctx;
}

// Asynchronously streams faulting parameter page from NVMe into fault address
int iouring_pagefault_resolve_page(
    PageFaultHandlerContext* ctx,
    void* fault_addr,
    off_t storage_offset
) {
    if (!ctx || !ctx->initialized || !fault_addr) return -EINVAL;

    // Read missing page directly into staging buffer via io_uring
    struct io_uring_sqe* sqe = io_uring_get_sqe(&ctx->ring);
    if (!sqe) return -EBUSY;

    io_uring_prep_read(sqe, ctx->storage_fd, ctx->staging_buffer, ctx->page_size, storage_offset);
    int ret = io_uring_submit_and_wait(&ctx->ring, 1);
    if (ret < 0) return ret;

    struct io_uring_cqe* cqe = nullptr;
    ret = io_uring_wait_cqe(&ctx->ring, &cqe);
    if (ret < 0) return ret;

    int bytes_read = cqe->res;
    io_uring_cqe_seen(&ctx->ring, cqe);
    if (bytes_read < 0) return bytes_read;

    // Resolve fault via UFFDIO_COPY if uffd is active, otherwise direct memcpy
    if (ctx->uffd >= 0) {
        struct uffdio_copy copy_op;
        copy_op.dst = (unsigned long)fault_addr;
        copy_op.src = (unsigned long)ctx->staging_buffer;
        copy_op.len = ctx->page_size;
        copy_op.mode = 0;
        copy_op.copy = 0;
        if (ioctl(ctx->uffd, UFFDIO_COPY, &copy_op) < 0) {
            std::memcpy(fault_addr, ctx->staging_buffer, ctx->page_size);
        }
    } else {
        std::memcpy(fault_addr, ctx->staging_buffer, ctx->page_size);
    }

    return bytes_read;
}

void iouring_pagefault_handler_close(PageFaultHandlerContext* ctx) {
    if (!ctx) return;
    if (ctx->initialized) {
        if (ctx->uffd >= 0) close(ctx->uffd);
        if (ctx->storage_fd >= 0) close(ctx->storage_fd);
        if (ctx->staging_buffer) free(ctx->staging_buffer);
        io_uring_queue_exit(&ctx->ring);
    }
    delete ctx;
}

}
