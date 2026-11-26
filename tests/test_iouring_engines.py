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











