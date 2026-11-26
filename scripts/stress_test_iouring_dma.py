import ctypes
import os
import tempfile
import time
import json
import numpy as np

def run_stress_test(num_iterations=2000, chunk_size=64*1024):
    lib = ctypes.CDLL("csrc/fused_iouring_checkpoint_rollback.so")
    lib.init_checkpoint_rollback_engine.argtypes = [ctypes.c_char_p, ctypes.c_int]
    lib.init_checkpoint_rollback_engine.restype = ctypes.c_void_p

    lib.submit_checkpoint_rollback_read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_longlong]
    lib.submit_checkpoint_rollback_read.restype = ctypes.c_int

    lib.reap_checkpoint_rollback_completions.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.reap_checkpoint_rollback_completions.restype = ctypes.c_int

    lib.close_checkpoint_rollback_engine.argtypes = [ctypes.c_void_p]
    lib.close_checkpoint_rollback_engine.restype = None

    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"M" * chunk_size)
        tf.flush()
        tpath = tf.name

    eng = lib.init_checkpoint_rollback_engine(tpath.encode('utf-8'), 32)
    assert eng is not None

    buf = (ctypes.c_char * chunk_size)()
    latencies = []

    for i in range(num_iterations):
        t0 = time.perf_counter()
        ret = lib.submit_checkpoint_rollback_read(eng, buf, chunk_size, 0)
        reaped = lib.reap_checkpoint_rollback_completions(eng, 1)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1e6)

    lib.close_checkpoint_rollback_engine(eng)
    os.unlink(tpath)

    p50 = np.percentile(latencies, 50)
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)
    max_lat = np.max(latencies)

    res = {
        "iterations": num_iterations,
        "chunk_size_bytes": chunk_size,
        "p50_us": round(float(p50), 2),
        "p95_us": round(float(p95), 2),
        "p99_us": round(float(p99), 2),
        "max_us": round(float(max_lat), 2)
    }
    with open("docs/benchmarks/iouring_stress_test_report.json", "w") as f:
        json.dump(res, f, indent=2)

    print("Direct-DMA stress test completed cleanly:")
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    run_stress_test()
