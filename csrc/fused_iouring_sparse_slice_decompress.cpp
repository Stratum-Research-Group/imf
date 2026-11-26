#define _GNU_SOURCE
#include <liburing.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#define SPARSE_QUEUE_DEPTH 64
#define CHUNK_ALIGN 4096

struct sparse_slice_engine {
    struct io_uring ring;
    int fd;
    int in_flight;
    size_t total_sliced;
};

extern "C" struct sparse_slice_engine* init_sparse_slice_engine(const char* sparse_file_path, int depth) {
    struct sparse_slice_engine* eng = (struct sparse_slice_engine*)malloc(sizeof(struct sparse_slice_engine));
    if (!eng) return NULL;
    memset(eng, 0, sizeof(*eng));

    eng->fd = open(sparse_file_path, O_RDONLY | O_DIRECT);
    if (eng->fd < 0) {
        eng->fd = open(sparse_file_path, O_RDONLY);
        if (eng->fd < 0) {
            free(eng);
            return NULL;
        }
    }

    int q_depth = (depth > 0) ? depth : SPARSE_QUEUE_DEPTH;
    struct io_uring_params params;
    memset(&params, 0, sizeof(params));

    if (io_uring_queue_init_params(q_depth, &eng->ring, &params) < 0) {
        close(eng->fd);
        free(eng);
        return NULL;
    }

    eng->in_flight = 0;
    eng->total_sliced = 0;
    return eng;
}

// In-place bitplane sparse de-indexing: uncompresses 2-bit non-zero blocks using bitmask metadata
extern "C" void decompress_sparse_bitplane_slice(
    const uint32_t* sparse_packed,
    const uint32_t* bitmask,
    uint32_t* dense_out,
    size_t num_words
) {
    size_t sparse_ptr = 0;
    for (size_t w = 0; w < num_words; ++w) {
        uint32_t mask = bitmask[w];
        if (mask != 0) {
            dense_out[w] = sparse_packed[sparse_ptr++];
        } else {
            dense_out[w] = 0x55555555; // Neutral 2-bit zero point (represented as 0101... = 1.0 - 1.5)
        }
    }
}

extern "C" int submit_sparse_slice_read(
    struct sparse_slice_engine* eng,
    void* dst_buf,
    size_t length,
    off_t offset
) {
    if (!eng || eng->fd < 0 || !dst_buf) return -1;

    struct io_uring_sqe* sqe = io_uring_get_sqe(&eng->ring);
    if (!sqe) {
        io_uring_submit_and_wait(&eng->ring, 1);
        sqe = io_uring_get_sqe(&eng->ring);
        if (!sqe) return -2;
    }

    io_uring_prep_read(sqe, eng->fd, dst_buf, length, offset);
    io_uring_sqe_set_data(sqe, dst_buf);

    int ret = io_uring_submit(&eng->ring);
    if (ret > 0) {
        eng->in_flight++;
        eng->total_sliced += length;
    }
    return ret;
}

extern "C" int reap_sparse_slice_completions(struct sparse_slice_engine* eng, int min_complete) {
    if (!eng) return -1;
    int reaped = 0;
    struct io_uring_cqe* cqe;

    while (reaped < min_complete && eng->in_flight > 0) {
        if (io_uring_wait_cqe(&eng->ring, &cqe) == 0) {
            io_uring_cqe_seen(&eng->ring, cqe);
            eng->in_flight--;
            reaped++;
        } else {
            break;
        }
    }

    while (eng->in_flight > 0) {
        if (io_uring_peek_cqe(&eng->ring, &cqe) == 0 && cqe) {
            io_uring_cqe_seen(&eng->ring, cqe);
            eng->in_flight--;
            reaped++;
        } else {
            break;
        }
    }

    return reaped;
}

extern "C" void close_sparse_slice_engine(struct sparse_slice_engine* eng) {
    if (!eng) return;
    reap_sparse_slice_completions(eng, eng->in_flight);
    close(eng->fd);
    io_uring_queue_exit(&eng->ring);
    free(eng);
}
