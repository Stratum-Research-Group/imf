// csrc/fused_iouring_direct_splice_pipe_to_socket.cpp
// ====================================================
// Production Linux 6.18 io_uring Direct Pipe-To-Socket Splice Gateway
// Transfers token streams from internal pipes directly to TCP/UNIX sockets
// via IORING_OP_SPLICE with zero user-space memory copies and zero context switches.

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <liburing.h>

extern "C" {

struct IOUringSpliceGateway {
    struct io_uring ring;
    int is_initialized;
};

IOUringSpliceGateway* iouring_splice_gateway_init(unsigned int entries) {
    if (entries == 0) entries = 32;

    IOUringSpliceGateway* gw = (IOUringSpliceGateway*)calloc(1, sizeof(IOUringSpliceGateway));
    if (!gw) return nullptr;

    int ret = io_uring_queue_init(entries, &gw->ring, 0);
    if (ret < 0) {
        free(gw);
        return nullptr;
    }

    gw->is_initialized = 1;
    return gw;
}

int iouring_splice_pipe_to_socket(
    IOUringSpliceGateway* gw,
    int pipe_fd_in,
    int socket_fd_out,
    unsigned int nbytes,
    uint64_t user_data
) {
    if (!gw || !gw->is_initialized || pipe_fd_in < 0 || socket_fd_out < 0 || nbytes == 0) {
        return -1;
    }

    struct io_uring_sqe* sqe = io_uring_get_sqe(&gw->ring);
    if (!sqe) return -2;

    // Splice from pipe (offset -1) to socket (offset -1)
    io_uring_prep_splice(sqe, pipe_fd_in, -1, socket_fd_out, -1, nbytes, SPLICE_F_NONBLOCK);
    io_uring_sqe_set_data64(sqe, user_data);

    return 0;
}

int iouring_splice_gateway_submit(IOUringSpliceGateway* gw) {
    if (!gw || !gw->is_initialized) return -1;
    return io_uring_submit(&gw->ring);
}

int iouring_splice_gateway_wait_cqe(
    IOUringSpliceGateway* gw,
    uint64_t* out_user_data,
    int* out_res
) {
    if (!gw || !gw->is_initialized) return -1;

    struct io_uring_cqe* cqe = nullptr;
    int ret = io_uring_wait_cqe(&gw->ring, &cqe);
    if (ret < 0) return ret;

    if (cqe) {
        if (out_user_data) *out_user_data = io_uring_cqe_get_data64(cqe);
        if (out_res) *out_res = cqe->res;
        io_uring_cqe_seen(&gw->ring, cqe);
        return 0;
    }
    return -1;
}

void iouring_splice_gateway_destroy(IOUringSpliceGateway* gw) {
    if (!gw) return;
    if (gw->is_initialized) {
        io_uring_queue_exit(&gw->ring);
    }
    free(gw);
}

} // extern "C"
