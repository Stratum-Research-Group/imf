// csrc/fused_iouring_registered_pipesplice.cpp
// ========================================================
// Production Linux 6.18 io_uring Kernel Memory Registration & Zero-Copy Pipe Splicing Ring Engine
// Combines io_uring buffer registration with asynchronous pipe splice operations
// for high-throughput zero-syscall IPC between daemon processes and CUDA host buffers.

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/uio.h>
#include <liburing.h>

extern "C" {

struct IOUringRegisteredPipeSpliceEngine {
    struct io_uring ring;
    int is_buffers_registered;
    int is_initialized;
    uint32_t queue_depth;
    uint32_t num_buffers;
};

IOUringRegisteredPipeSpliceEngine* iouring_registered_pipesplice_init(uint32_t queue_depth) {
    if (queue_depth == 0) queue_depth = 32;

    IOUringRegisteredPipeSpliceEngine* eng = (IOUringRegisteredPipeSpliceEngine*)calloc(1, sizeof(IOUringRegisteredPipeSpliceEngine));
    if (!eng) return nullptr;

    int ret = io_uring_queue_init(queue_depth, &eng->ring, 0);
    if (ret < 0) {
        free(eng);
        return nullptr;
    }

    eng->queue_depth = queue_depth;
    eng->is_buffers_registered = 0;
    eng->num_buffers = 0;
    eng->is_initialized = 1;
    return eng;
}

int iouring_registered_pipesplice_register_buffers(
    IOUringRegisteredPipeSpliceEngine* eng,
    struct iovec* iovecs,
    uint32_t nr_iovecs
) {
    if (!eng || !eng->is_initialized || !iovecs || nr_iovecs == 0) return -1;

    int ret = io_uring_register_buffers(&eng->ring, iovecs, nr_iovecs);
    if (ret == 0) {
        eng->is_buffers_registered = 1;
        eng->num_buffers = nr_iovecs;
        return 0;
    }
    // Return errno if registration is denied (e.g. RLIMIT_MEMLOCK)
    return ret;
}

int iouring_registered_pipesplice_prep_splice(
    IOUringRegisteredPipeSpliceEngine* eng,
    int fd_in,
    int64_t off_in,
    int fd_out,
    int64_t off_out,
    unsigned int nbytes,
    unsigned int flags,
    uint64_t user_data
) {
    if (!eng || !eng->is_initialized || fd_in < 0 || fd_out < 0) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) return -2;

    io_uring_prep_splice(sqe, fd_in, off_in, fd_out, off_out, nbytes, flags);
    sqe->user_data = user_data;
    return 0;
}

int iouring_registered_pipesplice_prep_read_fixed(
    IOUringRegisteredPipeSpliceEngine* eng,
    int fd,
    void* buf,
    unsigned int nbytes,
    uint64_t offset,
    int buf_index,
    uint64_t user_data
) {
    if (!eng || !eng->is_initialized || fd < 0 || !buf) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) return -2;

    io_uring_prep_read_fixed(sqe, fd, buf, nbytes, offset, buf_index);
    sqe->user_data = user_data;
    return 0;
}

int iouring_registered_pipesplice_prep_write_fixed(
    IOUringRegisteredPipeSpliceEngine* eng,
    int fd,
    const void* buf,
    unsigned int nbytes,
    uint64_t offset,
    int buf_index,
    uint64_t user_data
) {
    if (!eng || !eng->is_initialized || fd < 0 || !buf) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) return -2;

    io_uring_prep_write_fixed(sqe, fd, buf, nbytes, offset, buf_index);
    sqe->user_data = user_data;
    return 0;
}

int iouring_registered_pipesplice_submit(IOUringRegisteredPipeSpliceEngine* eng) {
    if (!eng || !eng->is_initialized) return -1;
    int ret = io_uring_submit(&eng->ring);
    return (ret >= 0) ? ret : -1;
}

int iouring_registered_pipesplice_reap(
    IOUringRegisteredPipeSpliceEngine* eng,
    int* out_res,
    uint64_t* out_user_data
) {
    if (!eng || !eng->is_initialized || !out_res) return -1;

    struct io_uring_cqe* cqe = nullptr;
    int ret = io_uring_peek_cqe(&eng->ring, &cqe);
    if (ret != 0 || !cqe) {
        ret = io_uring_wait_cqe(&eng->ring, &cqe);
        if (ret < 0 || !cqe) return -2;
    }

    *out_res = cqe->res;
    if (out_user_data) {
        *out_user_data = cqe->user_data;
    }

    io_uring_cqe_seen(&eng->ring, cqe);
    return 0;
}

void iouring_registered_pipesplice_free(IOUringRegisteredPipeSpliceEngine* eng) {
    if (!eng) return;
    if (eng->is_initialized) {
        if (eng->is_buffers_registered) {
            io_uring_unregister_buffers(&eng->ring);
            eng->is_buffers_registered = 0;
        }
        io_uring_queue_exit(&eng->ring);
        eng->is_initialized = 0;
    }
    free(eng);
}

}
