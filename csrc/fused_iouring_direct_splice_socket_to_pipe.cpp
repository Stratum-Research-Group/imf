// csrc/fused_iouring_direct_splice_socket_to_pipe.cpp
// ====================================================
// Production Linux 6.18 io_uring Direct Socket-To-Pipe Splice Gateway
// Ingests incoming network tokens from TCP/UNIX streaming sockets directly
// into internal process pipes via IORING_OP_SPLICE without user-space memory bouncing.

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <liburing.h>

extern "C" {

struct IOUringSocketToPipeGateway {
    struct io_uring ring;
    int is_initialized;
};

IOUringSocketToPipeGateway* iouring_socket_to_pipe_init(unsigned int entries) {
    if (entries == 0) entries = 32;

    IOUringSocketToPipeGateway* gw = (IOUringSocketToPipeGateway*)calloc(1, sizeof(IOUringSocketToPipeGateway));
    if (!gw) return nullptr;

    int ret = io_uring_queue_init(entries, &gw->ring, 0);
    if (ret < 0) {
        free(gw);
        return nullptr;
    }

    gw->is_initialized = 1;
    return gw;
}

int iouring_splice_socket_to_pipe(
    IOUringSocketToPipeGateway* gw,
    int socket_fd_in,
    int pipe_fd_out,
    unsigned int nbytes,
    uint64_t user_data
) {
    if (!gw || !gw->is_initialized || socket_fd_in < 0 || pipe_fd_out < 0 || nbytes == 0) {
        return -1;
    }

    struct io_uring_sqe* sqe = io_uring_get_sqe(&gw->ring);
    if (!sqe) return -2;

    // Splice from socket (offset -1) to pipe write end (offset -1)
    io_uring_prep_splice(sqe, socket_fd_in, -1, pipe_fd_out, -1, nbytes, SPLICE_F_NONBLOCK);
    io_uring_sqe_set_data64(sqe, user_data);

    return 0;
}

int iouring_socket_to_pipe_submit(IOUringSocketToPipeGateway* gw) {
    if (!gw || !gw->is_initialized) return -1;
    return io_uring_submit(&gw->ring);
}

int iouring_socket_to_pipe_wait_cqe(
    IOUringSocketToPipeGateway* gw,
    int* out_res,
    uint64_t* out_user_data
) {
    if (!gw || !gw->is_initialized || !out_res || !out_user_data) return -1;

    struct io_uring_cqe* cqe = nullptr;
    int ret = io_uring_wait_cqe(&gw->ring, &cqe);
    if (ret < 0) return ret;

    *out_res = cqe->res;
    *out_user_data = cqe->user_data;

    io_uring_cqe_seen(&gw->ring, cqe);
    return 0;
}

void iouring_socket_to_pipe_free(IOUringSocketToPipeGateway* gw) {
    if (!gw) return;
    if (gw->is_initialized) {
        io_uring_queue_exit(&gw->ring);
        gw->is_initialized = 0;
    }
    free(gw);
}

}
