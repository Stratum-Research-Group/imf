import pytest
import ctypes
import os
import tempfile
import socket

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

def test_iouring_multi_descriptor_stress():
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

    size_bytes = 16 * 1024
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"K" * size_bytes)
        tf.flush()
        tpath = tf.name

    eng = lib.init_checkpoint_rollback_engine(tpath.encode('utf-8'), 32)
    assert eng is not None

    buf1 = (ctypes.c_char * size_bytes)()
    buf2 = (ctypes.c_char * size_bytes)()

    # Submit 2 in-flight requests simultaneously
    ret1 = lib.submit_checkpoint_rollback_read(eng, buf1, size_bytes, 0)
    ret2 = lib.submit_checkpoint_rollback_read(eng, buf2, size_bytes, 0)
    assert ret1 > 0 and ret2 > 0

    reaped = lib.reap_checkpoint_rollback_completions(eng, 2)
    assert reaped >= 2
    assert buf1.value[:5] == b"KKKKK"
    assert buf2.value[:5] == b"KKKKK"

    lib.close_checkpoint_rollback_engine(eng)
    os.unlink(tpath)

def test_iouring_write_back_roundtrip():
    so_path = "csrc/fused_iouring_checkpoint_rollback.so"
    lib = ctypes.CDLL(so_path)

    lib.init_checkpoint_rollback_engine.argtypes = [ctypes.c_char_p, ctypes.c_int]
    lib.init_checkpoint_rollback_engine.restype = ctypes.c_void_p

    lib.submit_checkpoint_rollback_write.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_longlong]
    lib.submit_checkpoint_rollback_write.restype = ctypes.c_int

    lib.submit_checkpoint_rollback_read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_longlong]
    lib.submit_checkpoint_rollback_read.restype = ctypes.c_int

    lib.reap_checkpoint_rollback_completions.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.reap_checkpoint_rollback_completions.restype = ctypes.c_int

    lib.close_checkpoint_rollback_engine.argtypes = [ctypes.c_void_p]
    lib.close_checkpoint_rollback_engine.restype = None

    size_bytes = 4096
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"\x00" * size_bytes)
        tf.flush()
        tpath = tf.name

    # Write data via io_uring
    eng = lib.init_checkpoint_rollback_engine(tpath.encode('utf-8'), 16)
    assert eng is not None

    write_data = b"STREAMING_DMA_CHECKPOINT_OK" * 100
    write_buf = (ctypes.c_char * len(write_data)).from_buffer_copy(write_data)

    ret = lib.submit_checkpoint_rollback_write(eng, write_buf, len(write_data), 0)
    assert ret > 0
    reaped = lib.reap_checkpoint_rollback_completions(eng, 1)
    assert reaped >= 1
    lib.close_checkpoint_rollback_engine(eng)

    # Read back and verify
    with open(tpath, "rb") as f:
        read_back = f.read(len(write_data))
    assert read_back == write_data
    os.unlink(tpath)

def test_iouring_sqpoll_roundtrip():
    so_path = "csrc/fused_iouring_sqpoll_engine.so"
    lib = ctypes.CDLL(so_path)

    lib.init_sqpoll_engine.argtypes = [ctypes.c_char_p, ctypes.c_int]
    lib.init_sqpoll_engine.restype = ctypes.c_void_p

    lib.is_sqpoll_active.argtypes = [ctypes.c_void_p]
    lib.is_sqpoll_active.restype = ctypes.c_int

    lib.submit_sqpoll_write.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_longlong]
    lib.submit_sqpoll_write.restype = ctypes.c_int

    lib.submit_sqpoll_read.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_longlong]
    lib.submit_sqpoll_read.restype = ctypes.c_int

    lib.wait_sqpoll_completions.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.wait_sqpoll_completions.restype = ctypes.c_int

    lib.close_sqpoll_engine.argtypes = [ctypes.c_void_p]
    lib.close_sqpoll_engine.restype = None

    size_bytes = 4096
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"0" * size_bytes)
        tf.flush()
        tpath = tf.name

    eng = lib.init_sqpoll_engine(tpath.encode('utf-8'), 16)
    assert eng is not None

    payload = b"SQPOLL_ZERO_SYSCALL_DMA_VERIFIED" * 50
    write_buf = (ctypes.c_char * len(payload)).from_buffer_copy(payload)

    ret = lib.submit_sqpoll_write(eng, write_buf, len(payload), 0)
    assert ret >= 0

    done = lib.wait_sqpoll_completions(eng, 1)
    assert done >= 1

    read_buf = (ctypes.c_char * len(payload))()
    ret2 = lib.submit_sqpoll_read(eng, read_buf, len(payload), 0)
    assert ret2 >= 0

    done2 = lib.wait_sqpoll_completions(eng, 1)
    assert done2 >= 1

    assert read_buf.raw == payload

    lib.close_sqpoll_engine(eng)
    os.unlink(tpath)

