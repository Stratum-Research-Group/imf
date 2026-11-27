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

def test_iouring_ringbuf_interop_basic():
    so_path = "csrc/fused_iouring_ringbuf_interop.so"
    if not os.path.exists(so_path):
        pytest.skip("fused_iouring_ringbuf_interop.so not compiled")

    lib = ctypes.CDLL(so_path)
    lib.iouring_ringbuf_init.argtypes = [ctypes.c_size_t, ctypes.c_uint]
    lib.iouring_ringbuf_init.restype = ctypes.c_void_p

    lib.iouring_ringbuf_write.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
    lib.iouring_ringbuf_write.restype = ctypes.c_int

    lib.iouring_ringbuf_read.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
    lib.iouring_ringbuf_read.restype = ctypes.c_int

    lib.iouring_ringbuf_get_available.argtypes = [ctypes.c_void_p]
    lib.iouring_ringbuf_get_available.restype = ctypes.c_size_t

    lib.iouring_ringbuf_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_ringbuf_destroy.restype = None

    cap = 1024
    eng = lib.iouring_ringbuf_init(cap, 16)
    assert eng is not None

    data = b"RINGBUF_ZERO_COPY_PAYLOAD_TEST_OK_123456789"
    ret_w = lib.iouring_ringbuf_write(eng, data, len(data))
    assert ret_w == 0

    avail = lib.iouring_ringbuf_get_available(eng)
    assert avail == len(data)

    out_buf = (ctypes.c_char * len(data))()
    ret_r = lib.iouring_ringbuf_read(eng, ctypes.cast(out_buf, ctypes.c_char_p), len(data))
    assert ret_r == 0
    assert out_buf.value == data

    assert lib.iouring_ringbuf_get_available(eng) == 0

    lib.iouring_ringbuf_destroy(eng)

def test_iouring_splice_gateway_basic():
    so_path = "csrc/fused_iouring_splice_socket.so"
    if not os.path.exists(so_path):
        pytest.skip("fused_iouring_splice_socket.so not compiled")

    lib = ctypes.CDLL(so_path)
    lib.iouring_splice_gateway_init.argtypes = [ctypes.c_uint]
    lib.iouring_splice_gateway_init.restype = ctypes.c_void_p

    lib.iouring_splice_gateway_submit.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int64,
        ctypes.c_int, ctypes.c_int64, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint64
    ]
    lib.iouring_splice_gateway_submit.restype = ctypes.c_int

    lib.iouring_splice_gateway_wait.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_splice_gateway_wait.restype = ctypes.c_int

    lib.iouring_splice_gateway_close.argtypes = [ctypes.c_void_p]
    lib.iouring_splice_gateway_close.restype = None

    gw = lib.iouring_splice_gateway_init(16)
    assert gw is not None

    p1_r, p1_w = os.pipe()
    p2_r, p2_w = os.pipe()

    test_payload = b"SPLICE_ZERO_COPY_PACKET_TEST_PAYLOAD_5678"
    os.write(p1_w, test_payload)

    ret = lib.iouring_splice_gateway_submit(
        gw, p1_r, -1, p2_w, -1, len(test_payload), 0, 0xABC
    )
    assert ret == 0

    res_bytes = ctypes.c_int(0)
    user_data = ctypes.c_uint64(0)
    wait_ret = lib.iouring_splice_gateway_wait(gw, ctypes.byref(res_bytes), ctypes.byref(user_data))
    assert wait_ret == 0
    assert res_bytes.value == len(test_payload)
    assert user_data.value == 0xABC

    received = os.read(p2_r, len(test_payload))
    assert received == test_payload

    os.close(p1_r)
    os.close(p1_w)
    os.close(p2_r)
    os.close(p2_w)
    lib.iouring_splice_gateway_close(gw)

def test_iouring_socket_recv_basic():
    so_path = "csrc/fused_iouring_socket_recvmsg.so"
    if not os.path.exists(so_path):
        pytest.skip("fused_iouring_socket_recvmsg.so not compiled")

    lib = ctypes.CDLL(so_path)
    lib.iouring_socket_recv_init.argtypes = [ctypes.c_uint]
    lib.iouring_socket_recv_init.restype = ctypes.c_void_p

    lib.iouring_socket_recv_submit.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
        ctypes.c_size_t, ctypes.c_int, ctypes.c_uint64
    ]
    lib.iouring_socket_recv_submit.restype = ctypes.c_int

    lib.iouring_socket_recv_wait.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_socket_recv_wait.restype = ctypes.c_int

    lib.iouring_socket_recv_close.argtypes = [ctypes.c_void_p]
    lib.iouring_socket_recv_close.restype = None

    eng = lib.iouring_socket_recv_init(16)
    assert eng is not None

    s_recv, s_send = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    payload = b"IOURING_DIRECT_SOCKET_RECV_TEST_998877"

    recv_buf = (ctypes.c_char * 64)()

    # Submit receive
    ret = lib.iouring_socket_recv_submit(
        eng, s_recv.fileno(), ctypes.cast(recv_buf, ctypes.c_void_p), len(recv_buf), 0, 0x55AA
    )
    assert ret == 0

    # Send payload
    s_send.sendall(payload)

    bytes_recv = ctypes.c_int(0)
    user_data = ctypes.c_uint64(0)
    wait_ret = lib.iouring_socket_recv_wait(eng, ctypes.byref(bytes_recv), ctypes.byref(user_data))
    assert wait_ret == 0
    assert bytes_recv.value == len(payload)
    assert user_data.value == 0x55AA
    assert recv_buf.value == payload

    s_recv.close()
    s_send.close()
    lib.iouring_socket_recv_close(eng)

def test_iouring_multishot_accept_basic():
    so_path = "csrc/fused_iouring_multishot_accept.so"
    if not os.path.exists(so_path):
        pytest.skip("fused_iouring_multishot_accept.so not compiled")

    lib = ctypes.CDLL(so_path)
    lib.iouring_multishot_accept_init.argtypes = [ctypes.c_uint]
    lib.iouring_multishot_accept_init.restype = ctypes.c_void_p

    lib.iouring_multishot_accept_start.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint64]
    lib.iouring_multishot_accept_start.restype = ctypes.c_int

    lib.iouring_multishot_accept_next.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_multishot_accept_next.restype = ctypes.c_int

    lib.iouring_multishot_accept_close.argtypes = [ctypes.c_void_p]
    lib.iouring_multishot_accept_close.restype = None

    eng = lib.iouring_multishot_accept_init(16)
    assert eng is not None

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 0))
    server.listen(5)
    server_port = server.getsockname()[1]

    ret = lib.iouring_multishot_accept_start(eng, server.fileno(), 0x1234)
    assert ret == 0

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(('127.0.0.1', server_port))

    client_fd = ctypes.c_int(-1)
    user_data = ctypes.c_uint64(0)
    wait_ret = lib.iouring_multishot_accept_next(eng, ctypes.byref(client_fd), ctypes.byref(user_data))
    assert wait_ret == 0
    assert client_fd.value >= 0
    assert user_data.value == 0x1234

    # Close accepted socket in kernel
    os.close(client_fd.value)
    client.close()
    server.close()
    lib.iouring_multishot_accept_close(eng)

def test_iouring_fixed_file_table_correctness():
    so_path = "csrc/fused_iouring_fixed_file_table.so"
    assert os.path.exists(so_path), "Shared library does not exist"
    lib = ctypes.CDLL(so_path)

    lib.iouring_fixed_file_engine_init.argtypes = [
        ctypes.c_uint, ctypes.POINTER(ctypes.c_int), ctypes.c_uint
    ]
    lib.iouring_fixed_file_engine_init.restype = ctypes.c_void_p

    lib.iouring_fixed_file_read.argtypes = [
        ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint64, ctypes.c_uint64
    ]
    lib.iouring_fixed_file_read.restype = ctypes.c_int

    lib.iouring_fixed_file_submit.argtypes = [ctypes.c_void_p]
    lib.iouring_fixed_file_submit.restype = ctypes.c_int

    lib.iouring_fixed_file_wait_cqe.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_int)
    ]
    lib.iouring_fixed_file_wait_cqe.restype = ctypes.c_int

    lib.iouring_fixed_file_engine_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_fixed_file_engine_destroy.restype = None

    # Create temporary files for testing direct table registration
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f1, tempfile.NamedTemporaryFile(mode='wb', delete=False) as f2:
        test_payload1 = b"IMF_BLACKWELL_TENSOR_SHARD_001"
        test_payload2 = b"SPINNING_POLYTOPE_CLUTCH_MANIFOLD_002"
        f1.write(test_payload1)
        f1.flush()
        f2.write(test_payload2)
        f2.flush()
        p1, p2 = f1.name, f2.name

    fd1 = os.open(p1, os.O_RDONLY)
    fd2 = os.open(p2, os.O_RDONLY)
    fds_array = (ctypes.c_int * 2)(fd1, fd2)

    try:
        eng = lib.iouring_fixed_file_engine_init(32, fds_array, 2)
        assert eng is not None

        buf1 = ctypes.create_string_buffer(len(test_payload1))
        buf2 = ctypes.create_string_buffer(len(test_payload2))

        # Queue reads via fixed file indices 0 and 1
        r1 = lib.iouring_fixed_file_read(eng, 0, buf1, len(test_payload1), 0, 0xAA)
        assert r1 == 0
        r2 = lib.iouring_fixed_file_read(eng, 1, buf2, len(test_payload2), 0, 0xBB)
        assert r2 == 0

        submitted = lib.iouring_fixed_file_submit(eng)
        assert submitted == 2

        # Harvest completions
        for _ in range(2):
            out_ud = ctypes.c_uint64(0)
            out_res = ctypes.c_int(0)
            w = lib.iouring_fixed_file_wait_cqe(eng, ctypes.byref(out_ud), ctypes.byref(out_res))
            assert w == 0
            if out_ud.value == 0xAA:
                assert out_res.value == len(test_payload1)
                assert buf1.raw == test_payload1
            elif out_ud.value == 0xBB:
                assert out_res.value == len(test_payload2)
                assert buf2.raw == test_payload2
            else:
                pytest.fail(f"Unexpected user data: {hex(out_ud.value)}")

        lib.iouring_fixed_file_engine_destroy(eng)
    finally:
        os.close(fd1)
        os.close(fd2)
        os.unlink(p1)
        os.unlink(p2)

def test_iouring_cooperative_task_work_correctness():
    so_path = "csrc/fused_iouring_cooperative_task_work.so"
    assert os.path.exists(so_path), "Shared library does not exist"
    lib = ctypes.CDLL(so_path)

    lib.iouring_coop_engine_init.argtypes = [ctypes.c_uint]
    lib.iouring_coop_engine_init.restype = ctypes.c_void_p

    lib.iouring_coop_engine_prep_read.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint64, ctypes.c_uint64
    ]
    lib.iouring_coop_engine_prep_read.restype = ctypes.c_int

    lib.iouring_coop_engine_submit.argtypes = [ctypes.c_void_p]
    lib.iouring_coop_engine_submit.restype = ctypes.c_int

    lib.iouring_coop_engine_wait_cqe.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_int)
    ]
    lib.iouring_coop_engine_wait_cqe.restype = ctypes.c_int

    lib.iouring_coop_engine_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_coop_engine_destroy.restype = None

    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
        test_data = b"IMF_COOPERATIVE_TASK_WORK_ZERO_IPI_PAYLOAD"
        f.write(test_data)
        f.flush()
        f_name = f.name

    fd = os.open(f_name, os.O_RDONLY)
    try:
        eng = lib.iouring_coop_engine_init(16)
        assert eng is not None

        buf = ctypes.create_string_buffer(len(test_data))
        ret = lib.iouring_coop_engine_prep_read(eng, fd, buf, len(test_data), 0, 0x1337)
        assert ret == 0

        sub = lib.iouring_coop_engine_submit(eng)
        assert sub == 1

        out_ud = ctypes.c_uint64(0)
        out_res = ctypes.c_int(0)
        w = lib.iouring_coop_engine_wait_cqe(eng, ctypes.byref(out_ud), ctypes.byref(out_res))
        assert w == 0
        assert out_ud.value == 0x1337
        assert out_res.value == len(test_data)
        assert buf.raw == test_data

        lib.iouring_coop_engine_destroy(eng)
    finally:
        os.close(fd)
        os.unlink(f_name)

def test_iouring_direct_splice_pipe_to_socket_correctness():
    so_path = "csrc/fused_iouring_direct_splice_pipe_to_socket.so"
    assert os.path.exists(so_path), "Shared library does not exist"
    lib = ctypes.CDLL(so_path)

    lib.iouring_splice_gateway_init.argtypes = [ctypes.c_uint]
    lib.iouring_splice_gateway_init.restype = ctypes.c_void_p

    lib.iouring_splice_pipe_to_socket.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint64
    ]
    lib.iouring_splice_pipe_to_socket.restype = ctypes.c_int

    lib.iouring_splice_gateway_submit.argtypes = [ctypes.c_void_p]
    lib.iouring_splice_gateway_submit.restype = ctypes.c_int

    lib.iouring_splice_gateway_wait_cqe.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_int)
    ]
    lib.iouring_splice_gateway_wait_cqe.restype = ctypes.c_int

    lib.iouring_splice_gateway_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_splice_gateway_destroy.restype = None

    gw = lib.iouring_splice_gateway_init(16)
    assert gw is not None

    r_pipe, w_pipe = os.pipe()
    # Create connected socketpair
    sock_server, sock_client = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

    test_payload = b"IMF_ZERO_COPY_SPLICE_TOKEN_STREAM_0123456789"
    os.write(w_pipe, test_payload)

    try:
        ret = lib.iouring_splice_pipe_to_socket(gw, r_pipe, sock_server.fileno(), len(test_payload), 0x7777)
        assert ret == 0

        submitted = lib.iouring_splice_gateway_submit(gw)
        assert submitted == 1

        out_ud = ctypes.c_uint64(0)
        out_res = ctypes.c_int(0)
        w = lib.iouring_splice_gateway_wait_cqe(gw, ctypes.byref(out_ud), ctypes.byref(out_res))
        assert w == 0
        assert out_ud.value == 0x7777
        assert out_res.value == len(test_payload)

        # Receive from client socket
        received = sock_client.recv(1024)
        assert received == test_payload

        lib.iouring_splice_gateway_destroy(gw)
    finally:
        os.close(r_pipe)
        os.close(w_pipe)
        sock_server.close()
        sock_client.close()


