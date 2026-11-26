// csrc/fused_iouring_fixed_file_table.cpp
// =======================================
// Production Linux 6.18 io_uring Direct Registered File Table Engine
// Bypasses kernel fdtable locking and reference counting via IORING_REGISTER_FILES
// and IOSQE_FIXED_FILE for ultra-low latency model shard tensor ingestion.

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <liburing.h>

extern "C" {

struct IOUringFixedFileEngine {
    struct io_uring ring;
    int is_initialized;
    unsigned int nr_files;
    int* registered_fds;
};

IOUringFixedFileEngine* iouring_fixed_file_engine_init(
    unsigned int entries,
    const int* fds,
    unsigned int nr_files
) {
    if (entries == 0) entries = 64;
    if (!fds || nr_files == 0) return nullptr;

    IOUringFixedFileEngine* eng = (IOUringFixedFileEngine*)calloc(1, sizeof(IOUringFixedFileEngine));
    if (!eng) return nullptr;

    int ret = io_uring_queue_init(entries, &eng->ring, 0);
    if (ret < 0) {
        free(eng);
        return nullptr;
    }

    // Register fixed files table
    ret = io_uring_register_files(&eng->ring, fds, nr_files);
    if (ret < 0) {
        io_uring_queue_exit(&eng->ring);
        free(eng);
        return nullptr;
    }

    eng->registered_fds = (int*)malloc(nr_files * sizeof(int));
    if (eng->registered_fds) {
        memcpy(eng->registered_fds, fds, nr_files * sizeof(int));
    }
    eng->nr_files = nr_files;
    eng->is_initialized = 1;

    return eng;
}

int iouring_fixed_file_read(
    IOUringFixedFileEngine* eng,
    unsigned int file_index,
    void* buf,
    unsigned int nbytes,
    uint64_t offset,
    uint64_t user_data
) {
    if (!eng || !eng->is_initialized || file_index >= eng->nr_files || !buf) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) return -2;

    // Direct file index read with IOSQE_FIXED_FILE
    io_uring_prep_read(sqe, (int)file_index, buf, nbytes, offset);
    sqe->flags |= IOSQE_FIXED_FILE;
    io_uring_sqe_set_data64(sqe, user_data);

    return 0;
}

int iouring_fixed_file_submit(IOUringFixedFileEngine* eng) {
    if (!eng || !eng->is_initialized) return -1;
    return io_uring_submit(&eng->ring);
}

int iouring_fixed_file_wait_cqe(
    IOUringFixedFileEngine* eng,
    uint64_t* out_user_data,
    int* out_res
) {
    if (!eng || !eng->is_initialized) return -1;

    struct io_uring_cqe* cqe = nullptr;
    int ret = io_uring_wait_cqe(&eng->ring, &cqe);
    if (ret < 0) return ret;

    if (cqe) {
        if (out_user_data) *out_user_data = io_uring_cqe_get_data64(cqe);
        if (out_res) *out_res = cqe->res;
        io_uring_cqe_seen(&eng->ring, cqe);
        return 0;
    }
    return -1;
}

void iouring_fixed_file_engine_destroy(IOUringFixedFileEngine* eng) {
    if (!eng) return;
    if (eng->is_initialized) {
        io_uring_unregister_files(&eng->ring);
        io_uring_queue_exit(&eng->ring);
    }
    if (eng->registered_fds) {
        free(eng->registered_fds);
    }
    free(eng);
}

} // extern "C"
