import pytest
import torch
import ctypes
import math

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_polar_svd_correctness():
    so_path = "csrc/fused_blackwell_bit_polar_svd.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_bit_polar_svd.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_void_p
    ]

    batch_size = 16
    A = torch.randn(batch_size, 16, 16, device='cuda', dtype=torch.float32)
    U = torch.zeros(batch_size, 16, 16, device='cuda', dtype=torch.float32)
    S = torch.zeros(batch_size, 16, device='cuda', dtype=torch.float32)
    V = torch.zeros(batch_size, 16, 16, device='cuda', dtype=torch.float32)

    lib.launch_fused_blackwell_bit_polar_svd(
        ctypes.c_void_p(A.data_ptr()),
        ctypes.c_void_p(U.data_ptr()),
        ctypes.c_void_p(S.data_ptr()),
        ctypes.c_void_p(V.data_ptr()),
        batch_size, None
    )
    torch.cuda.synchronize()

    # Singular values must be strictly non-negative
    assert (S >= 0).all()
    # Check that U and V are approximately orthogonal: U^T U ~ I
    UTU = torch.bmm(U.transpose(1, 2), U)
    I = torch.eye(16, device='cuda').unsqueeze(0).expand(batch_size, -1, -1)
    diff = torch.norm(UTU - I, dim=(1, 2)).mean().item()
    assert diff < 0.2  # Convergence tolerance for 5-sweep Jacobi

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_rotor_slerp_correctness():
    so_path = "csrc/fused_blackwell_bit_rotor_slerp.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_bit_rotor_slerp.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_float, ctypes.c_int, ctypes.c_void_p
    ]

    batch_size = 32
    r0 = torch.tensor([[1.0, 0.0, 0.0, 0.0]], device='cuda').expand(batch_size, -1)
    r1 = torch.tensor([[0.0, 1.0, 0.0, 0.0]], device='cuda').expand(batch_size, -1)
    out = torch.zeros(batch_size, 4, device='cuda', dtype=torch.float32)

    # t = 0.5 (halfway between (1,0,0,0) and (0,1,0,0) is (1/sqrt(2), 1/sqrt(2), 0, 0))
    lib.launch_fused_blackwell_bit_rotor_slerp(
        ctypes.c_void_p(r0.data_ptr()),
        ctypes.c_void_p(r1.data_ptr()),
        ctypes.c_void_p(out.data_ptr()),
        0.5, batch_size, None
    )
    torch.cuda.synchronize()

    expected_comp = 1.0 / math.sqrt(2.0)
    assert abs(out[0, 0].item() - expected_comp) < 1e-4
    assert abs(out[0, 1].item() - expected_comp) < 1e-4
    assert abs(out[0, 2].item()) < 1e-4
    assert abs(out[0, 3].item()) < 1e-4

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_berry_phase_zero_loop():
    so_path = "csrc/fused_blackwell_bit_berry_phase.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_bit_berry_phase.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_void_p
    ]

    batch_size = 8
    num_nodes = 4
    # Constant state loop -> phase should be 0
    real = torch.ones(batch_size, num_nodes, 16, device='cuda', dtype=torch.float32)
    imag = torch.zeros(batch_size, num_nodes, 16, device='cuda', dtype=torch.float32)
    out = torch.zeros(batch_size, device='cuda', dtype=torch.float32)

    lib.launch_fused_blackwell_bit_berry_phase(
        ctypes.c_void_p(real.data_ptr()),
        ctypes.c_void_p(imag.data_ptr()),
        ctypes.c_void_p(out.data_ptr()),
        batch_size, num_nodes, None
    )
    torch.cuda.synchronize()

    assert (torch.abs(out) < 1e-5).all()

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_fused_attention_causal():
    so_path = "csrc/fused_blackwell_bit_attention.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_bit_attention.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_float, ctypes.c_int, ctypes.c_int, ctypes.c_void_p
    ]

    batch = 2
    seq_len = 64
    head_dim = 32
    scale = 1.0 / math.sqrt(head_dim)

    Q = torch.randn(batch, seq_len, head_dim, device='cuda', dtype=torch.float32)
    K = torch.randn(batch, seq_len, head_dim, device='cuda', dtype=torch.float32)
    V = torch.randn(batch, seq_len, head_dim, device='cuda', dtype=torch.float32)
    Out = torch.zeros(batch, seq_len, head_dim, device='cuda', dtype=torch.float32)

    lib.launch_fused_blackwell_bit_attention(
        ctypes.c_void_p(Q.data_ptr()),
        ctypes.c_void_p(K.data_ptr()),
        ctypes.c_void_p(V.data_ptr()),
        ctypes.c_void_p(Out.data_ptr()),
        scale, seq_len, batch, None
    )
    torch.cuda.synchronize()

    # Reference PyTorch causal attention
    scores = torch.bmm(Q, K.transpose(1, 2)) * scale
    mask = torch.triu(torch.full((seq_len, seq_len), float('-inf'), device='cuda'), diagonal=1)
    scores = scores + mask
    attn_weights = torch.softmax(scores, dim=-1)
    ref_out = torch.bmm(attn_weights, V)

    diff = torch.norm(Out - ref_out).item() / (batch * seq_len * head_dim)
    assert diff < 1e-4, f"Attention output divergence: {diff}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_dequant_gemv_correctness():
    so_path = "csrc/fused_blackwell_bit_dequant_gemv.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_bit_dequant_gemv.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p
    ]

    M = 64
    K = 128
    half_K = K // 2

    # Packed nibbles
    W_packed = torch.randint(0, 256, (M, half_K), device='cuda', dtype=torch.uint8)
    X = torch.randn(K, device='cuda', dtype=torch.float32)
    scales = torch.ones(M, device='cuda', dtype=torch.float32) * 0.1
    biases = torch.zeros(M, device='cuda', dtype=torch.float32)
    Y = torch.zeros(M, device='cuda', dtype=torch.float32)

    lib.launch_fused_blackwell_bit_dequant_gemv(
        ctypes.c_void_p(W_packed.data_ptr()),
        ctypes.c_void_p(X.data_ptr()),
        ctypes.c_void_p(scales.data_ptr()),
        ctypes.c_void_p(biases.data_ptr()),
        ctypes.c_void_p(Y.data_ptr()),
        M, K, None
    )
    torch.cuda.synchronize()

    # Reference dequantization in PyTorch
    w_cpu = W_packed.cpu().numpy()
    W_unpacked = torch.zeros(M, K, dtype=torch.float32)
    for i in range(M):
        for j in range(half_K):
            byte_v = int(w_cpu[i, j])
            w0 = float((byte_v & 0x0F) - 8) * 0.1
            w1 = float(((byte_v >> 4) & 0x0F) - 8) * 0.1
            W_unpacked[i, j * 2] = w0
            W_unpacked[i, j * 2 + 1] = w1

    ref_Y = torch.mv(W_unpacked.cuda(), X)
    diff = torch.norm(Y - ref_Y).item() / M
    assert diff < 1e-4, f"Dequant GEMV diff: {diff}"
