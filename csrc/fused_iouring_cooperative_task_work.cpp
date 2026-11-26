// csrc/fused_iouring_cooperative_task_work.cpp
// ===========================================
// Production Linux 6.18 io_uring Cooperative Task-Work Engine
// Eliminates inter-processor interrupts (IPI) and asynchronous task-work preemption
// via IORING_SETUP_COOP_TASKRUN and IORING_SETUP_TASKRUN_FLAG for ultra-low latency model shards.

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <liburing.h>

extern "C" {

struct IOUringCoopEngine {
    struct io_uring ring;
    int is_initialized;
    uint32_t active_flags;
};

IOUringCoopEngine* iouring_coop_engine_init(unsigned int entries) {
    if (entries == 0) entries = 64;

    IOUringCoopEngine* eng = (IOUringCoopEngine*)calloc(1, sizeof(IOUringCoopEngine));
    if (!eng) return nullptr;

    // First attempt initialization with modern Linux 6.x cooperative task-work flags
    uint32_t flags = 0;
#ifdef IORING_SETUP_COOP_TASKRUN
    flags |= IORING_SETUP_COOP_TASKRUN;
#endif
#ifdef IORING_SETUP_TASKRUN_FLAG
    flags |= IORING_SETUP_TASKRUN_FLAG;
#endif

    int ret = io_uring_queue_init(entries, &eng->ring, flags);
    if (ret < 0 && flags != 0) {
        // Fallback to standard ring flags if kernel version lacks coop flag
        flags = 0;
        ret = io_uring_queue_init(entries, &eng->ring, 0);
    }

    if (ret < 0) {
        free(eng);
        return nullptr;
    }

    eng->active_flags = flags;
    eng->is_initialized = 1;
    return eng;
}

int iouring_coop_engine_prep_read(
    IOUringCoopEngine* eng,
    int fd,
    void* buf,
    unsigned int nbytes,
    uint64_t offset,
    uint64_t user_data
) {
    if (!eng || !eng->is_initialized || fd < 0 || !buf) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) return -2;

    io_uring_prep_read(sqe, fd, buf, nbytes, offset);
    io_uring_sqe_set_data64(sqe, user_data);

    return 0;
}

int iouring_coop_engine_submit(IOUringCoopEngine* eng) {
    if (!eng || !eng->is_initialized) return -1;
    return io_uring_submit(&eng->ring);
}

int iouring_coop_engine_wait_cqe(
    IOUringCoopEngine* eng,
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

uint32_t iouring_coop_engine_get_flags(IOUringCoopEngine* eng) {
    if (!eng) return 0;
    return eng->active_flags;
}

void iouring_coop_engine_destroy(IOUringCoopEngine* eng) {
    if (!eng) return;
    if (eng->is_initialized) {
        io_uring_queue_exit(&eng->ring);
    }
    free(eng);
}

} // extern "C"
