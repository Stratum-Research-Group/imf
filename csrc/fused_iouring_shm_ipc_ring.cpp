#define _GNU_SOURCE
#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/eventfd.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#define SHM_RING_DEPTH 64
#define SHM_SEGMENT_SIZE (16 * 1024 * 1024) // 16MB shared memory buffer

struct shm_ipc_ring {
    struct io_uring ring;
    int shm_fd;
    void* shm_base;
    int ev_fd;
    int in_flight;
    size_t segment_size;
};

extern "C" struct shm_ipc_ring* init_shm_ipc_ring(const char* shm_name, int is_creator, int depth) {
    struct shm_ipc_ring* ipc = (struct shm_ipc_ring*)malloc(sizeof(struct shm_ipc_ring));
    if (!ipc) return NULL;
    memset(ipc, 0, sizeof(*ipc));

    int flags = is_creator ? (O_RDWR | O_CREAT | O_TRUNC) : O_RDWR;
    ipc->shm_fd = shm_open(shm_name, flags, 0666);
    if (ipc->shm_fd < 0) {
        free(ipc);
        return NULL;
    }

    ipc->segment_size = SHM_SEGMENT_SIZE;
    if (is_creator) {
        if (ftruncate(ipc->shm_fd, ipc->segment_size) < 0) {
            close(ipc->shm_fd);
            shm_unlink(shm_name);
            free(ipc);
            return NULL;
        }
    }

    ipc->shm_base = mmap(NULL, ipc->segment_size, PROT_READ | PROT_WRITE, MAP_SHARED, ipc->shm_fd, 0);
    if (ipc->shm_base == MAP_FAILED) {
        close(ipc->shm_fd);
        free(ipc);
        return NULL;
    }

    ipc->ev_fd = eventfd(0, EFD_NONBLOCK | EFD_CLOEXEC);

    int q_depth = (depth > 0) ? depth : SHM_RING_DEPTH;
    struct io_uring_params params;
    memset(&params, 0, sizeof(params));

    if (io_uring_queue_init_params(q_depth, &ipc->ring, &params) < 0) {
        munmap(ipc->shm_base, ipc->segment_size);
        close(ipc->shm_fd);
        close(ipc->ev_fd);
        free(ipc);
        return NULL;
    }

    ipc->in_flight = 0;
    return ipc;
}

extern "C" int notify_shm_ipc_write(struct shm_ipc_ring* ipc, uint64_t counter) {
    if (!ipc || ipc->ev_fd < 0) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&ipc->ring);
    if (!sqe) {
        io_uring_submit_and_wait(&ipc->ring, 1);
        sqe = io_uring_get_sqe(&ipc->ring);
        if (!sqe) return -2;
    }

    static uint64_t ev_val = 1;
    ev_val = counter;
    io_uring_prep_write(sqe, ipc->ev_fd, &ev_val, sizeof(ev_val), 0);

    int ret = io_uring_submit(&ipc->ring);
    if (ret > 0) ipc->in_flight++;
    return ret;
}

extern "C" int poll_shm_ipc_notification(struct shm_ipc_ring* ipc, uint64_t* out_counter) {
    if (!ipc || ipc->ev_fd < 0 || !out_counter) return -1;

    uint64_t val = 0;
    ssize_t s = read(ipc->ev_fd, &val, sizeof(val));
    if (s == sizeof(val)) {
        *out_counter = val;
        return 0;
    }
    return -1; // No events pending
}

extern "C" void* get_shm_buffer(struct shm_ipc_ring* ipc) {
    return ipc ? ipc->shm_base : NULL;
}

extern "C" void close_shm_ipc_ring(struct shm_ipc_ring* ipc, const char* shm_name_to_unlink) {
    if (!ipc) return;

    if (ipc->shm_base && ipc->shm_base != MAP_FAILED) {
        munmap(ipc->shm_base, ipc->segment_size);
    }
    if (ipc->shm_fd >= 0) close(ipc->shm_fd);
    if (ipc->ev_fd >= 0) close(ipc->ev_fd);
    if (shm_name_to_unlink) shm_unlink(shm_name_to_unlink);

    io_uring_queue_exit(&ipc->ring);
    free(ipc);
}