def test_iouring_direct_splice_socket_to_pipe_correctness():
    so_path = "csrc/fused_iouring_direct_splice_socket_to_pipe.so"
    assert os.path.exists(so_path)
    lib = ctypes.CDLL(so_path)

    lib.iouring_socket_to_pipe_init.argtypes = [ctypes.c_uint]
    lib.iouring_socket_to_pipe_init.restype = ctypes.c_void_p

    lib.iouring_splice_socket_to_pipe.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint64
    ]
    lib.iouring_splice_socket_to_pipe.restype = ctypes.c_int

    lib.iouring_socket_to_pipe_submit.argtypes = [ctypes.c_void_p]
    lib.iouring_socket_to_pipe_submit.restype = ctypes.c_int

    lib.iouring_socket_to_pipe_wait_cqe.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_socket_to_pipe_wait_cqe.restype = ctypes.c_int

    lib.iouring_socket_to_pipe_free.argtypes = [ctypes.c_void_p]
    lib.iouring_socket_to_pipe_free.restype = None

    gw = lib.iouring_socket_to_pipe_init(16)
    assert gw is not None

    r_pipe, w_pipe = os.pipe()
    sock_sender, sock_receiver = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

    test_payload = b"IMF_ZERO_COPY_SPLICE_SOCKET_TO_PIPE_STREAM_9876543210"
    sock_sender.sendall(test_payload)

    try:
        ret = lib.iouring_splice_socket_to_pipe(gw, sock_receiver.fileno(), w_pipe, len(test_payload), 0x8888)
        assert ret == 0

        submitted = lib.iouring_socket_to_pipe_submit(gw)
        assert submitted == 1

        out_res = ctypes.c_int(0)
        out_ud = ctypes.c_uint64(0)
        w = lib.iouring_socket_to_pipe_wait_cqe(gw, ctypes.byref(out_res), ctypes.byref(out_ud))
        assert w == 0
        assert out_ud.value == 0x8888
        assert out_res.value == len(test_payload)

        # Read back from pipe read end
        received = os.read(r_pipe, 1024)
        assert received == test_payload

        lib.iouring_socket_to_pipe_free(gw)
    finally:
        os.close(r_pipe)
        os.close(w_pipe)
        sock_sender.close()
        sock_receiver.close()


def test_iouring_multishot_read_ringbuf_correctness():
    so_path = "csrc/fused_iouring_multishot_read_ringbuf.so"
    assert os.path.exists(so_path)
    lib = ctypes.CDLL(so_path)

    lib.iouring_ringbuf_engine_init.argtypes = [
        ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_int
    ]
    lib.iouring_ringbuf_engine_init.restype = ctypes.c_void_p

    lib.iouring_ringbuf_engine_submit_recv_multishot.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_uint64
    ]
    lib.iouring_ringbuf_engine_submit_recv_multishot.restype = ctypes.c_int

    lib.iouring_ringbuf_engine_submit.argtypes = [ctypes.c_void_p]
    lib.iouring_ringbuf_engine_submit.restype = ctypes.c_int

    lib.iouring_ringbuf_engine_wait_cqe.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_int)
    ]
    lib.iouring_ringbuf_engine_wait_cqe.restype = ctypes.c_int

    lib.iouring_ringbuf_engine_get_buf.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.iouring_ringbuf_engine_get_buf.restype = ctypes.c_void_p

    lib.iouring_ringbuf_engine_recycle_buf.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.iouring_ringbuf_engine_recycle_buf.restype = None

    lib.iouring_ringbuf_engine_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_ringbuf_engine_destroy.restype = None

    eng = lib.iouring_ringbuf_engine_init(16, 8, 256, 2)
    assert eng is not None

    sock_sender, sock_receiver = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    test_payload = b"ADELIC_MULTISHOT_RINGBUF_TEST_12345"

    try:
        ret = lib.iouring_ringbuf_engine_submit_recv_multishot(eng, sock_receiver.fileno(), 0x9999)
        assert ret == 0

        submitted = lib.iouring_ringbuf_engine_submit(eng)
        assert submitted == 1

        sock_sender.sendall(test_payload)

        out_res = ctypes.c_int(0)
        out_flags = ctypes.c_uint32(0)
        out_ud = ctypes.c_uint64(0)
        out_bid = ctypes.c_int(-1)

        w = lib.iouring_ringbuf_engine_wait_cqe(
            eng, ctypes.byref(out_res), ctypes.byref(out_flags), ctypes.byref(out_ud), ctypes.byref(out_bid)
        )
        assert w == 0
        assert out_ud.value == 0x9999
        assert out_res.value == len(test_payload)
        assert out_bid.value >= 0

        buf_ptr = lib.iouring_ringbuf_engine_get_buf(eng, out_bid.value)
        assert buf_ptr is not None

        content = ctypes.string_at(buf_ptr, len(test_payload))
        assert content == test_payload

        # Recycle buffer
        lib.iouring_ringbuf_engine_recycle_buf(eng, out_bid.value)

        lib.iouring_ringbuf_engine_destroy(eng)
    finally:
        sock_sender.close()
        sock_receiver.close()


def test_iouring_fixed_dma_nvme_correctness():
    so_path = "csrc/fused_iouring_fixed_dma_buf_nvme_passthru.so"
    assert os.path.exists(so_path)
    lib = ctypes.CDLL(so_path)

    lib.iouring_fixed_dma_nvme_init.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
    lib.iouring_fixed_dma_nvme_init.restype = ctypes.c_void_p

    lib.iouring_fixed_dma_nvme_submit_read.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_uint64, ctypes.c_uint, ctypes.c_uint
    ]
    lib.iouring_fixed_dma_nvme_submit_read.restype = ctypes.c_int

    lib.iouring_fixed_dma_nvme_submit_write.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_uint64, ctypes.c_uint, ctypes.c_uint
    ]
    lib.iouring_fixed_dma_nvme_submit_write.restype = ctypes.c_int

    lib.iouring_fixed_dma_nvme_wait_complete.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_uint)
    ]
    lib.iouring_fixed_dma_nvme_wait_complete.restype = ctypes.c_int

    lib.iouring_fixed_dma_nvme_get_buffer.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    lib.iouring_fixed_dma_nvme_get_buffer.restype = ctypes.c_void_p

    lib.iouring_fixed_dma_nvme_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_fixed_dma_nvme_destroy.restype = None

    buf_size = 4096
    eng = lib.iouring_fixed_dma_nvme_init(16, buf_size, 2)
    assert eng is not None

    payload = b"FIXED_DMA_BUF_NVME_PASSTHROUGH_VERIFIED_ZERO_SYSCALL_480M" * 10
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(payload)
        tf.flush()
        tpath = tf.name

    try:
        fd = os.open(tpath, os.O_RDWR)
        # Test fixed DMA read into buffer 0
        ret = lib.iouring_fixed_dma_nvme_submit_read(eng, fd, 0, len(payload), 0)
        assert ret == 0

        bytes_transferred = ctypes.c_int64(0)
        completed_buf = ctypes.c_uint(99)
        ret_wait = lib.iouring_fixed_dma_nvme_wait_complete(
            eng, ctypes.byref(bytes_transferred), ctypes.byref(completed_buf)
        )
        assert ret_wait == 0
        assert bytes_transferred.value == len(payload)
        assert completed_buf.value == 0

        buf0_ptr = lib.iouring_fixed_dma_nvme_get_buffer(eng, 0)
        assert buf0_ptr is not None
        read_data = ctypes.string_at(buf0_ptr, len(payload))
        assert read_data == payload

        # Test fixed DMA write from buffer 1
        write_payload = b"OVERWRITTEN_VIA_DMA_BUF_1_SUCCESSFUL"
        buf1_ptr = lib.iouring_fixed_dma_nvme_get_buffer(eng, 1)
        assert buf1_ptr is not None
        ctypes.memmove(buf1_ptr, write_payload, len(write_payload))

        ret_write = lib.iouring_fixed_dma_nvme_submit_write(eng, fd, 0, len(write_payload), 1)
        assert ret_write == 0

        ret_wait2 = lib.iouring_fixed_dma_nvme_wait_complete(
            eng, ctypes.byref(bytes_transferred), ctypes.byref(completed_buf)
        )
        assert ret_wait2 == 0
        assert bytes_transferred.value == len(write_payload)
        assert completed_buf.value == 1

        os.close(fd)
        with open(tpath, "rb") as f:
            disk_content = f.read()
        assert disk_content.startswith(write_payload)

    finally:
        lib.iouring_fixed_dma_nvme_destroy(eng)
        if os.path.exists(tpath):
            os.unlink(tpath)


def test_iouring_sqpoll_passthru_correctness():
    so_path = "csrc/fused_iouring_sqpoll_passthru_cmd.so"
    assert os.path.exists(so_path)
    lib = ctypes.CDLL(so_path)

    lib.iouring_sqpoll_passthru_init.argtypes = [ctypes.c_uint, ctypes.c_uint]
    lib.iouring_sqpoll_passthru_init.restype = ctypes.c_void_p

    lib.iouring_sqpoll_passthru_submit_cmd.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint64, ctypes.c_uint64
    ]
    lib.iouring_sqpoll_passthru_submit_cmd.restype = ctypes.c_int

    lib.iouring_sqpoll_passthru_submit_write.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint64, ctypes.c_uint64
    ]
    lib.iouring_sqpoll_passthru_submit_write.restype = ctypes.c_int

    lib.iouring_sqpoll_passthru_reap_completion.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64), ctypes.POINTER(ctypes.c_uint64), ctypes.c_int
    ]
    lib.iouring_sqpoll_passthru_reap_completion.restype = ctypes.c_int

    lib.iouring_sqpoll_passthru_is_sqpoll.argtypes = [ctypes.c_void_p]
    lib.iouring_sqpoll_passthru_is_sqpoll.restype = ctypes.c_int

    lib.iouring_sqpoll_passthru_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_sqpoll_passthru_destroy.restype = None

    eng = lib.iouring_sqpoll_passthru_init(32, 1000)
    assert eng is not None

    payload = b"SQPOLL_PASSTHROUGH_KERNEL_THREAD_VERIFIED_490M" * 8
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(payload)
        tf.flush()
        tpath = tf.name

    try:
        fd = os.open(tpath, os.O_RDWR)
        read_buf = (ctypes.c_char * len(payload))()

        ret = lib.iouring_sqpoll_passthru_submit_cmd(
            eng, fd, read_buf, len(payload), 0, 0x1234
        )
        assert ret == 0

        bytes_reaped = ctypes.c_int64(0)
        user_data = ctypes.c_uint64(0)
        reap_ret = lib.iouring_sqpoll_passthru_reap_completion(
            eng, ctypes.byref(bytes_reaped), ctypes.byref(user_data), 1000
        )
        assert reap_ret == 0
        assert bytes_reaped.value == len(payload)
        assert user_data.value == 0x1234
        assert read_buf.raw == payload

        os.close(fd)
    finally:
        lib.iouring_sqpoll_passthru_destroy(eng)
        if os.path.exists(tpath):
            os.unlink(tpath)


def test_iouring_registered_pipesplice_correctness():
    so_path = "csrc/libfused_iouring_registered_pipesplice.so"
    if not os.path.exists(so_path):
        so_path = "csrc/fused_iouring_registered_pipesplice.so"
    if not os.path.exists(so_path):
        pytest.skip("registered pipesplice so not found")

    lib = ctypes.CDLL(so_path)
    lib.iouring_registered_pipesplice_init.argtypes = [ctypes.c_uint32]
    lib.iouring_registered_pipesplice_init.restype = ctypes.c_void_p

    lib.iouring_registered_pipesplice_prep_splice.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int64,
        ctypes.c_int, ctypes.c_int64, ctypes.c_uint,
        ctypes.c_uint, ctypes.c_uint64
    ]
    lib.iouring_registered_pipesplice_prep_splice.restype = ctypes.c_int

    lib.iouring_registered_pipesplice_submit.argtypes = [ctypes.c_void_p]
    lib.iouring_registered_pipesplice_submit.restype = ctypes.c_int

    lib.iouring_registered_pipesplice_reap.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_registered_pipesplice_reap.restype = ctypes.c_int

    lib.iouring_registered_pipesplice_free.argtypes = [ctypes.c_void_p]
    lib.iouring_registered_pipesplice_free.restype = None

    eng = lib.iouring_registered_pipesplice_init(16)
    assert eng is not None

    p1_r, p1_w = os.pipe()
    p2_r, p2_w = os.pipe()

    payload = b"REGISTERED_PIPE_SPLICE_ZERO_SYSCALL_500M_BENCHMARK" * 4
    os.write(p1_w, payload)

    try:
        prep_ret = lib.iouring_registered_pipesplice_prep_splice(
            eng, p1_r, -1, p2_w, -1, len(payload), 0, 0x500500
        )
        assert prep_ret == 0

        sub_ret = lib.iouring_registered_pipesplice_submit(eng)
        assert sub_ret >= 0

        res = ctypes.c_int(0)
        ud = ctypes.c_uint64(0)
        reap_ret = lib.iouring_registered_pipesplice_reap(eng, ctypes.byref(res), ctypes.byref(ud))
        assert reap_ret == 0
        assert res.value == len(payload)
        assert ud.value == 0x500500

        received = os.read(p2_r, len(payload))
        assert received == payload
    finally:
        os.close(p1_r)
        os.close(p1_w)
        os.close(p2_r)
        os.close(p2_w)
        lib.iouring_registered_pipesplice_free(eng)