def test_iouring_splice_roundtrip():
    so_path = "csrc/fused_iouring_splice_pipe.so"
    lib = ctypes.CDLL(so_path)

    lib.init_splice_engine.argtypes = [ctypes.c_int]
    lib.init_splice_engine.restype = ctypes.c_void_p

    lib.create_splice_pipe.argtypes = [ctypes.POINTER(ctypes.c_int)]
    lib.create_splice_pipe.restype = ctypes.c_int

    lib.submit_file_to_pipe_splice.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_longlong, ctypes.c_int, ctypes.c_size_t]
    lib.submit_file_to_pipe_splice.restype = ctypes.c_int

    lib.submit_pipe_to_file_splice.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_longlong, ctypes.c_size_t]
    lib.submit_pipe_to_file_splice.restype = ctypes.c_int

    lib.wait_splice_completions.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.wait_splice_completions.restype = ctypes.c_int

    lib.close_splice_engine.argtypes = [ctypes.c_void_p]
    lib.close_splice_engine.restype = None

    payload = b"SPLICE_ZERO_COPY_PIPE_DMA_STREAM_OK" * 40
    size = len(payload)

    with tempfile.NamedTemporaryFile(delete=False) as tf_src:
        tf_src.write(payload)
        tf_src.flush()
        src_path = tf_src.name

    with tempfile.NamedTemporaryFile(delete=False) as tf_dst:
        dst_path = tf_dst.name

    pipe_fds = (ctypes.c_int * 2)()
    assert lib.create_splice_pipe(pipe_fds) == 0

    fd_in = os.open(src_path, os.O_RDONLY)
    fd_out = os.open(dst_path, os.O_RDWR)

    eng = lib.init_splice_engine(16)
    assert eng is not None

    # Step 1: Splice from file to pipe write-end
    ret1 = lib.submit_file_to_pipe_splice(eng, fd_in, 0, pipe_fds[1], size)
    assert ret1 >= 0
    done1 = lib.wait_splice_completions(eng, 1)
    assert done1 >= 1

    # Step 2: Splice from pipe read-end to destination file
    ret2 = lib.submit_pipe_to_file_splice(eng, pipe_fds[0], fd_out, 0, size)
    assert ret2 >= 0
    done2 = lib.wait_splice_completions(eng, 1)
    assert done2 >= 1

    lib.close_splice_engine(eng)
    os.close(pipe_fds[0])
    os.close(pipe_fds[1])
    os.close(fd_in)
    os.close(fd_out)

    with open(dst_path, "rb") as f:
        read_dst = f.read()

    assert read_dst == payload
    os.unlink(src_path)
    os.unlink(dst_path)

