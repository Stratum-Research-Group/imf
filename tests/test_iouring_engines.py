import pytest
import ctypes
import os
import tempfile

def test_iouring_gather_scatter_basic():
    so_path = "csrc/fused_iouring_gather_scatter.so"
    lib = ctypes.CDLL(so_path)
    
    lib.iouring_gather_scatter_init.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_uint]
    lib.iouring_gather_scatter_init.restype = ctypes.c_void_p

    lib.iouring_gather_scatter_read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_longlong]
    lib.iouring_gather_scatter_read.restype = ctypes.c_int

    lib.iouring_gather_scatter_close.argtypes = [ctypes.c_void_p]
    lib.iouring_gather_scatter_close.restype = None

    num_vectors = 4
    chunk_size = 4096
    total_bytes = num_vectors * chunk_size
    data = b"X" * total_bytes

    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(data)
        tf.flush()
        temp_path = tf.name

    ctx = lib.iouring_gather_scatter_init(temp_path.encode('utf-8'), num_vectors, chunk_size, 16)
    assert ctx is not None

    transferred = lib.iouring_gather_scatter_read(ctx, None, num_vectors, 0)
    assert transferred == total_bytes

    lib.iouring_gather_scatter_close(ctx)
    os.unlink(temp_path)

def test_iouring_checkpoint_rollback_basic():
    so_path = "csrc/fused_iouring_checkpoint_rollback.so"
    lib = ctypes.CDLL(so_path)

    lib.init_checkpoint_rollback_engine.argtypes = [ctypes.c_char_p, ctypes.c_int]
    lib.init_checkpoint_rollback_engine.restype = ctypes.c_void_p

    lib.submit_checkpoint_rollback_read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_longlong]
    lib.submit_checkpoint_rollback_read.restype = ctypes.c_int

    lib.reap_checkpoint_rollback_completions.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.reap_checkpoint_rollback_completions.restype = ctypes.c_int

    lib.close_checkpoint_rollback_engine.argtypes = [ctypes.c_void_p]
    lib.close_checkpoint_rollback_engine.restype = None

    size_bytes = 64 * 1024
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"Z" * size_bytes)
        tf.flush()
        temp_path = tf.name

    eng = lib.init_checkpoint_rollback_engine(temp_path.encode('utf-8'), 16)
    assert eng is not None

    buf = (ctypes.c_char * size_bytes)()
    ret = lib.submit_checkpoint_rollback_read(eng, buf, size_bytes, 0)
    assert ret > 0

    reaped = lib.reap_checkpoint_rollback_completions(eng, 1)
    assert reaped >= 1
    assert buf.value[:10] == b"ZZZZZZZZZZ"

    lib.close_checkpoint_rollback_engine(eng)
    os.unlink(temp_path)
