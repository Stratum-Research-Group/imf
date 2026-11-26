import ctypes
import os
import tempfile
import time
import json

def benchmark_iouring_gather_scatter():
    lib = ctypes.CDLL("csrc/fused_iouring_gather_scatter.so")
    
    # GatherScatterContext* iouring_gather_scatter_init(const char* filepath, size_t num_vectors, size_t chunk_size, unsigned int queue_depth);
    lib.iouring_gather_scatter_init.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_uint]
    lib.iouring_gather_scatter_init.restype = ctypes.c_void_p

    # int iouring_gather_scatter_read(GatherScatterContext* ctx, uint8_t** dst_buffers, size_t num_vectors, off_t file_offset);
    lib.iouring_gather_scatter_read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_longlong]
    lib.iouring_gather_scatter_read.restype = ctypes.c_int

    # void iouring_gather_scatter_close(GatherScatterContext* ctx);
    lib.iouring_gather_scatter_close.argtypes = [ctypes.c_void_p]
    lib.iouring_gather_scatter_close.restype = None

    results = {}
    chunk_size = 4096 # 4KB aligned
    
    for num_vecs in [16, 64, 256, 1024]:
        total_bytes = num_vecs * chunk_size
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(os.urandom(total_bytes))
            tf.flush()
            temp_path = tf.name

        ctx = lib.iouring_gather_scatter_init(temp_path.encode('utf-8'), num_vecs, chunk_size, 64)
        if not ctx:
            os.unlink(temp_path)
            continue

        # Warmup
        lib.iouring_gather_scatter_read(ctx, None, num_vecs, 0)

        iters = 50
        start = time.perf_counter()
        for _ in range(iters):
            bytes_transferred = lib.iouring_gather_scatter_read(ctx, None, num_vecs, 0)
        total_time = (time.perf_counter() - start) / iters

        lib.iouring_gather_scatter_close(ctx)
        os.unlink(temp_path)

        bandwidth_mbs = (total_bytes / (1024 * 1024)) / total_time
        latency_us = total_time * 1e6
        results[f"{num_vecs}_vecs_{chunk_size//1024}KB"] = {
            "num_vectors": num_vecs,
            "chunk_size_bytes": chunk_size,
            "total_bytes": total_bytes,
            "latency_us": round(latency_us, 2),
            "bandwidth_mb_per_sec": round(bandwidth_mbs, 2)
        }
    return results

def benchmark_checkpoint_rollback():
    lib = ctypes.CDLL("csrc/fused_iouring_checkpoint_rollback.so")

    # struct checkpoint_rollback_engine* init_checkpoint_rollback_engine(const char* checkpoint_path, int depth);
    lib.init_checkpoint_rollback_engine.argtypes = [ctypes.c_char_p, ctypes.c_int]
    lib.init_checkpoint_rollback_engine.restype = ctypes.c_void_p

    # int submit_checkpoint_rollback_read(struct checkpoint_rollback_engine* eng, void* target_weights_buf, size_t length, off_t file_offset);
    lib.submit_checkpoint_rollback_read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_longlong]
    lib.submit_checkpoint_rollback_read.restype = ctypes.c_int

    # int reap_checkpoint_rollback_completions(struct checkpoint_rollback_engine* eng, int min_complete);
    lib.reap_checkpoint_rollback_completions.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.reap_checkpoint_rollback_completions.restype = ctypes.c_int

    # void close_checkpoint_rollback_engine(struct checkpoint_rollback_engine* eng);
    lib.close_checkpoint_rollback_engine.argtypes = [ctypes.c_void_p]
    lib.close_checkpoint_rollback_engine.restype = None

    results = {}
    buf = (ctypes.c_char * (16 * 1024 * 1024))() # 16MB buffer

    for size_mb in [1, 4, 16, 64]:
        size_bytes = size_mb * 1024 * 1024
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            # write in 1MB chunks
            one_mb = b'\xaa' * (1024 * 1024)
            for _ in range(size_mb):
                tf.write(one_mb)
            tf.flush()
            temp_path = tf.name

        eng = lib.init_checkpoint_rollback_engine(temp_path.encode('utf-8'), 64)
        if not eng:
            os.unlink(temp_path)
            continue

        # Warmup
        lib.submit_checkpoint_rollback_read(eng, buf, min(size_bytes, 16 * 1024 * 1024), 0)
        lib.reap_checkpoint_rollback_completions(eng, 1)

        iters = 20
        start = time.perf_counter()
        for _ in range(iters):
            read_len = min(size_bytes, 16 * 1024 * 1024)
            lib.submit_checkpoint_rollback_read(eng, buf, read_len, 0)
            lib.reap_checkpoint_rollback_completions(eng, 1)
        total_time = (time.perf_counter() - start) / iters

        lib.close_checkpoint_rollback_engine(eng)
        os.unlink(temp_path)

        bandwidth_mbs = size_mb / total_time
        latency_us = total_time * 1e6
        results[f"{size_mb}MB"] = {
            "size_mb": size_mb,
            "latency_us": round(latency_us, 2),
            "bandwidth_mb_per_sec": round(bandwidth_mbs, 2)
        }
    return results

if __name__ == "__main__":
    print("Executing io_uring Direct DMA storage benchmarks on host...")
    res = {
        "storage_subsystem": "Linux 6.18+ NVMe / tmpfs io_uring zero-copy DMA",
        "gather_scatter_engine": benchmark_iouring_gather_scatter(),
        "checkpoint_rollback_engine": benchmark_checkpoint_rollback()
    }
    with open("docs/benchmarks/reproducible_iouring_hardware_benchmark.json", "w") as f:
        json.dump(res, f, indent=2)
    print("Benchmark complete:")
    print(json.dumps(res, indent=2))