def test_iouring_epoll_eventfd_ring_correctness():
    so_path = "csrc/libfused_iouring_epoll_eventfd_ring.so"
    if not os.path.exists(so_path):
        so_path = "csrc/fused_iouring_epoll_eventfd_ring.so"
    if not os.path.exists(so_path):
        pytest.skip("eventfd ring so not found")

    lib = ctypes.CDLL(so_path)
    lib.iouring_eventfd_ring_init.argtypes = [ctypes.c_uint32, ctypes.c_int]
    lib.iouring_eventfd_ring_init.restype = ctypes.c_void_p

    lib.iouring_eventfd_ring_submit_nop.argtypes = [ctypes.c_void_p, ctypes.c_uint64]
    lib.iouring_eventfd_ring_submit_nop.restype = ctypes.c_int

    lib.iouring_eventfd_ring_reap.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_eventfd_ring_reap.restype = ctypes.c_int

    lib.iouring_eventfd_ring_free.argtypes = [ctypes.c_void_p]
    lib.iouring_eventfd_ring_free.restype = None

    import struct
    efd = os.eventfd(0, os.EFD_NONBLOCK)
    eng = lib.iouring_eventfd_ring_init(16, efd)
    assert eng is not None

    try:
        sub_ret = lib.iouring_eventfd_ring_submit_nop(eng, 0x8888)
        assert sub_ret == 0

        res = ctypes.c_int(-1)
        ud = ctypes.c_uint64(0)
        reap_ret = lib.iouring_eventfd_ring_reap(eng, ctypes.byref(res), ctypes.byref(ud))
        assert reap_ret == 0
        assert res.value == 0
        assert ud.value == 0x8888

        # Verify kernel signaled eventfd
        val_bytes = os.read(efd, 8)
        val = struct.unpack("Q", val_bytes)[0]
        assert val >= 1
    finally:
        lib.iouring_eventfd_ring_free(eng)
        os.close(efd)


def test_iouring_bpf_memtrace_correctness():
    so_path = "csrc/libfused_iouring_bpf_memtrace_ring.so"
    if not os.path.exists(so_path):
        so_path = "csrc/fused_iouring_bpf_memtrace_ring.so"
    if not os.path.exists(so_path):
        pytest.skip("bpf memtrace ring so not found")

    lib = ctypes.CDLL(so_path)
    lib.iouring_bpf_memtrace_init.argtypes = [ctypes.c_uint32]
    lib.iouring_bpf_memtrace_init.restype = ctypes.c_void_p

    lib.iouring_bpf_memtrace_log_event.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64
    ]
    lib.iouring_bpf_memtrace_log_event.restype = ctypes.c_int

    lib.iouring_bpf_memtrace_get_summary.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_bpf_memtrace_get_summary.restype = ctypes.c_int

    lib.iouring_bpf_memtrace_free.argtypes = [ctypes.c_void_p]
    lib.iouring_bpf_memtrace_free.restype = None

    eng = lib.iouring_bpf_memtrace_init(128)
    assert eng is not None

    try:
        # Log 3 events
        ret1 = lib.iouring_bpf_memtrace_log_event(eng, 1, 0x1000, 4096, 250)
        ret2 = lib.iouring_bpf_memtrace_log_event(eng, 2, 0x2000, 8192, 350)
        ret3 = lib.iouring_bpf_memtrace_log_event(eng, 1, 0x3000, 4096, 300)
        assert ret1 == 0 and ret2 == 0 and ret3 == 0

        tot_ev = ctypes.c_uint64(0)
        tot_bytes = ctypes.c_uint64(0)
        avg_lat = ctypes.c_uint64(0)

        s_ret = lib.iouring_bpf_memtrace_get_summary(
            eng, ctypes.byref(tot_ev), ctypes.byref(tot_bytes), ctypes.byref(avg_lat)
        )
        assert s_ret == 0
        assert tot_ev.value == 3
        assert tot_bytes.value == (4096 + 8192 + 4096)
        assert avg_lat.value == ((250 + 350 + 300) // 3)
    finally:
        lib.iouring_bpf_memtrace_free(eng)

def test_iouring_dmabuf_ring_correctness():
    so_path = "csrc/fused_iouring_dmabuf_ring.so"
    assert os.path.exists(so_path), "Shared library does not exist"
    lib = ctypes.CDLL(so_path)

    lib.iouring_dmabuf_ring_init.argtypes = [ctypes.c_uint32]
    lib.iouring_dmabuf_ring_init.restype = ctypes.c_void_p

    lib.iouring_dmabuf_ring_register_buf.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint64,
        ctypes.c_uint64,
        ctypes.c_uint32
    ]
    lib.iouring_dmabuf_ring_register_buf.restype = ctypes.c_int

    lib.iouring_dmabuf_ring_submit_transfer.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint64,
        ctypes.c_uint64
    ]
    lib.iouring_dmabuf_ring_submit_transfer.restype = ctypes.c_int

    lib.iouring_dmabuf_ring_get_stats.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_dmabuf_ring_get_stats.restype = ctypes.c_int

    lib.iouring_dmabuf_ring_free.argtypes = [ctypes.c_void_p]
    lib.iouring_dmabuf_ring_free.restype = None

    eng = lib.iouring_dmabuf_ring_init(64)
    assert eng is not None

    try:
        # Register buffer at slot 0
        r_ret = lib.iouring_dmabuf_ring_register_buf(eng, 0, 10, 0, 1048576, 1)
        assert r_ret == 0

        # Submit transfer: 1MB in 100,000 ns (0.0001 sec) -> ~10,000 MB/s
        t_ret = lib.iouring_dmabuf_ring_submit_transfer(eng, 0, 1048576, 100000)
        assert t_ret == 0

        tot_trans = ctypes.c_uint64(0)
        tot_bytes = ctypes.c_uint64(0)
        peak_bw = ctypes.c_uint64(0)

        s_ret = lib.iouring_dmabuf_ring_get_stats(
            eng, ctypes.byref(tot_trans), ctypes.byref(tot_bytes), ctypes.byref(peak_bw)
        )
        assert s_ret == 0
        assert tot_trans.value == 1
        assert tot_bytes.value == 1048576
        assert peak_bw.value >= 9000
    finally:
        lib.iouring_dmabuf_ring_free(eng)

def test_iouring_futex_waitv_ring_correctness():
    so_path = "csrc/fused_iouring_futex_waitv_ring.so"
    assert os.path.exists(so_path), "Shared library does not exist"
    lib = ctypes.CDLL(so_path)

    lib.iouring_futex_waitv_init.argtypes = [ctypes.c_uint32]
    lib.iouring_futex_waitv_init.restype = ctypes.c_void_p

    lib.iouring_futex_waitv_register_target.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_uint32,
        ctypes.c_uint32
    ]
    lib.iouring_futex_waitv_register_target.restype = ctypes.c_int

    lib.iouring_futex_waitv_submit_wait.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint64
    ]
    lib.iouring_futex_waitv_submit_wait.restype = ctypes.c_int

    lib.iouring_futex_waitv_wake.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32
    ]
    lib.iouring_futex_waitv_wake.restype = ctypes.c_int

    lib.iouring_futex_waitv_get_stats.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_futex_waitv_get_stats.restype = ctypes.c_int

    lib.iouring_futex_waitv_free.argtypes = [ctypes.c_void_p]
    lib.iouring_futex_waitv_free.restype = None

    eng = lib.iouring_futex_waitv_init(32)
    assert eng is not None

    try:
        val0 = ctypes.c_uint32(100)
        val1 = ctypes.c_uint32(200)

        r0 = lib.iouring_futex_waitv_register_target(eng, 0, ctypes.byref(val0), 100, 0)
        r1 = lib.iouring_futex_waitv_register_target(eng, 1, ctypes.byref(val1), 200, 0)
        assert r0 == 0 and r1 == 0

        # Wait when both match expected -> 0 (sleeping / no target changed yet)
        w_ret = lib.iouring_futex_waitv_submit_wait(eng, 2, 1000)
        assert w_ret == 0

        # Wake target 1 with new value 201
        wake_ret = lib.iouring_futex_waitv_wake(eng, 1, 201)
        assert wake_ret == 0
        assert val1.value == 201

        # Now wait detects target 1 changed -> returns index 1
        w_ret2 = lib.iouring_futex_waitv_submit_wait(eng, 2, 1000)
        assert w_ret2 == 1

        tot_waits = ctypes.c_uint64(0)
        tot_wakes = ctypes.c_uint64(0)
        timeouts = ctypes.c_uint64(0)
        s_ret = lib.iouring_futex_waitv_get_stats(
            eng, ctypes.byref(tot_waits), ctypes.byref(tot_wakes), ctypes.byref(timeouts)
        )
        assert s_ret == 0
        assert tot_waits.value == 2
        assert tot_wakes.value == 1
    finally:
        lib.iouring_futex_waitv_free(eng)

def test_iouring_send_zc_notify_ring_correctness():
    so_path = "csrc/fused_iouring_send_zc_notify_ring.so"
    assert os.path.exists(so_path), "Shared library does not exist"
    lib = ctypes.CDLL(so_path)

    lib.iouring_send_zc_notify_init.argtypes = [ctypes.c_uint32]
    lib.iouring_send_zc_notify_init.restype = ctypes.c_void_p

    lib.iouring_send_zc_register_buf.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint64
    ]
    lib.iouring_send_zc_register_buf.restype = ctypes.c_int

    lib.iouring_send_zc_submit_send.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint64,
        ctypes.c_uint32
    ]
    lib.iouring_send_zc_submit_send.restype = ctypes.c_int

    lib.iouring_send_zc_flush_notifs.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32)
    ]
    lib.iouring_send_zc_flush_notifs.restype = ctypes.c_int

    lib.iouring_send_zc_get_stats.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_send_zc_get_stats.restype = ctypes.c_int

    lib.iouring_send_zc_free.argtypes = [ctypes.c_void_p]
    lib.iouring_send_zc_free.restype = None

    eng = lib.iouring_send_zc_notify_init(16)
    assert eng is not None

    try:
        dummy_buf = (ctypes.c_char * 4096)()
        reg_ret = lib.iouring_send_zc_register_buf(eng, 0, ctypes.byref(dummy_buf), 4096)
        assert reg_ret == 0

        # Submit zero-copy send
        send_ret = lib.iouring_send_zc_submit_send(eng, 0, 2048, 0)
        assert send_ret == 0

        # Flush notifications
        completed = ctypes.c_uint32(0)
        flush_ret = lib.iouring_send_zc_flush_notifs(eng, ctypes.byref(completed))
        assert flush_ret == 0
        assert completed.value == 1

        tot_sends = ctypes.c_uint64(0)
        tot_bytes = ctypes.c_uint64(0)
        tot_notifs = ctypes.c_uint64(0)
        s_ret = lib.iouring_send_zc_get_stats(
            eng, ctypes.byref(tot_sends), ctypes.byref(tot_bytes), ctypes.byref(tot_notifs)
        )
        assert s_ret == 0
        assert tot_sends.value == 1
        assert tot_bytes.value == 2048
        assert tot_notifs.value == 1
    finally:
        lib.iouring_send_zc_free(eng)


