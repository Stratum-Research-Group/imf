// csrc/fused_iouring_multishot_accept.cpp
// =========================================
// Production Linux 6.18 io_uring Multishot Accept & Socket Dispatch Engine
// Asynchronous connection intake with zero per-connection syscalls via IORING_ACCEPT_MULTISHOT.

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/socket.h>
#include <liburing.h>

extern "C" {

struct IOUringMultishotAcceptEngine {
    struct io_uring ring;
    int is_initialized;
    int listen_fd;
};

IOUringMultishotAcceptEngine* iouring_multishot_accept_init(unsigned int entries) {
    if (entries == 0) entries = 32;

    IOUringMultishotAcceptEngine* eng = (IOUringMultishotAcceptEngine*)calloc(1, sizeof(IOUringMultishotAcceptEngine));
    if (!eng) return nullptr;

    int ret = io_uring_queue_init(entries, &eng->ring, 0);
    if (ret < 0) {
        free(eng);
        return nullptr;
    }

    eng->is_initialized = 1;
    eng->listen_fd = -1;
    return eng;
}

int iouring_multishot_accept_start(
    IOUringMultishotAcceptEngine* eng,
    int listen_fd,
    uint64_t user_data
) {
    if (!eng || !eng->is_initialized || listen_fd < 0) return -1;

    eng->listen_fd = listen_fd;
    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) return -2;

    io_uring_prep_multishot_accept(sqe, listen_fd, nullptr, nullptr, 0);
    io_uring_sqe_set_data64(sqe, user_data);

    int ret = io_uring_submit(&eng->ring);
    return ret >= 0 ? 0 : ret;
}

int iouring_multishot_accept_next(
    IOUringMultishotAcceptEngine* eng,
    int* client_fd,
    uint64_t* user_data
) {
    if (!eng || !eng->is_initialized) return -1;

    struct io_uring_cqe* cqe = nullptr;
    int ret = io_uring_wait_cqe(&eng->ring, &cqe);
    if (ret < 0) return ret;

    if (client_fd) *client_fd = cqe->res;
    if (user_data) *user_data = cqe->user_data;

    int res = cqe->res;
    io_uring_cqe_seen(&eng->ring, cqe);
    return res >= 0 ? 0 : res;
}

void iouring_multishot_accept_close(IOUringMultishotAcceptEngine* eng) {
    if (!eng) return;
    if (eng->is_initialized) {
        io_uring_queue_exit(&eng->ring);
        eng->is_initialized = 0;
    }
    free(eng);
}

} // extern "C"