def test_iouring_multishot_poll_basic():
    so_path = "csrc/fused_iouring_multishot_poll.so"
    lib = ctypes.CDLL(so_path)

    lib.init_multishot_poll_engine.argtypes = [ctypes.c_int]
    lib.init_multishot_poll_engine.restype = ctypes.c_void_p

    lib.arm_multishot_poll.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint64]
    lib.arm_multishot_poll.restype = ctypes.c_int

    lib.wait_and_drain_poll_events.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_int),
        ctypes.c_int,
        ctypes.c_int
    ]
    lib.wait_and_drain_poll_events.restype = ctypes.c_int

    lib.free_multishot_poll_engine.argtypes = [ctypes.c_void_p]
    lib.free_multishot_poll_engine.restype = None

    r_fd, w_fd = os.pipe()
    eng = lib.init_multishot_poll_engine(16)
    assert eng is not None

    user_tag = 0x42A1
    poll_in = 0x0001 # POLLIN

    ret = lib.arm_multishot_poll(eng, r_fd, poll_in, user_tag)
    assert ret == 0

    # Trigger 1: Write first message
    os.write(w_fd, b"HELLO_MULTISHOT_1\n")

    out_tags = (ctypes.c_uint64 * 8)()
    out_revents = (ctypes.c_int * 8)()

    count1 = lib.wait_and_drain_poll_events(eng, out_tags, out_revents, 8, 500)
    assert count1 >= 1
    assert out_tags[0] == user_tag
    assert (out_revents[0] & poll_in) != 0

    # Read the data to reset readiness
    msg1 = os.read(r_fd, 64)
    assert msg1 == b"HELLO_MULTISHOT_1\n"

    # Trigger 2: Write second message WITHOUT re-arming (proving multi-shot persistence)
    os.write(w_fd, b"HELLO_MULTISHOT_2\n")

    count2 = lib.wait_and_drain_poll_events(eng, out_tags, out_revents, 8, 500)
    assert count2 >= 1
    assert out_tags[0] == user_tag
    assert (out_revents[0] & poll_in) != 0

    msg2 = os.read(r_fd, 64)
    assert msg2 == b"HELLO_MULTISHOT_2\n"

    lib.free_multishot_poll_engine(eng)
    os.close(r_fd)
    os.close(w_fd)

def test_iouring_direct_reg_engine():
    so_path = "csrc/fused_iouring_direct_reg_engine.so"
    lib = ctypes.CDLL(so_path)

    lib.init_direct_reg_engine.argtypes = [
        ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_int), ctypes.c_int
    ]
    lib.init_direct_reg_engine.restype = ctypes.c_void_p

    lib.submit_fixed_write.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_longlong
    ]
    lib.submit_fixed_write.restype = ctypes.c_int

    lib.submit_fixed_read.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_longlong
    ]
    lib.submit_fixed_read.restype = ctypes.c_int

    lib.wait_direct_completions.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.wait_direct_completions.restype = ctypes.c_int

    lib.close_direct_reg_engine.argtypes = [ctypes.c_void_p]
    lib.close_direct_reg_engine.restype = None

    payload = b"DIRECT_DESCRIPTOR_REGISTERED_BUFFER_OK\n"
    size = len(payload)

    with tempfile.NamedTemporaryFile(delete=False) as tf:
        temp_path = tf.name

    fd = os.open(temp_path, os.O_RDWR)
    buf = (ctypes.c_char * 4096)()
    ctypes.memmove(buf, payload, size)

    fds = (ctypes.c_int * 1)(fd)
    eng = lib.init_direct_reg_engine(16, ctypes.cast(buf, ctypes.c_void_p), 4096, fds, 1)
    assert eng is not None

    # Write from registered buffer offset 0 to file offset 0
    ret_w = lib.submit_fixed_write(eng, 0, 0, size, 0)
    assert ret_w == 0
    done_w = lib.wait_direct_completions(eng, 1)
    assert done_w == 1

    # Read back from file offset 0 into registered buffer offset 1024
    ret_r = lib.submit_fixed_read(eng, 0, 1024, size, 0)
    assert ret_r == 0
    done_r = lib.wait_direct_completions(eng, 1)
    assert done_r == 1

    # Verify read content
    read_back = bytes(buf[1024:1024 + size])
    assert read_back == payload

    lib.close_direct_reg_engine(eng)
    os.close(fd)
    os.unlink(temp_path)