def test_iouring_workstealing_multiring_correctness():
    so_path = "csrc/libfused_iouring_workstealing_multiring.so"
    if not os.path.exists(so_path):
        pytest.skip(f"{so_path} not found")

    lib = ctypes.CDLL(so_path)
    lib.iouring_workstealing_init.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    lib.iouring_workstealing_init.restype = ctypes.c_void_p

    lib.iouring_workstealing_submit.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint32
    ]
    lib.iouring_workstealing_submit.restype = ctypes.c_int

    lib.iouring_workstealing_balance.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)
    ]
    lib.iouring_workstealing_balance.restype = ctypes.c_int

    lib.iouring_workstealing_complete.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)
    ]
    lib.iouring_workstealing_complete.restype = ctypes.c_int

    lib.iouring_workstealing_get_stats.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_workstealing_get_stats.restype = ctypes.c_int

    lib.iouring_workstealing_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_workstealing_destroy.restype = None

    num_rings = 4
    ring_cap = 16
    eng = lib.iouring_workstealing_init(num_rings, ring_cap)
    assert eng is not None

    try:
        # Submit 6 jobs to ring 0 (load = 6), 0 jobs to ring 1 (load = 0)
        for j in range(6):
            ret = lib.iouring_workstealing_submit(eng, 0, 100 + j, 1024, 1)
            assert ret == 0

        # Run workstealing balance: should steal (6 - 0) / 2 = 3 jobs from ring 0 to ring 1
        stolen = ctypes.c_uint32(0)
        b_ret = lib.iouring_workstealing_balance(eng, ctypes.byref(stolen))
        assert b_ret == 0
        assert stolen.value == 3

        # Complete jobs on ring 1 (stolen jobs)
        act1 = ctypes.c_uint32(0)
        c_ret1 = lib.iouring_workstealing_complete(eng, 1, 10, ctypes.byref(act1))
        assert c_ret1 == 0
        assert act1.value == 3

        # Complete jobs on ring 0 (remaining jobs)
        act0 = ctypes.c_uint32(0)
        c_ret0 = lib.iouring_workstealing_complete(eng, 0, 10, ctypes.byref(act0))
        assert c_ret0 == 0
        assert act0.value == 3

        # Verify stats
        tot_jobs = ctypes.c_uint64(0)
        tot_stolen = ctypes.c_uint64(0)
        tot_bytes = ctypes.c_uint64(0)
        s_ret = lib.iouring_workstealing_get_stats(
            eng, ctypes.byref(tot_jobs), ctypes.byref(tot_stolen), ctypes.byref(tot_bytes)
        )
        assert s_ret == 0
        assert tot_jobs.value == 6
        assert tot_stolen.value == 3
        assert tot_bytes.value == 6 * 1024
    finally:
        lib.iouring_workstealing_destroy(eng)


def test_iouring_direct_nvme_streaming_correctness():
    so_path = "csrc/libfused_iouring_direct_nvme_streaming.so"
    if not os.path.exists(so_path):
        pytest.skip(f"{so_path} not found")

    lib = ctypes.CDLL(so_path)
    lib.iouring_nvme_streaming_init.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    lib.iouring_nvme_streaming_init.restype = ctypes.c_void_p

    lib.iouring_nvme_streaming_register_block.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint64
    ]
    lib.iouring_nvme_streaming_register_block.restype = ctypes.c_int

    lib.iouring_nvme_streaming_submit_io.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint64, ctypes.c_uint32, ctypes.c_int
    ]
    lib.iouring_nvme_streaming_submit_io.restype = ctypes.c_int

    lib.iouring_nvme_streaming_reap_completions.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)
    ]
    lib.iouring_nvme_streaming_reap_completions.restype = ctypes.c_int

    lib.iouring_nvme_streaming_get_telemetry.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_nvme_streaming_get_telemetry.restype = ctypes.c_int

    lib.iouring_nvme_streaming_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_nvme_streaming_destroy.restype = None

    q_depth = 16
    sector_sz = 4096
    eng = lib.iouring_nvme_streaming_init(q_depth, sector_sz)
    assert eng is not None

    try:
        dummy_buf = (ctypes.c_char * 8192)()
        r_ret = lib.iouring_nvme_streaming_register_block(eng, 0, ctypes.byref(dummy_buf), 8192)
        assert r_ret == 0

        # Submit read of 2 sectors (8192 bytes)
        sub_ret = lib.iouring_nvme_streaming_submit_io(eng, 0, 1024, 2, 0)
        assert sub_ret == 0

        # Reap completions
        reaped = ctypes.c_uint32(0)
        reap_ret = lib.iouring_nvme_streaming_reap_completions(eng, 10, ctypes.byref(reaped))
        assert reap_ret == 0
        assert reaped.value == 1

        # Check telemetry
        total_ops = ctypes.c_uint64(0)
        total_bytes = ctypes.c_uint64(0)
        overflows = ctypes.c_uint64(0)
        t_ret = lib.iouring_nvme_streaming_get_telemetry(
            eng, ctypes.byref(total_ops), ctypes.byref(total_bytes), ctypes.byref(overflows)
        )
        assert t_ret == 0
        assert total_ops.value == 1
        assert total_bytes.value == 8192
        assert overflows.value == 0
    finally:
        lib.iouring_nvme_streaming_destroy(eng)


def test_iouring_vectored_socket_splice_fifo_correctness():
    so_path = "csrc/libfused_iouring_vectored_socket_splice_fifo.so"
    if not os.path.exists(so_path):
        pytest.skip(f"{so_path} not found")

    lib = ctypes.CDLL(so_path)
    lib.iouring_splice_fifo_init.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    lib.iouring_splice_fifo_init.restype = ctypes.c_void_p

    lib.iouring_splice_fifo_enqueue.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32
    ]
    lib.iouring_splice_fifo_enqueue.restype = ctypes.c_int

    lib.iouring_splice_fifo_dequeue.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)
    ]
    lib.iouring_splice_fifo_dequeue.restype = ctypes.c_int

    lib.iouring_splice_fifo_splice_sockets.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)
    ]
    lib.iouring_splice_fifo_splice_sockets.restype = ctypes.c_int

    lib.iouring_splice_fifo_get_telemetry.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_splice_fifo_get_telemetry.restype = ctypes.c_int

    lib.iouring_splice_fifo_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_splice_fifo_destroy.restype = None

    cap = 1024
    eng = lib.iouring_splice_fifo_init(cap, cap)
    assert eng is not None

    try:
        data = b"TATE_LOCAL_DUALITY_AND_POITOU_TATE_EXACT_STREAM_PACKET"
        e_ret = lib.iouring_splice_fifo_enqueue(eng, data, len(data))
        assert e_ret == 0

        out_buf = (ctypes.c_char * len(data))()
        actual = ctypes.c_uint32(0)
        d_ret = lib.iouring_splice_fifo_dequeue(eng, out_buf, len(data), ctypes.byref(actual))
        assert d_ret == 0
        assert actual.value == len(data)
        assert bytes(out_buf.raw[:actual.value]) == data

        # Test socket splicing
        spliced = ctypes.c_uint32(0)
        sp_ret = lib.iouring_splice_fifo_splice_sockets(eng, 3, 4, 4096, ctypes.byref(spliced))
        assert sp_ret == 0
        assert spliced.value == 4096

        # Check telemetry
        tot_enq = ctypes.c_uint64(0)
        tot_deq = ctypes.c_uint64(0)
        tot_spl = ctypes.c_uint64(0)
        t_ret = lib.iouring_splice_fifo_get_telemetry(
            eng, ctypes.byref(tot_enq), ctypes.byref(tot_deq), ctypes.byref(tot_spl)
        )
        assert t_ret == 0
        assert tot_enq.value == len(data)
        assert tot_deq.value == len(data)
        assert tot_spl.value == 4096
    finally:
        lib.iouring_splice_fifo_destroy(eng)


def test_iouring_page_pool_allocator_correctness():
    so_path = "csrc/libfused_iouring_page_pool_allocator.so"
    if not os.path.exists(so_path):
        pytest.skip("libfused_iouring_page_pool_allocator.so not compiled")

    lib = ctypes.CDLL(so_path)
    lib.iouring_page_pool_init.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    lib.iouring_page_pool_init.restype = ctypes.c_void_p

    lib.iouring_page_pool_allocate.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_void_p)
    ]
    lib.iouring_page_pool_allocate.restype = ctypes.c_int

    lib.iouring_page_pool_release.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.iouring_page_pool_release.restype = ctypes.c_int

    lib.iouring_page_pool_register_ring_buffers.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.iouring_page_pool_register_ring_buffers.restype = ctypes.c_int

    lib.iouring_page_pool_get_stats.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_page_pool_get_stats.restype = ctypes.c_int

    lib.iouring_page_pool_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_page_pool_destroy.restype = None

    num_pages = 64
    page_size = 4096
    eng = lib.iouring_page_pool_init(num_pages, page_size)
    assert eng is not None

    try:
        # Register ring buffers
        reg_ret = lib.iouring_page_pool_register_ring_buffers(eng, 5)
        assert reg_ret == 0

        # Allocate page 0
        p_idx = ctypes.c_uint32(0)
        p_ptr = ctypes.c_void_p(0)
        a_ret = lib.iouring_page_pool_allocate(eng, ctypes.byref(p_idx), ctypes.byref(p_ptr))
        assert a_ret == 0
        assert p_idx.value == 0
        assert p_ptr.value != 0

        # Write to allocated memory
        ctypes.memset(p_ptr, 0x42, 64)

        # Allocate page 1
        p_idx2 = ctypes.c_uint32(0)
        p_ptr2 = ctypes.c_void_p(0)
        a_ret2 = lib.iouring_page_pool_allocate(eng, ctypes.byref(p_idx2), ctypes.byref(p_ptr2))
        assert a_ret2 == 0
        assert p_idx2.value == 1

        # Check stats
        tot_p = ctypes.c_uint32(0)
        alloc_p = ctypes.c_uint32(0)
        tot_alloc = ctypes.c_uint64(0)
        tot_free = ctypes.c_uint64(0)
        s_ret = lib.iouring_page_pool_get_stats(
            eng, ctypes.byref(tot_p), ctypes.byref(alloc_p),
            ctypes.byref(tot_alloc), ctypes.byref(tot_free)
        )
        assert s_ret == 0
        assert tot_p.value == num_pages
        assert alloc_p.value == 2
        assert tot_alloc.value == 2
        assert tot_free.value == 0

        # Release page 0
        rel_ret = lib.iouring_page_pool_release(eng, p_idx.value)
        assert rel_ret == 0

        # Stats after release
        s_ret2 = lib.iouring_page_pool_get_stats(
            eng, ctypes.byref(tot_p), ctypes.byref(alloc_p),
            ctypes.byref(tot_alloc), ctypes.byref(tot_free)
        )
        assert s_ret2 == 0
        assert alloc_p.value == 1
        assert tot_free.value == 1

        # Double free returns error
        assert lib.iouring_page_pool_release(eng, p_idx.value) == -3
    finally:
        lib.iouring_page_pool_destroy(eng)


def test_iouring_socket_multiplexer_correctness():
    so_path = "csrc/libfused_iouring_socket_multiplexer.so"
    if not os.path.exists(so_path):
        pytest.skip("libfused_iouring_socket_multiplexer.so not compiled")

    lib = ctypes.CDLL(so_path)
    lib.iouring_socket_multiplexer_init.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    lib.iouring_socket_multiplexer_init.restype = ctypes.c_void_p

    lib.iouring_socket_multiplexer_register_socket.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
    lib.iouring_socket_multiplexer_register_socket.restype = ctypes.c_int

    lib.iouring_socket_multiplexer_unregister_socket.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.iouring_socket_multiplexer_unregister_socket.restype = ctypes.c_int

    lib.iouring_socket_multiplexer_route.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
    lib.iouring_socket_multiplexer_route.restype = ctypes.c_int

    lib.iouring_socket_multiplexer_broadcast.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)
    ]
    lib.iouring_socket_multiplexer_broadcast.restype = ctypes.c_int

    lib.iouring_socket_multiplexer_get_stats.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_socket_multiplexer_get_stats.restype = ctypes.c_int

    lib.iouring_socket_multiplexer_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_socket_multiplexer_destroy.restype = None

    max_sock = 32
    ring_entries = 64
    mux = lib.iouring_socket_multiplexer_init(max_sock, ring_entries)
    assert mux is not None

    try:
        # Register 2 sockets
        r1 = lib.iouring_socket_multiplexer_register_socket(mux, 10, 0)
        assert r1 == 0
        r2 = lib.iouring_socket_multiplexer_register_socket(mux, 11, 1)
        assert r2 == 0

        # Route a single message to socket 0
        payload = b"FONTAINE_MAZUR_GEOMETRIC_COCYCLE_PACKET"
        rt = lib.iouring_socket_multiplexer_route(mux, 0, payload, len(payload))
        assert rt == 0

        # Broadcast message to all active sockets (2 sockets)
        sent = ctypes.c_uint32(0)
        bc = lib.iouring_socket_multiplexer_broadcast(mux, payload, len(payload), ctypes.byref(sent))
        assert bc == 0
        assert sent.value == 2

        # Verify stats
        act = ctypes.c_uint32(0)
        pkts = ctypes.c_uint64(0)
        bytes_tot = ctypes.c_uint64(0)
        st = lib.iouring_socket_multiplexer_get_stats(
            mux, ctypes.byref(act), ctypes.byref(pkts), ctypes.byref(bytes_tot)
        )
        assert st == 0
        assert act.value == 2
        assert pkts.value == 3  # 1 route + 2 broadcast
        assert bytes_tot.value == 3 * len(payload)

        # Unregister socket 1
        unreg = lib.iouring_socket_multiplexer_unregister_socket(mux, 1)
        assert unreg == 0

        st2 = lib.iouring_socket_multiplexer_get_stats(
            mux, ctypes.byref(act), ctypes.byref(pkts), ctypes.byref(bytes_tot)
        )
        assert st2 == 0
        assert act.value == 1
    finally:
        lib.iouring_socket_multiplexer_destroy(mux)


def test_iouring_socket_buf_recycler_correctness():
    so_path = "csrc/libfused_iouring_socket_buf_recycler.so"
    if not os.path.exists(so_path):
        pytest.skip("libfused_iouring_socket_buf_recycler.so not compiled")

    lib = ctypes.CDLL(so_path)
    lib.iouring_socket_buf_recycler_init.argtypes = [ctypes.c_uint16, ctypes.c_uint32, ctypes.c_uint32]
    lib.iouring_socket_buf_recycler_init.restype = ctypes.c_void_p

    lib.iouring_socket_buf_recycler_acquire.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint16),
        ctypes.POINTER(ctypes.c_void_p)
    ]
    lib.iouring_socket_buf_recycler_acquire.restype = ctypes.c_int

    lib.iouring_socket_buf_recycler_replenish.argtypes = [ctypes.c_void_p, ctypes.c_uint16]
    lib.iouring_socket_buf_recycler_replenish.restype = ctypes.c_int

    lib.iouring_socket_buf_recycler_multishot_recv.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
    lib.iouring_socket_buf_recycler_multishot_recv.restype = ctypes.c_int

    lib.iouring_socket_buf_recycler_get_stats.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_socket_buf_recycler_get_stats.restype = ctypes.c_int

    lib.iouring_socket_buf_recycler_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_socket_buf_recycler_destroy.restype = None

    bgid = 1
    num_bufs = 64
    buf_size = 4096
    rec = lib.iouring_socket_buf_recycler_init(bgid, num_bufs, buf_size)
    assert rec is not None

    try:
        # Acquire a buffer
        bid = ctypes.c_uint16(0)
        ptr = ctypes.c_void_p(0)
        acq_ret = lib.iouring_socket_buf_recycler_acquire(rec, ctypes.byref(bid), ctypes.byref(ptr))
        assert acq_ret == 0
        assert bid.value == 0
        assert ptr.value != 0

        # Replenish the buffer
        rep_ret = lib.iouring_socket_buf_recycler_replenish(rec, bid.value)
        assert rep_ret == 0

        # Multishot simulated batch receive of 10 buffers
        m_ret = lib.iouring_socket_buf_recycler_multishot_recv(rec, 4, 10)
        assert m_ret == 0

        # Check telemetry stats
        avail = ctypes.c_uint32(0)
        tot_rep = ctypes.c_uint64(0)
        tot_acq = ctypes.c_uint64(0)
        st = lib.iouring_socket_buf_recycler_get_stats(
            rec, ctypes.byref(avail), ctypes.byref(tot_rep), ctypes.byref(tot_acq)
        )
        assert st == 0
        assert avail.value == num_bufs
        assert tot_rep.value == 11
        assert tot_acq.value == 11

        # Double replenish returns error
        assert lib.iouring_socket_buf_recycler_replenish(rec, bid.value) == -3
    finally:
        lib.iouring_socket_buf_recycler_destroy(rec)


def test_iouring_numa_page_distributor_correctness():
    so_path = "csrc/libfused_iouring_numa_page_distributor.so"
    if not os.path.exists(so_path):
        pytest.skip("io_uring NUMA page distributor library not built")

    lib = ctypes.CDLL(so_path)
    lib.iouring_numa_distributor_init.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
    lib.iouring_numa_distributor_init.restype = ctypes.c_void_p

    lib.iouring_numa_distributor_allocate.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_void_p)
    ]
    lib.iouring_numa_distributor_allocate.restype = ctypes.c_int

    lib.iouring_numa_distributor_release.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.iouring_numa_distributor_release.restype = ctypes.c_int

    lib.iouring_numa_distributor_stats.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_numa_distributor_stats.restype = ctypes.c_int

    lib.iouring_numa_distributor_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_numa_distributor_destroy.restype = None

    num_nodes = 2
    pages_per_node = 4
    page_size = 4096

    dist = lib.iouring_numa_distributor_init(num_nodes, pages_per_node, page_size)
    assert dist is not None

    try:
        # Allocate all 4 pages on node 0
        allocated_ids_node0 = []
        for _ in range(4):
            pid = ctypes.c_uint32(0)
            paddr = ctypes.c_void_p(0)
            ret = lib.iouring_numa_distributor_allocate(dist, 0, ctypes.byref(pid), ctypes.byref(paddr))
            assert ret == 0 # Local NUMA hit
            allocated_ids_node0.append(pid.value)

        # 5th allocation requesting node 0 triggers fallback migration to node 1
        pid_remote = ctypes.c_uint32(0)
        paddr_remote = ctypes.c_void_p(0)
        ret_mig = lib.iouring_numa_distributor_allocate(dist, 0, ctypes.byref(pid_remote), ctypes.byref(paddr_remote))
        assert ret_mig == 1 # Remote node migration
        assert pid_remote.value >= 4 # In node 1 range

        # Check stats: 4 hits on node 0, 1 migration to node 1
        avail = ctypes.c_uint32(0)
        hits = ctypes.c_uint64(0)
        migrations = ctypes.c_uint64(0)
        st = lib.iouring_numa_distributor_stats(dist, ctypes.byref(avail), ctypes.byref(hits), ctypes.byref(migrations))
        assert st == 0
        assert avail.value == 3
        assert hits.value == 4
        assert migrations.value == 1

        # Release one page and reallocate
        rel_ret = lib.iouring_numa_distributor_release(dist, allocated_ids_node0[0])
        assert rel_ret == 0

        # Now allocate on node 0 succeeds with local hit
        pid_re = ctypes.c_uint32(0)
        paddr_re = ctypes.c_void_p(0)
        ret_re = lib.iouring_numa_distributor_allocate(dist, 0, ctypes.byref(pid_re), ctypes.byref(paddr_re))
        assert ret_re == 0
        assert pid_re.value == allocated_ids_node0[0]

    finally:
        lib.iouring_numa_distributor_destroy(dist)


def test_iouring_zc_rx_ring_correctness():
    so_path = "csrc/libfused_iouring_zc_rx_ring.so"
    if not os.path.exists(so_path):
        pytest.skip("io_uring ZC RX ring library not built")

    lib = ctypes.CDLL(so_path)
    lib.iouring_zc_rx_ring_init.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
    lib.iouring_zc_rx_ring_init.restype = ctypes.c_void_p

    lib.iouring_zc_rx_ring_produce.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_void_p)
    ]
    lib.iouring_zc_rx_ring_produce.restype = ctypes.c_int

    lib.iouring_zc_rx_ring_consume.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_void_p)
    ]
    lib.iouring_zc_rx_ring_consume.restype = ctypes.c_int

    lib.iouring_zc_rx_ring_stats.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_zc_rx_ring_stats.restype = ctypes.c_int

    lib.iouring_zc_rx_ring_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_zc_rx_ring_destroy.restype = None

    cap = 16
    hdr_size = 64
    pay_size = 1024

    ring = lib.iouring_zc_rx_ring_init(cap, hdr_size, pay_size)
    assert ring is not None

    try:
        # Produce 3 packets
        for i in range(3):
            pkt_id = ctypes.c_uint32(0)
            pay_ptr = ctypes.c_void_p(0)
            ret = lib.iouring_zc_rx_ring_produce(ring, 32, 512, ctypes.byref(pkt_id), ctypes.byref(pay_ptr))
            assert ret == 0
            assert pkt_id.value == i
            assert pay_ptr.value != 0

        # Check stats
        avail = ctypes.c_uint32(0)
        tot_rx = ctypes.c_uint64(0)
        tot_c = ctypes.c_uint64(0)
        zc_b = ctypes.c_uint64(0)
        st = lib.iouring_zc_rx_ring_stats(
            ring, ctypes.byref(avail), ctypes.byref(tot_rx), ctypes.byref(tot_c), ctypes.byref(zc_b)
        )
        assert st == 0
        assert tot_rx.value == 3
        assert zc_b.value == 3 * 512
        assert avail.value == cap - 1 - 3

        # Consume 2 packets
        for i in range(2):
            c_pkt_id = ctypes.c_uint32(0)
            c_pay_len = ctypes.c_uint32(0)
            c_pay_ptr = ctypes.c_void_p(0)
            c_ret = lib.iouring_zc_rx_ring_consume(
                ring, ctypes.byref(c_pkt_id), ctypes.byref(c_pay_len), ctypes.byref(c_pay_ptr)
            )
            assert c_ret == 0
            assert c_pkt_id.value == i
            assert c_pay_len.value == 512
            assert c_pay_ptr.value != 0

        # Consume 1 more packet
        c_pkt_id = ctypes.c_uint32(0)
        c_pay_len = ctypes.c_uint32(0)
        c_pay_ptr = ctypes.c_void_p(0)
        assert lib.iouring_zc_rx_ring_consume(ring, ctypes.byref(c_pkt_id), ctypes.byref(c_pay_len), ctypes.byref(c_pay_ptr)) == 0

        # Ring now empty
        assert lib.iouring_zc_rx_ring_consume(ring, ctypes.byref(c_pkt_id), ctypes.byref(c_pay_len), ctypes.byref(c_pay_ptr)) == -2
    finally:
        lib.iouring_zc_rx_ring_destroy(ring)


def test_iouring_zc_tx_burst_correctness():
    so_path = "csrc/libfused_iouring_zc_tx_burst.so"
    if not os.path.exists(so_path):
        pytest.skip("io_uring ZC TX burst library not built")

    lib = ctypes.CDLL(so_path)
    lib.iouring_zc_tx_burst_init.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    lib.iouring_zc_tx_burst_init.restype = ctypes.c_void_p

    lib.iouring_zc_tx_burst_enqueue.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_void_p)
    ]
    lib.iouring_zc_tx_burst_enqueue.restype = ctypes.c_int

    lib.iouring_zc_tx_burst_submit.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_zc_tx_burst_submit.restype = ctypes.c_int

    lib.iouring_zc_tx_burst_stats.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64)
    ]
    lib.iouring_zc_tx_burst_stats.restype = ctypes.c_int

    lib.iouring_zc_tx_burst_destroy.argtypes = [ctypes.c_void_p]
    lib.iouring_zc_tx_burst_destroy.restype = None

    cap = 32
    pkt_size = 2048

    burst = lib.iouring_zc_tx_burst_init(cap, pkt_size)
    assert burst is not None

    try:
        # Enqueue 5 packets
        for i in range(5):
            pkt_id = ctypes.c_uint32(0)
            buf_ptr = ctypes.c_void_p(0)
            ret = lib.iouring_zc_tx_burst_enqueue(burst, 1024, ctypes.byref(pkt_id), ctypes.byref(buf_ptr))
            assert ret == 0
            assert pkt_id.value == i
            assert buf_ptr.value != 0

        # Check stats before burst submission
        avail = ctypes.c_uint32(0)
        tot_enq = ctypes.c_uint64(0)
        tot_sub = ctypes.c_uint64(0)
        tot_bytes = ctypes.c_uint64(0)
        st = lib.iouring_zc_tx_burst_stats(
            burst, ctypes.byref(avail), ctypes.byref(tot_enq), ctypes.byref(tot_sub), ctypes.byref(tot_bytes)
        )
        assert st == 0
        assert tot_enq.value == 5
        assert tot_sub.value == 0
        assert avail.value == cap - 1 - 5

        # Submit burst of max 3 packets
        burst_cnt = ctypes.c_uint32(0)
        burst_bytes = ctypes.c_uint64(0)
        sub_ret = lib.iouring_zc_tx_burst_submit(burst, 3, ctypes.byref(burst_cnt), ctypes.byref(burst_bytes))
        assert sub_ret == 0
        assert burst_cnt.value == 3
        assert burst_bytes.value == 3 * 1024

        # Submit remaining 2 packets
        sub_ret2 = lib.iouring_zc_tx_burst_submit(burst, 10, ctypes.byref(burst_cnt), ctypes.byref(burst_bytes))
        assert sub_ret2 == 0
        assert burst_cnt.value == 2
        assert burst_bytes.value == 2 * 1024

        # Check final stats
        lib.iouring_zc_tx_burst_stats(
            burst, ctypes.byref(avail), ctypes.byref(tot_enq), ctypes.byref(tot_sub), ctypes.byref(tot_bytes)
        )
        assert tot_sub.value == 5
        assert tot_bytes.value == 5 * 1024
        assert avail.value == cap - 1
    finally:
        lib.iouring_zc_tx_burst_destroy(burst)


def test_iouring_kernel_page_migrator_correctness():
    so_path = "csrc/libfused_iouring_kernel_page_migrator.so"
    if not os.path.exists(so_path):
        pytest.skip("Kernel page migrator engine not compiled")

    lib = ctypes.CDLL(so_path)
    lib.iouring_kernel_page_migrator_init.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32]
    lib.iouring_kernel_page_migrator_init.restype = ctypes.c_void_p

    lib.iouring_kernel_page_migrator_queue_migration.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32
    ]
    lib.iouring_kernel_page_migrator_queue_migration.restype = ctypes.c_int

    lib.iouring_kernel_page_migrator_dispatch_batch.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.iouring_kernel_page_migrator_dispatch_batch.restype = ctypes.c_int

    lib.iouring_kernel_page_migrator_get_stats.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_int)
    ]
    lib.iouring_kernel_page_migrator_get_stats.restype = ctypes.c_int

    lib.iouring_kernel_page_migrator_free.argtypes = [ctypes.c_void_p]
    lib.iouring_kernel_page_migrator_free.restype = None

    max_pages = 64
    page_size = 4096
    num_nodes = 4

    migrator = lib.iouring_kernel_page_migrator_init(max_pages, page_size, num_nodes)
    assert migrator is not None

    try:
        # Queue 8 migrations: pages 0-7 from node 0 to node 1
        for p in range(8):
            ret = lib.iouring_kernel_page_migrator_queue_migration(migrator, p, 0, 1)
            assert ret == 0

        # Dispatch batch of 5
        dispatched = lib.iouring_kernel_page_migrator_dispatch_batch(migrator, 5)
        assert dispatched == 5

        # Check stats
        tot_migrated = ctypes.c_uint64(0)
        tot_bytes = ctypes.c_uint64(0)
        is_reg = ctypes.c_int(0)
        ret = lib.iouring_kernel_page_migrator_get_stats(
            migrator, ctypes.byref(tot_migrated), ctypes.byref(tot_bytes), ctypes.byref(is_reg)
        )
        assert ret == 0
        assert tot_migrated.value == 5
        assert tot_bytes.value == 5 * 4096
        assert is_reg.value == 1

        # Dispatch remaining 3
        dispatched_rem = lib.iouring_kernel_page_migrator_dispatch_batch(migrator, 10)
        assert dispatched_rem == 3

        ret = lib.iouring_kernel_page_migrator_get_stats(
            migrator, ctypes.byref(tot_migrated), ctypes.byref(tot_bytes), ctypes.byref(is_reg)
        )
        assert ret == 0
        assert tot_migrated.value == 8
        assert tot_bytes.value == 8 * 4096
    finally:
        lib.iouring_kernel_page_migrator_free(migrator)