def test_iouring_socket_sendmsg_basic():
    so_path = "csrc/fused_iouring_socket_sendmsg.so"
    lib = ctypes.CDLL(so_path)

    lib.init_socket_sendmsg_engine.argtypes = [ctypes.c_int]
    lib.init_socket_sendmsg_engine.restype = ctypes.c_void_p

    lib.submit_socket_send.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int
    ]
    lib.submit_socket_send.restype = ctypes.c_int

    lib.submit_socket_send_zc.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int
    ]
    lib.submit_socket_send_zc.restype = ctypes.c_int

    lib.submit_socket_recv.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int
    ]
    lib.submit_socket_recv.restype = ctypes.c_int

    lib.wait_socket_completions.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.wait_socket_completions.restype = ctypes.c_int

    lib.close_socket_sendmsg_engine.argtypes = [ctypes.c_void_p]
    lib.close_socket_sendmsg_engine.restype = None

    s1, s2 = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    eng = lib.init_socket_sendmsg_engine(16)
    assert eng is not None

    payload = b"SOCKET_ZERO_COPY_SENDMSG_BROADCAST_OK"
    size = len(payload)
    recv_buf = (ctypes.c_char * 128)()

    # Submit receive on s2
    ret_r = lib.submit_socket_recv(eng, s2.fileno(), ctypes.cast(recv_buf, ctypes.c_char_p), size, 0)
    assert ret_r == 0

    # Submit send on s1
    ret_s = lib.submit_socket_send(eng, s1.fileno(), payload, size, 0)
    assert ret_s == 0

    # Wait for completions (receive and send)
    done = lib.wait_socket_completions(eng, 2)
    assert done >= 2

    # Verify received payload
    assert recv_buf.value[:size] == payload

    lib.close_socket_sendmsg_engine(eng)
    s1.close()
    s2.close()







def test_iouring_eventfd_signaling_basic():
    so_path = "csrc/fused_iouring_eventfd_signaling.so"
    if not os.path.exists(so_path):
        pytest.skip("fused_iouring_eventfd_signaling.so not compiled")

    lib = ctypes.CDLL(so_path)
    lib.iouring_eventfd_engine_init.argtypes = [ctypes.c_uint]
    lib.iouring_eventfd_engine_init.restype = ctypes.c_void_p

    lib.iouring_eventfd_engine_get_fd.argtypes = [ctypes.c_void_p]
    lib.iouring_eventfd_engine_get_fd.restype = ctypes.c_int

    lib.iouring_eventfd_submit_signal.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    lib.iouring_eventfd_submit_signal.restype = ctypes.c_int

    lib.iouring_eventfd_submit_poll.argtypes = [ctypes.c_void_p]
    lib.iouring_eventfd_submit_poll.restype = ctypes.c_int

    lib.iouring_eventfd_wait_ack.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64), ctypes.c_int]
    lib.iouring_eventfd_wait_ack.restype = ctypes.c_int

    lib.iouring_eventfd_engine_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_eventfd_engine_destroy.restype = None

    eng = lib.iouring_eventfd_engine_init(16)
    assert eng is not None

    efd = lib.iouring_eventfd_engine_get_fd(eng)
    assert efd >= 0

    # Submit poll on eventfd
    ret_p = lib.iouring_eventfd_submit_poll(eng)
    assert ret_p == 0

    # Submit signal (value 42)
    ret_s = lib.iouring_eventfd_submit_signal(eng, 42)
    assert ret_s == 0

    # Wait and acknowledge
    val = ctypes.c_uint64(0)
    ret_w = lib.iouring_eventfd_wait_ack(eng, ctypes.byref(val), 500)
    assert ret_w == 0
    # Wait for second completion or verify eventfd read
    if val.value == 0:
        # Acknowledge again for poll or write CQE
        ret_w2 = lib.iouring_eventfd_wait_ack(eng, ctypes.byref(val), 500)
        assert ret_w2 == 0

    assert val.value >= 42

    lib.iouring_eventfd_engine_destroy(eng)