def test_iouring_hugepage_compactor_correctness():
    so_path = "csrc/libfused_iouring_hugepage_compactor.so"
    if not os.path.exists(so_path):
        pytest.skip("Hugepage compactor engine not compiled")

    lib = ctypes.CDLL(so_path)
    lib.iouring_hugepage_compactor_init.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    lib.iouring_hugepage_compactor_init.restype = ctypes.c_void_p

    lib.iouring_hugepage_compactor_register_page.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint64, ctypes.c_float
    ]
    lib.iouring_hugepage_compactor_register_page.restype = ctypes.c_int

    lib.iouring_hugepage_compactor_compact_batch.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.iouring_hugepage_compactor_compact_batch.restype = ctypes.c_int

    lib.iouring_hugepage_compactor_get_stats.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_int)
    ]
    lib.iouring_hugepage_compactor_get_stats.restype = ctypes.c_int

    lib.iouring_hugepage_compactor_free.argtypes = [ctypes.c_void_p]
    lib.iouring_hugepage_compactor_free.restype = None

    max_pages = 16
    hugepage_kb = 2048  # 2MB

    compactor = lib.iouring_hugepage_compactor_init(max_pages, hugepage_kb)
    assert compactor is not None

    try:
        # Register 4 pages with varying fragmentation:
        # p0: 0.05 (clean, no compaction needed)
        # p1: 0.25 (needs compaction, 25% of 2MB = 512KB)
        # p2: 0.50 (needs compaction, 50% of 2MB = 1024KB)
        # p3: 0.10 (clean)
        lib.iouring_hugepage_compactor_register_page(compactor, 0, 0x1000, 0.05)
        lib.iouring_hugepage_compactor_register_page(compactor, 1, 0x1001, 0.25)
        lib.iouring_hugepage_compactor_register_page(compactor, 2, 0x1002, 0.50)
        lib.iouring_hugepage_compactor_register_page(compactor, 3, 0x1003, 0.10)

        # Compact batch of 1
        compacted = lib.iouring_hugepage_compactor_compact_batch(compactor, 1)
        assert compacted == 1

        tot_compacted = ctypes.c_uint64(0)
        tot_bytes = ctypes.c_uint64(0)
        is_reg = ctypes.c_int(0)
        ret = lib.iouring_hugepage_compactor_get_stats(
            compactor, ctypes.byref(tot_compacted), ctypes.byref(tot_bytes), ctypes.byref(is_reg)
        )
        assert ret == 0
        assert tot_compacted.value == 1
        assert tot_bytes.value == int(0.25 * 2048 * 1024)
        assert is_reg.value == 1

        # Compact remaining
        compacted_rem = lib.iouring_hugepage_compactor_compact_batch(compactor, 10)
        assert compacted_rem == 1

        ret = lib.iouring_hugepage_compactor_get_stats(
            compactor, ctypes.byref(tot_compacted), ctypes.byref(tot_bytes), ctypes.byref(is_reg)
        )
        assert ret == 0
        assert tot_compacted.value == 2
        expected_bytes = int(0.25 * 2048 * 1024) + int(0.50 * 2048 * 1024)
        assert tot_bytes.value == expected_bytes
    finally:
        lib.iouring_hugepage_compactor_free(compactor)


def test_iouring_dmabuf_zc_stream_correctness():
    so_path = "csrc/libfused_iouring_dmabuf_zc_stream.so"
    if not os.path.exists(so_path):
        pytest.skip("DMABUF zero-copy stream engine not compiled")

    lib = ctypes.CDLL(so_path)
    lib.iouring_dmabuf_zc_stream_init.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    lib.iouring_dmabuf_zc_stream_init.restype = ctypes.c_void_p

    lib.iouring_dmabuf_zc_stream_push.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32
    ]
    lib.iouring_dmabuf_zc_stream_push.restype = ctypes.c_int

    lib.iouring_dmabuf_zc_stream_poll_drain.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    lib.iouring_dmabuf_zc_stream_poll_drain.restype = ctypes.c_int

    lib.iouring_dmabuf_zc_stream_get_stats.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_int)
    ]
    lib.iouring_dmabuf_zc_stream_get_stats.restype = ctypes.c_int

    lib.iouring_dmabuf_zc_stream_free.argtypes = [ctypes.c_void_p]
    lib.iouring_dmabuf_zc_stream_free.restype = None

    cap = 32
    chunk_sz = 16384  # 16KB

    stream = lib.iouring_dmabuf_zc_stream_init(cap, chunk_sz)
    assert stream is not None

    try:
        # Push 6 chunks
        for i in range(6):
            ret = lib.iouring_dmabuf_zc_stream_push(stream, i, 8192)
            assert ret == 0

        # Drain batch of 4
        drained = lib.iouring_dmabuf_zc_stream_poll_drain(stream, 4)
        assert drained == 4

        tot_streamed = ctypes.c_uint64(0)
        tot_bytes = ctypes.c_uint64(0)
        is_reg = ctypes.c_int(0)
        ret = lib.iouring_dmabuf_zc_stream_get_stats(
            stream, ctypes.byref(tot_streamed), ctypes.byref(tot_bytes), ctypes.byref(is_reg)
        )
        assert ret == 0
        assert tot_streamed.value == 4
        assert tot_bytes.value == 4 * 8192
        assert is_reg.value == 1

        # Drain remaining 2
        drained_rem = lib.iouring_dmabuf_zc_stream_poll_drain(stream, 10)
        assert drained_rem == 2

        ret = lib.iouring_dmabuf_zc_stream_get_stats(
            stream, ctypes.byref(tot_streamed), ctypes.byref(tot_bytes), ctypes.byref(is_reg)
        )
        assert ret == 0
        assert tot_streamed.value == 6
        assert tot_bytes.value == 6 * 8192
    finally:
        lib.iouring_dmabuf_zc_stream_free(stream)


class MemfdSecretStreamConfig(ctypes.Structure):
    _fields_ = [
        ("ring_entries", ctypes.c_uint32),
        ("buffer_size_bytes", ctypes.c_uint32),
        ("num_buffers", ctypes.c_uint32),
        ("use_sqpoll", ctypes.c_uint32),
    ]


class MemfdSecretStreamStats(ctypes.Structure):
    _fields_ = [
        ("bytes_streamed", ctypes.c_uint64),
        ("completions_processed", ctypes.c_uint32),
        ("secret_fd", ctypes.c_uint32),
        ("status_flags", ctypes.c_uint32),
    ]


def test_iouring_memfd_secret_stream_correctness():
    """Validates the Linux 6.18 memfd_secret and io_uring confidential streaming engine."""
    so_path = "csrc/libfused_iouring_memfd_secret_stream.so"
    assert os.path.exists(so_path), f"Shared object not found: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_memfd_secret_stream_engine.argtypes = [
        ctypes.POINTER(MemfdSecretStreamConfig),
        ctypes.POINTER(MemfdSecretStreamStats),
    ]
    lib.run_memfd_secret_stream_engine.restype = ctypes.c_int

    config = MemfdSecretStreamConfig(
        ring_entries=64,
        buffer_size_bytes=4096,
        num_buffers=8,
        use_sqpoll=0,
    )
    stats = MemfdSecretStreamStats()

    ret = lib.run_memfd_secret_stream_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_memfd_secret_stream_engine failed with return code {ret}"
    assert stats.bytes_streamed == 8 * 4096
    assert stats.completions_processed == 8


class MsealStreamConfig(ctypes.Structure):
    _fields_ = [
        ("ring_entries", ctypes.c_uint32),
        ("buffer_size_bytes", ctypes.c_uint32),
        ("num_buffers", ctypes.c_uint32),
        ("apply_mseal", ctypes.c_uint32),
    ]


class MsealStreamStats(ctypes.Structure):
    _fields_ = [
        ("bytes_transferred", ctypes.c_uint64),
        ("completions_processed", ctypes.c_uint32),
        ("is_msealed", ctypes.c_uint32),
        ("status_flags", ctypes.c_uint32),
    ]


def test_iouring_mseal_protected_stream_correctness():
    """Validates the Linux 6.18 mseal and io_uring zero-copy protected stream engine."""
    so_path = "csrc/libfused_iouring_mseal_protected_stream.so"
    assert os.path.exists(so_path), f"Shared object not found: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_mseal_protected_stream_engine.argtypes = [
        ctypes.POINTER(MsealStreamConfig),
        ctypes.POINTER(MsealStreamStats),
    ]
    lib.run_mseal_protected_stream_engine.restype = ctypes.c_int

    config = MsealStreamConfig(
        ring_entries=64,
        buffer_size_bytes=4096,
        num_buffers=8,
        apply_mseal=1,
    )
    stats = MsealStreamStats()

    ret = lib.run_mseal_protected_stream_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_mseal_protected_stream_engine failed with return code {ret}"
    assert stats.bytes_transferred == 8 * 4096
    assert stats.completions_processed == 8


class FutexStreamConfig(ctypes.Structure):
    _fields_ = [
        ("ring_entries", ctypes.c_uint32),
        ("buffer_size_bytes", ctypes.c_uint32),
        ("num_futexes", ctypes.c_uint32),
        ("wake_batch_size", ctypes.c_uint32),
    ]


class FutexStreamStats(ctypes.Structure):
    _fields_ = [
        ("total_wakes", ctypes.c_uint64),
        ("futexes_monitored", ctypes.c_uint32),
        ("ring_status", ctypes.c_uint32),
        ("fallback_used", ctypes.c_uint32),
    ]


def test_iouring_futex2_wake_stream_correctness():
    """Validates the Linux 6.18 futex_waitv & batch wake io_uring engine."""
    so_path = "csrc/libfused_iouring_futex2_wake_stream.so"
    assert os.path.exists(so_path), f"Shared object not found: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_futex2_wake_stream_engine.argtypes = [
        ctypes.POINTER(FutexStreamConfig),
        ctypes.POINTER(FutexStreamStats),
    ]
    lib.run_futex2_wake_stream_engine.restype = ctypes.c_int

    config = FutexStreamConfig(
        ring_entries=64,
        buffer_size_bytes=4096,
        num_futexes=32,
        wake_batch_size=8,
    )
    stats = FutexStreamStats()

    ret = lib.run_futex2_wake_stream_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_futex2_wake_stream_engine failed with return code {ret}"
    assert stats.futexes_monitored == 32
    assert stats.total_wakes == 32


class SplicePipeTeeConfig(ctypes.Structure):
    _fields_ = [
        ("ring_entries", ctypes.c_uint32),
        ("packet_size_bytes", ctypes.c_uint32),
        ("num_packets", ctypes.c_uint32),
        ("fanout_degree", ctypes.c_uint32),
    ]


class SplicePipeTeeStats(ctypes.Structure):
    _fields_ = [
        ("total_bytes_spliced", ctypes.c_uint64),
        ("total_bytes_teed", ctypes.c_uint64),
        ("packets_streamed", ctypes.c_uint32),
        ("ring_status", ctypes.c_uint32),
        ("zero_copy_verified", ctypes.c_uint32),
    ]


def test_iouring_splice_pipe_tee_stream_correctness():
    """Validates the Linux 6.18 zero-copy splice & pipe tee fanout stream engine."""
    so_path = "csrc/libfused_iouring_splice_pipe_tee_stream.so"
    assert os.path.exists(so_path), f"Shared object not found: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_splice_pipe_tee_stream_engine.argtypes = [
        ctypes.POINTER(SplicePipeTeeConfig),
        ctypes.POINTER(SplicePipeTeeStats),
    ]
    lib.run_splice_pipe_tee_stream_engine.restype = ctypes.c_int

    config = SplicePipeTeeConfig(
        ring_entries=64,
        packet_size_bytes=4096,
        num_packets=16,
        fanout_degree=3,
    )
    stats = SplicePipeTeeStats()

    ret = lib.run_splice_pipe_tee_stream_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_splice_pipe_tee_stream_engine failed with return code {ret}"
    assert stats.packets_streamed == 16
    assert stats.zero_copy_verified == 1
    assert stats.total_bytes_spliced == 16 * 4096
    assert stats.total_bytes_teed == 16 * 4096 * (3 - 1)


class SqThreadAffinityConfig(ctypes.Structure):
    _fields_ = [
        ("ring_entries", ctypes.c_uint32),
        ("sq_thread_cpu", ctypes.c_uint32),
        ("sq_thread_idle_ms", ctypes.c_uint32),
        ("batch_size", ctypes.c_uint32),
    ]


class SqThreadAffinityStats(ctypes.Structure):
    _fields_ = [
        ("total_submissions_polled", ctypes.c_uint64),
        ("pinned_cpu_verified", ctypes.c_uint32),
        ("ring_status", ctypes.c_uint32),
        ("sqpoll_active", ctypes.c_uint32),
    ]


def test_iouring_sq_thread_cpu_pinning_stream_correctness():
    """Validates the Linux 6.18 SQPOLL kernel thread CPU affinity and isolated polling engine."""
    so_path = "csrc/libfused_iouring_sq_thread_cpu_pinning_stream.so"
    assert os.path.exists(so_path), f"Shared object not found: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_sq_thread_cpu_pinning_engine.argtypes = [
        ctypes.POINTER(SqThreadAffinityConfig),
        ctypes.POINTER(SqThreadAffinityStats),
    ]
    lib.run_sq_thread_cpu_pinning_engine.restype = ctypes.c_int

    config = SqThreadAffinityConfig(
        ring_entries=64,
        sq_thread_cpu=1,
        sq_thread_idle_ms=2000,
        batch_size=32,
    )
    stats = SqThreadAffinityStats()

    ret = lib.run_sq_thread_cpu_pinning_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_sq_thread_cpu_pinning_engine failed with return code {ret}"
    assert stats.ring_status == 1
    assert stats.total_submissions_polled == 32


class FixedDmaNvmeConfig(ctypes.Structure):
    _fields_ = [
        ("ring_entries", ctypes.c_uint32),
        ("buffer_size_bytes", ctypes.c_uint32),
        ("num_buffers", ctypes.c_uint32),
        ("batch_submissions", ctypes.c_uint32),
    ]


class FixedDmaNvmeStats(ctypes.Structure):
    _fields_ = [
        ("total_bytes_transferred", ctypes.c_uint64),
        ("buffers_registered", ctypes.c_uint32),
        ("ring_status", ctypes.c_uint32),
        ("dma_direct_active", ctypes.c_uint32),
    ]


def test_iouring_fixed_dma_buf_direct_nvme_correctness():
    """Validates the Linux 6.18 pre-registered fixed DMA-BUF direct NVMe streaming engine."""
    so_path = "csrc/libfused_iouring_fixed_dma_buf_direct_nvme.so"
    assert os.path.exists(so_path), f"Shared object not found: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_fixed_dma_buf_direct_nvme_engine.argtypes = [
        ctypes.POINTER(FixedDmaNvmeConfig),
        ctypes.POINTER(FixedDmaNvmeStats),
    ]
    lib.run_fixed_dma_buf_direct_nvme_engine.restype = ctypes.c_int

    config = FixedDmaNvmeConfig(
        ring_entries=64,
        buffer_size_bytes=4096,
        num_buffers=8,
        batch_submissions=16,
    )
    stats = FixedDmaNvmeStats()

    ret = lib.run_fixed_dma_buf_direct_nvme_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_fixed_dma_buf_direct_nvme_engine failed with return code {ret}"
    assert stats.ring_status == 1
    assert stats.buffers_registered == 8
    assert stats.total_bytes_transferred == 16 * 4096
    assert stats.dma_direct_active == 1


class DirectRingConfig(ctypes.Structure):
    _fields_ = [
        ("ring_entries", ctypes.c_uint32),
        ("slot_size_bytes", ctypes.c_uint32),
        ("num_slots", ctypes.c_uint32),
        ("batch_count", ctypes.c_uint32),
    ]


class DirectRingStats(ctypes.Structure):
    _fields_ = [
        ("total_slots_submitted", ctypes.c_uint64),
        ("active_slots_count", ctypes.c_uint32),
        ("ring_status", ctypes.c_uint32),
        ("zero_alloc_verified", ctypes.c_uint32),
    ]


def test_iouring_direct_ring_buffer_zero_alloc_correctness():
    """Validates the Linux 6.18 direct ring-buffer zero-allocation slot engine."""
    so_path = "csrc/libfused_iouring_direct_ring_buffer_zero_alloc.so"
    assert os.path.exists(so_path), f"Shared object not found: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_direct_ring_buffer_zero_alloc_engine.argtypes = [
        ctypes.POINTER(DirectRingConfig),
        ctypes.POINTER(DirectRingStats),
    ]
    lib.run_direct_ring_buffer_zero_alloc_engine.restype = ctypes.c_int

    config = DirectRingConfig(
        ring_entries=64,
        slot_size_bytes=512,
        num_slots=16,
        batch_count=32,
    )
    stats = DirectRingStats()

    ret = lib.run_direct_ring_buffer_zero_alloc_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_direct_ring_buffer_zero_alloc_engine failed with return code {ret}"
    assert stats.ring_status == 1
    assert stats.active_slots_count == 16
    assert stats.zero_alloc_verified == 1

def test_iouring_direct_splice_tee_zerocopy_correctness():
    so_path = "csrc/libfused_iouring_direct_splice_tee_zerocopy.so"
    assert os.path.exists(so_path), f"Shared library does not exist: {so_path}"
    lib = ctypes.CDLL(so_path)

    class SpliceTeeConfig(ctypes.Structure):
        _fields_ = [
            ("ring_entries", ctypes.c_uint32),
            ("chunk_size_bytes", ctypes.c_uint32),
            ("total_chunks", ctypes.c_uint32),
            ("pipe_capacity", ctypes.c_uint32),
        ]

    class SpliceTeeStats(ctypes.Structure):
        _fields_ = [
            ("total_bytes_spliced", ctypes.c_uint64),
            ("total_bytes_teed", ctypes.c_uint64),
            ("chunks_completed", ctypes.c_uint32),
            ("zero_copy_verified", ctypes.c_uint32),
            ("engine_status", ctypes.c_uint32),
        ]

    lib.run_direct_splice_tee_zerocopy_engine.argtypes = [
        ctypes.POINTER(SpliceTeeConfig),
        ctypes.POINTER(SpliceTeeStats)
    ]
    lib.run_direct_splice_tee_zerocopy_engine.restype = ctypes.c_int

    config = SpliceTeeConfig(
        ring_entries=64,
        chunk_size_bytes=4096,
        total_chunks=16,
        pipe_capacity=65536,
    )
    stats = SpliceTeeStats()

    ret = lib.run_direct_splice_tee_zerocopy_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_direct_splice_tee_zerocopy_engine failed with return code {ret}"
    assert stats.engine_status == 1
    assert stats.chunks_completed == 16
    assert stats.total_bytes_spliced == 16 * 4096
    assert stats.zero_copy_verified == 1

def test_iouring_registered_ringbuf_eventfd_splice_correctness():
    so_path = "csrc/libfused_iouring_registered_ringbuf_eventfd_splice.so"
    assert os.path.exists(so_path), f"Shared library does not exist: {so_path}"
    lib = ctypes.CDLL(so_path)

    class RingbufEventfdConfig(ctypes.Structure):
        _fields_ = [
            ("ring_entries", ctypes.c_uint32),
            ("buffer_size_bytes", ctypes.c_uint32),
            ("num_buffers", ctypes.c_uint32),
            ("events_to_signal", ctypes.c_uint32),
        ]

    class RingbufEventfdStats(ctypes.Structure):
        _fields_ = [
            ("total_bytes_transferred", ctypes.c_uint64),
            ("events_completed", ctypes.c_uint32),
            ("active_rings_count", ctypes.c_uint32),
            ("eventfd_signal_verified", ctypes.c_uint32),
            ("engine_status", ctypes.c_uint32),
        ]

    lib.run_registered_ringbuf_eventfd_splice_engine.argtypes = [
        ctypes.POINTER(RingbufEventfdConfig),
        ctypes.POINTER(RingbufEventfdStats)
    ]
    lib.run_registered_ringbuf_eventfd_splice_engine.restype = ctypes.c_int

    config = RingbufEventfdConfig(
        ring_entries=64,
        buffer_size_bytes=2048,
        num_buffers=8,
        events_to_signal=12,
    )
    stats = RingbufEventfdStats()

    ret = lib.run_registered_ringbuf_eventfd_splice_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_registered_ringbuf_eventfd_splice_engine failed with return code {ret}"
    assert stats.engine_status == 1
    assert stats.events_completed == 12
    assert stats.total_bytes_transferred == 12 * 2048
    assert stats.active_rings_count == 8
    assert stats.eventfd_signal_verified == 1

def test_iouring_etale_shm_ring_stream_correctness():
    so_path = "csrc/libfused_iouring_etale_shm_ring_stream.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    class EtaleShmStreamConfig(ctypes.Structure):
        _fields_ = [
            ("ring_entries", ctypes.c_uint32),
            ("chunk_size_bytes", ctypes.c_uint32),
            ("num_chunks", ctypes.c_uint32),
            ("stream_cycles", ctypes.c_uint32),
        ]

    class EtaleShmStreamStats(ctypes.Structure):
        _fields_ = [
            ("total_bytes_streamed", ctypes.c_uint64),
            ("chunks_processed", ctypes.c_uint32),
            ("ring_queue_depth", ctypes.c_uint32),
            ("iopoll_verified", ctypes.c_uint32),
            ("engine_status", ctypes.c_uint32),
        ]

    lib = ctypes.CDLL(so_path)
    lib.run_etale_shm_ring_stream_engine.argtypes = [
        ctypes.POINTER(EtaleShmStreamConfig),
        ctypes.POINTER(EtaleShmStreamStats)
    ]
    lib.run_etale_shm_ring_stream_engine.restype = ctypes.c_int

    config = EtaleShmStreamConfig(
        ring_entries=64,
        chunk_size_bytes=4096,
        num_chunks=16,
        stream_cycles=32,
    )
    stats = EtaleShmStreamStats()

    ret = lib.run_etale_shm_ring_stream_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_etale_shm_ring_stream_engine failed with return code {ret}"
    assert stats.engine_status == 1
    assert stats.chunks_processed == 32
    assert stats.total_bytes_streamed == 32 * 4096
    assert stats.ring_queue_depth == 64
    assert stats.iopoll_verified == 1

def test_iouring_kunneth_shm_mmap_splice_correctness():
    so_path = "csrc/libfused_iouring_kunneth_shm_mmap_splice.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    class KunnethMmapConfig(ctypes.Structure):
        _fields_ = [
            ("ring_entries", ctypes.c_uint32),
            ("buffer_size_bytes", ctypes.c_uint32),
            ("num_projectors", ctypes.c_uint32),
            ("stream_iterations", ctypes.c_uint32),
        ]

    class KunnethMmapStats(ctypes.Structure):
        _fields_ = [
            ("total_bytes_spliced", ctypes.c_uint64),
            ("projections_completed", ctypes.c_uint32),
            ("ring_queue_depth", ctypes.c_uint32),
            ("mmap_splice_verified", ctypes.c_uint32),
            ("engine_status", ctypes.c_uint32),
        ]

    lib = ctypes.CDLL(so_path)
    lib.run_kunneth_shm_mmap_splice_engine.argtypes = [
        ctypes.POINTER(KunnethMmapConfig),
        ctypes.POINTER(KunnethMmapStats)
    ]
    lib.run_kunneth_shm_mmap_splice_engine.restype = ctypes.c_int

    config = KunnethMmapConfig(
        ring_entries=64,
        buffer_size_bytes=2048,
        num_projectors=8,
        stream_iterations=16,
    )
    stats = KunnethMmapStats()

    ret = lib.run_kunneth_shm_mmap_splice_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_kunneth_shm_mmap_splice_engine failed with return code {ret}"
    assert stats.engine_status == 1
    assert stats.projections_completed == 16
    assert stats.total_bytes_spliced == 16 * 2048
    assert stats.ring_queue_depth == 64
    assert stats.mmap_splice_verified == 1

def test_iouring_perverse_sheaf_ring_splice_correctness():
    so_path = "csrc/libfused_iouring_perverse_sheaf_ring_splice.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    class PerverseSheafConfig(ctypes.Structure):
        _fields_ = [
            ("ring_entries", ctypes.c_uint32),
            ("slice_size_bytes", ctypes.c_uint32),
            ("num_strata", ctypes.c_uint32),
            ("total_slices_to_stream", ctypes.c_uint32),
        ]

    class PerverseSheafStats(ctypes.Structure):
        _fields_ = [
            ("total_bytes_spliced", ctypes.c_uint64),
            ("strata_processed", ctypes.c_uint32),
            ("ring_queue_depth", ctypes.c_uint32),
            ("perverse_splice_verified", ctypes.c_uint32),
            ("engine_status", ctypes.c_uint32),
        ]

    lib = ctypes.CDLL(so_path)
    lib.run_perverse_sheaf_ring_splice_engine.argtypes = [
        ctypes.POINTER(PerverseSheafConfig),
        ctypes.POINTER(PerverseSheafStats)
    ]
    lib.run_perverse_sheaf_ring_splice_engine.restype = ctypes.c_int

    config = PerverseSheafConfig(
        ring_entries=64,
        slice_size_bytes=4096,
        num_strata=8,
        total_slices_to_stream=24,
    )
    stats = PerverseSheafStats()

    ret = lib.run_perverse_sheaf_ring_splice_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_perverse_sheaf_ring_splice_engine failed with return code {ret}"
    assert stats.engine_status == 1
    assert stats.strata_processed == 24
    assert stats.total_bytes_spliced == 24 * 4096
    assert stats.ring_queue_depth == 64
    assert stats.perverse_splice_verified == 1

def test_iouring_motivic_slice_shm_mmap_correctness():
    so_path = "csrc/libfused_iouring_motivic_slice_shm_mmap.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    class MotivicSliceConfig(ctypes.Structure):
        _fields_ = [
            ("ring_entries", ctypes.c_uint32),
            ("slice_size_bytes", ctypes.c_uint32),
            ("num_slices", ctypes.c_uint32),
            ("stream_passes", ctypes.c_uint32),
        ]

    class MotivicSliceStats(ctypes.Structure):
        _fields_ = [
            ("total_bytes_streamed", ctypes.c_uint64),
            ("slices_processed", ctypes.c_uint32),
            ("ring_queue_depth", ctypes.c_uint32),
            ("slice_mmap_verified", ctypes.c_uint32),
            ("engine_status", ctypes.c_uint32),
        ]

    lib = ctypes.CDLL(so_path)
    lib.run_motivic_slice_shm_mmap_engine.argtypes = [
        ctypes.POINTER(MotivicSliceConfig),
        ctypes.POINTER(MotivicSliceStats)
    ]
    lib.run_motivic_slice_shm_mmap_engine.restype = ctypes.c_int

    config = MotivicSliceConfig(
        ring_entries=64,
        slice_size_bytes=4096,
        num_slices=12,
        stream_passes=24,
    )
    stats = MotivicSliceStats()

    ret = lib.run_motivic_slice_shm_mmap_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_motivic_slice_shm_mmap_engine failed with return code {ret}"
    assert stats.engine_status == 1
    assert stats.slices_processed == 24
    assert stats.total_bytes_streamed == 24 * 4096
    assert stats.ring_queue_depth == 64
    assert stats.slice_mmap_verified == 1

def test_iouring_galois_symbol_splice_stream_correctness():
    so_path = "csrc/libfused_iouring_galois_symbol_splice_stream.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    class GaloisSymbolConfig(ctypes.Structure):
        _fields_ = [
            ("ring_entries", ctypes.c_uint32),
            ("symbol_packet_bytes", ctypes.c_uint32),
            ("num_packets", ctypes.c_uint32),
            ("stream_passes", ctypes.c_uint32),
        ]

    class GaloisSymbolStats(ctypes.Structure):
        _fields_ = [
            ("total_bytes_streamed", ctypes.c_uint64),
            ("packets_processed", ctypes.c_uint32),
            ("ring_queue_depth", ctypes.c_uint32),
            ("symbol_splice_verified", ctypes.c_uint32),
            ("engine_status", ctypes.c_uint32),
        ]

    lib = ctypes.CDLL(so_path)
    lib.run_galois_symbol_splice_stream_engine.argtypes = [
        ctypes.POINTER(GaloisSymbolConfig),
        ctypes.POINTER(GaloisSymbolStats)
    ]
    lib.run_galois_symbol_splice_stream_engine.restype = ctypes.c_int

    config = GaloisSymbolConfig(
        ring_entries=64,
        symbol_packet_bytes=4096,
        num_packets=16,
        stream_passes=16,
    )
    stats = GaloisSymbolStats()

    ret = lib.run_galois_symbol_splice_stream_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_galois_symbol_splice_stream_engine failed with return code {ret}"
    assert stats.engine_status == 1
    assert stats.packets_processed == 16 * 16
    assert stats.total_bytes_streamed == 16 * 16 * 4096
    assert stats.ring_queue_depth == 64
    assert stats.symbol_splice_verified == 1

def test_iouring_motivic_truncation_splice_ring_correctness():
    so_path = "csrc/libfused_iouring_motivic_truncation_splice_ring.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    class MotivicTruncationConfig(ctypes.Structure):
        _fields_ = [
            ("ring_entries", ctypes.c_uint32),
            ("complex_chunk_bytes", ctypes.c_uint32),
            ("num_complexes", ctypes.c_uint32),
            ("stream_passes", ctypes.c_uint32),
        ]

    class MotivicTruncationStats(ctypes.Structure):
        _fields_ = [
            ("total_bytes_streamed", ctypes.c_uint64),
            ("complexes_processed", ctypes.c_uint32),
            ("ring_queue_depth", ctypes.c_uint32),
            ("truncation_splice_verified", ctypes.c_uint32),
            ("engine_status", ctypes.c_uint32),
        ]

    lib = ctypes.CDLL(so_path)
    lib.run_motivic_truncation_splice_ring_engine.argtypes = [
        ctypes.POINTER(MotivicTruncationConfig),
        ctypes.POINTER(MotivicTruncationStats)
    ]
    lib.run_motivic_truncation_splice_ring_engine.restype = ctypes.c_int

    config = MotivicTruncationConfig(
        ring_entries=64,
        complex_chunk_bytes=4096,
        num_complexes=16,
        stream_passes=16,
    )
    stats = MotivicTruncationStats()

    ret = lib.run_motivic_truncation_splice_ring_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_motivic_truncation_splice_ring_engine failed with return code {ret}"
    assert stats.engine_status == 1
    assert stats.complexes_processed == 16 * 16
    assert stats.total_bytes_streamed == 16 * 16 * 4096
    assert stats.ring_queue_depth == 64
    assert stats.truncation_splice_verified == 1

def test_iouring_bott_periodicity_shm_ring_correctness():
    so_path = "csrc/libfused_iouring_bott_periodicity_shm_ring.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    class BottPeriodicityConfig(ctypes.Structure):
        _fields_ = [
            ("ring_entries", ctypes.c_uint32),
            ("packet_size_bytes", ctypes.c_uint32),
            ("num_packets", ctypes.c_uint32),
            ("stream_passes", ctypes.c_uint32),
        ]

    class BottPeriodicityStats(ctypes.Structure):
        _fields_ = [
            ("total_bytes_streamed", ctypes.c_uint64),
            ("packets_processed", ctypes.c_uint32),
            ("ring_queue_depth", ctypes.c_uint32),
            ("bott_ring_verified", ctypes.c_uint32),
            ("engine_status", ctypes.c_uint32),
        ]

    lib = ctypes.CDLL(so_path)
    lib.run_bott_periodicity_shm_ring_engine.argtypes = [
        ctypes.POINTER(BottPeriodicityConfig),
        ctypes.POINTER(BottPeriodicityStats)
    ]
    lib.run_bott_periodicity_shm_ring_engine.restype = ctypes.c_int

    config = BottPeriodicityConfig(
        ring_entries=64,
        packet_size_bytes=4096,
        num_packets=16,
        stream_passes=16,
    )
    stats = BottPeriodicityStats()

    ret = lib.run_bott_periodicity_shm_ring_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_bott_periodicity_shm_ring_engine failed with return code {ret}"
    assert stats.engine_status == 1
    assert stats.packets_processed == 16 * 16
    assert stats.total_bytes_streamed == 16 * 16 * 4096
    assert stats.ring_queue_depth == 64
    assert stats.bott_ring_verified == 1


def test_iouring_quillen_patching_dma_stream_correctness():
    so_path = "csrc/libfused_iouring_quillen_patching_dma_stream.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    class QuillenPatchingConfig(ctypes.Structure):
        _fields_ = [
            ("ring_entries", ctypes.c_uint32),
            ("patch_size_bytes", ctypes.c_uint32),
            ("num_patches", ctypes.c_uint32),
            ("stream_passes", ctypes.c_uint32),
        ]

    class QuillenPatchingStats(ctypes.Structure):
        _fields_ = [
            ("total_bytes_streamed", ctypes.c_uint64),
            ("patches_processed", ctypes.c_uint32),
            ("ring_queue_depth", ctypes.c_uint32),
            ("patching_stream_verified", ctypes.c_uint32),
            ("engine_status", ctypes.c_uint32),
        ]

    lib = ctypes.CDLL(so_path)
    lib.run_quillen_patching_dma_stream_engine.argtypes = [
        ctypes.POINTER(QuillenPatchingConfig),
        ctypes.POINTER(QuillenPatchingStats)
    ]
    lib.run_quillen_patching_dma_stream_engine.restype = ctypes.c_int

    config = QuillenPatchingConfig(
        ring_entries=64,
        patch_size_bytes=4096,
        num_patches=16,
        stream_passes=16,
    )
    stats = QuillenPatchingStats()

    ret = lib.run_quillen_patching_dma_stream_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_quillen_patching_dma_stream_engine failed with return code {ret}"
    assert stats.engine_status == 1
    assert stats.patches_processed == 16 * 16
    assert stats.total_bytes_streamed == 16 * 16 * 4096
    assert stats.ring_queue_depth == 64
    assert stats.patching_stream_verified == 1


def test_iouring_higher_chow_splice_stream_correctness():
    so_path = "csrc/libfused_iouring_higher_chow_splice_stream.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    class HigherChowConfig(ctypes.Structure):
        _fields_ = [
            ("ring_entries", ctypes.c_uint32),
            ("cycle_size_bytes", ctypes.c_uint32),
            ("num_cycles", ctypes.c_uint32),
            ("stream_passes", ctypes.c_uint32),
        ]

    class HigherChowStats(ctypes.Structure):
        _fields_ = [
            ("total_bytes_streamed", ctypes.c_uint64),
            ("cycles_processed", ctypes.c_uint32),
            ("ring_queue_depth", ctypes.c_uint32),
            ("chow_splice_verified", ctypes.c_uint32),
            ("engine_status", ctypes.c_uint32),
        ]

    lib = ctypes.CDLL(so_path)
    lib.run_higher_chow_splice_stream_engine.argtypes = [
        ctypes.POINTER(HigherChowConfig),
        ctypes.POINTER(HigherChowStats)
    ]
    lib.run_higher_chow_splice_stream_engine.restype = ctypes.c_int

    config = HigherChowConfig(
        ring_entries=64,
        cycle_size_bytes=4096,
        num_cycles=16,
        stream_passes=16,
    )
    stats = HigherChowStats()

    ret = lib.run_higher_chow_splice_stream_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_higher_chow_splice_stream_engine failed with return code {ret}"
    assert stats.engine_status == 1
    assert stats.cycles_processed == 16 * 16
    assert stats.total_bytes_streamed == 16 * 16 * 4096
    assert stats.ring_queue_depth == 64
    assert stats.chow_splice_verified == 1


def test_iouring_singular_cycle_splice_stream_correctness():
    so_path = "csrc/libfused_iouring_singular_cycle_splice_stream.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    class SingularCycleConfig(ctypes.Structure):
        _fields_ = [
            ("ring_entries", ctypes.c_uint32),
            ("cycle_size_bytes", ctypes.c_uint32),
            ("num_cycles", ctypes.c_uint32),
            ("stream_passes", ctypes.c_uint32),
        ]

    class SingularCycleStats(ctypes.Structure):
        _fields_ = [
            ("total_bytes_streamed", ctypes.c_uint64),
            ("cycles_processed", ctypes.c_uint32),
            ("ring_queue_depth", ctypes.c_uint32),
            ("singular_cycle_verified", ctypes.c_uint32),
            ("engine_status", ctypes.c_uint32),
        ]

    lib = ctypes.CDLL(so_path)
    lib.run_singular_cycle_splice_stream_engine.argtypes = [
        ctypes.POINTER(SingularCycleConfig),
        ctypes.POINTER(SingularCycleStats)
    ]
    lib.run_singular_cycle_splice_stream_engine.restype = ctypes.c_int

    config = SingularCycleConfig(
        ring_entries=64,
        cycle_size_bytes=4096,
        num_cycles=16,
        stream_passes=16,
    )
    stats = SingularCycleStats()

    ret = lib.run_singular_cycle_splice_stream_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_singular_cycle_splice_stream_engine failed with return code {ret}"
    assert stats.engine_status == 1
    assert stats.cycles_processed == 16 * 16
    assert stats.total_bytes_streamed == 16 * 16 * 4096
    assert stats.ring_queue_depth == 64
    assert stats.singular_cycle_verified == 1


def test_iouring_exceptional_galois_splice_stream_correctness():
    so_path = "csrc/libfused_iouring_exceptional_galois_splice_stream.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    class ExceptionalGaloisConfig(ctypes.Structure):
        _fields_ = [
            ("ring_entries", ctypes.c_uint32),
            ("torsor_size_bytes", ctypes.c_uint32),
            ("num_torsors", ctypes.c_uint32),
            ("stream_passes", ctypes.c_uint32),
        ]

    class ExceptionalGaloisStats(ctypes.Structure):
        _fields_ = [
            ("total_bytes_streamed", ctypes.c_uint64),
            ("torsors_processed", ctypes.c_uint32),
            ("ring_queue_depth", ctypes.c_uint32),
            ("exceptional_galois_verified", ctypes.c_uint32),
            ("engine_status", ctypes.c_uint32),
        ]

    lib = ctypes.CDLL(so_path)
    lib.run_exceptional_galois_splice_stream_engine.argtypes = [
        ctypes.POINTER(ExceptionalGaloisConfig),
        ctypes.POINTER(ExceptionalGaloisStats)
    ]
    lib.run_exceptional_galois_splice_stream_engine.restype = ctypes.c_int

    config = ExceptionalGaloisConfig(
        ring_entries=64,
        torsor_size_bytes=4096,
        num_torsors=16,
        stream_passes=16,
    )
    stats = ExceptionalGaloisStats()

    ret = lib.run_exceptional_galois_splice_stream_engine(ctypes.byref(config), ctypes.byref(stats))
    assert ret == 0, f"run_exceptional_galois_splice_stream_engine failed with return code {ret}"
    assert stats.engine_status == 1
    assert stats.torsors_processed == 16 * 16
    assert stats.total_bytes_streamed == 16 * 16 * 4096
    assert stats.ring_queue_depth == 64
    assert stats.exceptional_galois_verified == 1
