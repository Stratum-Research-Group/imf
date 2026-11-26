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

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_rope_correctness():
    so_path = "csrc/fused_blackwell_bit_rope.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_bit_rope.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_void_p
    ]

    batch = 2
    seq_len = 16
    num_heads = 4
    head_dim = 32
    base_theta = 10000.0

    x = torch.randn(batch, seq_len, num_heads, head_dim, device='cuda', dtype=torch.float32)
    out = torch.zeros_like(x)

    lib.launch_fused_blackwell_bit_rope(
        ctypes.c_void_p(x.data_ptr()),
        ctypes.c_void_p(out.data_ptr()),
        seq_len, num_heads, head_dim, batch, base_theta, None
    )
    torch.cuda.synchronize()

    # Analytical PyTorch RoPE reference
    half_dim = head_dim // 2
    i = torch.arange(half_dim, device='cuda', dtype=torch.float32)
    inv_freq = 1.0 / (base_theta ** (2 * i / head_dim))
    pos = torch.arange(seq_len, device='cuda', dtype=torch.float32)
    sinusoid_inp = torch.einsum("i,j->ij", pos, inv_freq)
    sin = sinusoid_inp.sin().unsqueeze(0).unsqueeze(2)  # [1, seq_len, 1, half_dim]
    cos = sinusoid_inp.cos().unsqueeze(0).unsqueeze(2)

    x0 = x[..., :half_dim]
    x1 = x[..., half_dim:]
    ref_x0 = x0 * cos - x1 * sin
    ref_x1 = x0 * sin + x1 * cos
    ref_out = torch.cat([ref_x0, ref_x1], dim=-1)

    diff = torch.norm(out - ref_out).item() / (batch * seq_len * num_heads * head_dim)
    assert diff < 1e-4, f"RoPE diff: {diff}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA device required")
def test_causal_sdpa_correctness():
    so_path = "csrc/fused_blackwell_bit_causal_sdpa.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_bit_causal_sdpa.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p
    ]

    batch = 2
    num_heads = 4
    seq_len = 16
    head_dim = 32

    q = torch.randn(batch, num_heads, seq_len, head_dim, device='cuda', dtype=torch.float32)
    k = torch.randn(batch, num_heads, seq_len, head_dim, device='cuda', dtype=torch.float32)
    v = torch.randn(batch, num_heads, seq_len, head_dim, device='cuda', dtype=torch.float32)
    out = torch.zeros_like(q)

    lib.launch_fused_blackwell_bit_causal_sdpa(
        ctypes.c_void_p(q.data_ptr()),
        ctypes.c_void_p(k.data_ptr()),
        ctypes.c_void_p(v.data_ptr()),
        ctypes.c_void_p(out.data_ptr()),
        batch, num_heads, seq_len, head_dim, None
    )
    torch.cuda.synchronize()

    # Analytical PyTorch SDPA reference with causal mask
    ref_out = torch.nn.functional.scaled_dot_product_attention(q, k, v, is_causal=True)

    diff = torch.norm(out - ref_out).item() / (batch * num_heads * seq_len * head_dim)
    assert diff < 1e-4, f"Causal SDPA diff: {diff}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA device required")
def test_rmsnorm_residual_correctness():
    so_path = "csrc/fused_blackwell_bit_rmsnorm.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_bit_rmsnorm.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_void_p
    ]

    num_rows = 32
    hidden_dim = 128
    eps = 1e-6

    x = torch.randn(num_rows, hidden_dim, device='cuda', dtype=torch.float32)
    residual = torch.randn(num_rows, hidden_dim, device='cuda', dtype=torch.float32)
    gamma = torch.randn(hidden_dim, device='cuda', dtype=torch.float32)
    out = torch.zeros_like(x)
    updated_res = torch.zeros_like(residual)

    lib.launch_fused_blackwell_bit_rmsnorm(
        ctypes.c_void_p(x.data_ptr()),
        ctypes.c_void_p(residual.data_ptr()),
        ctypes.c_void_p(gamma.data_ptr()),
        ctypes.c_void_p(out.data_ptr()),
        ctypes.c_void_p(updated_res.data_ptr()),
        num_rows, hidden_dim, eps, None
    )
    torch.cuda.synchronize()

    # Analytical reference
    ref_x_prime = x + residual
    ref_var = ref_x_prime.pow(2).mean(dim=-1, keepdim=True)
    ref_rrms = torch.rsqrt(ref_var + eps)
    ref_out = ref_x_prime * ref_rrms * gamma

    diff_res = torch.norm(updated_res - ref_x_prime).item() / (num_rows * hidden_dim)
    diff_out = torch.norm(out - ref_out).item() / (num_rows * hidden_dim)

    assert diff_res < 1e-5, f"Residual diff: {diff_res}"
    assert diff_out < 1e-4, f"RMSNorm out diff: {diff_out}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA device required")
def test_sliding_window_attn_correctness():
    so_path = "csrc/fused_blackwell_sliding_window_attn.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_sliding_window_attn.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_void_p
    ]

    batch = 2
    num_heads = 4
    seq_len = 16
    head_dim = 64
    window_size = 4
    scale = 1.0 / math.sqrt(head_dim)
    rotary_base = 10000.0

    q = torch.randn(batch, num_heads, seq_len, head_dim, device='cuda', dtype=torch.float32)
    k = torch.randn(batch, num_heads, seq_len, head_dim, device='cuda', dtype=torch.float32)
    v = torch.randn(batch, num_heads, seq_len, head_dim, device='cuda', dtype=torch.float32)
    out = torch.zeros_like(q)

    lib.launch_fused_blackwell_sliding_window_attn(
        ctypes.c_void_p(q.data_ptr()),
        ctypes.c_void_p(k.data_ptr()),
        ctypes.c_void_p(v.data_ptr()),
        ctypes.c_void_p(out.data_ptr()),
        batch, num_heads, seq_len, head_dim, window_size, scale, rotary_base, None
    )
    torch.cuda.synchronize()

    # Analytical reference with manual RoPE and causal sliding window masking
    pos = torch.arange(seq_len, device='cuda', dtype=torch.float32)
    dim_idx = torch.arange(0, head_dim, 2, device='cuda', dtype=torch.float32)
    inv_freq = 1.0 / (rotary_base ** (dim_idx / head_dim))
    angles = torch.einsum('i,j->ij', pos, inv_freq)
    cos_a = torch.cos(angles)
    sin_a = torch.sin(angles)

    def apply_rotary(x):
        x0 = x[..., 0::2]
        x1 = x[..., 1::2]
        r0 = x0 * cos_a - x1 * sin_a
        r1 = x0 * sin_a + x1 * cos_a
        return torch.stack([r0, r1], dim=-1).flatten(-2)

    q_rot = apply_rotary(q)
    k_rot = apply_rotary(k)

    scores = torch.matmul(q_rot, k_rot.transpose(-1, -2)) * scale
    mask = torch.ones(seq_len, seq_len, device='cuda', dtype=torch.bool)
    for i in range(seq_len):
        start = max(0, i - window_size + 1)
        mask[i, start:i+1] = False
    scores.masked_fill_(mask, -1e30)
    attn = torch.softmax(scores, dim=-1)
    ref_out = torch.matmul(attn, v)

    diff = torch.norm(out - ref_out).item() / (batch * num_heads * seq_len * head_dim)
    assert diff < 1e-4, f"SWA diff: {diff}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA device required")
def test_gqa_dequant_correctness():
    so_path = "csrc/fused_blackwell_gqa_dequant.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_gqa_dequant.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_float, ctypes.c_void_p
    ]

    batch = 2
    num_q_heads = 8
    num_kv_heads = 2
    seq_len = 16
    head_dim = 64
    scale = 1.0 / math.sqrt(head_dim)

    q = torch.randn(batch, num_q_heads, seq_len, head_dim, device='cuda', dtype=torch.float32)
    k_quant = torch.randint(-128, 127, (batch, num_kv_heads, seq_len, head_dim), device='cuda', dtype=torch.int8)
    k_scale = torch.rand(batch, num_kv_heads, seq_len, device='cuda', dtype=torch.float32) * 0.05 + 0.01
    v_quant = torch.randint(-128, 127, (batch, num_kv_heads, seq_len, head_dim), device='cuda', dtype=torch.int8)
    v_scale = torch.rand(batch, num_kv_heads, seq_len, device='cuda', dtype=torch.float32) * 0.05 + 0.01
    out = torch.zeros_like(q)

    lib.launch_fused_blackwell_gqa_dequant(
        ctypes.c_void_p(q.data_ptr()),
        ctypes.c_void_p(k_quant.data_ptr()),
        ctypes.c_void_p(k_scale.data_ptr()),
        ctypes.c_void_p(v_quant.data_ptr()),
        ctypes.c_void_p(v_scale.data_ptr()),
        ctypes.c_void_p(out.data_ptr()),
        batch, num_q_heads, num_kv_heads, seq_len, head_dim, scale, None
    )
    torch.cuda.synchronize()

    # Analytical reference:
    k_dequant = k_quant.float() * k_scale.unsqueeze(-1)
    v_dequant = v_quant.float() * v_scale.unsqueeze(-1)

    gqa_ratio = num_q_heads // num_kv_heads
    k_expanded = k_dequant.repeat_interleave(gqa_ratio, dim=1)
    v_expanded = v_dequant.repeat_interleave(gqa_ratio, dim=1)

    scores = torch.matmul(q, k_expanded.transpose(-1, -2)) * scale
    causal_mask = torch.triu(torch.ones(seq_len, seq_len, device='cuda', dtype=torch.bool), diagonal=1)
    scores.masked_fill_(causal_mask, -1e30)
    attn = torch.softmax(scores, dim=-1)
    ref_out = torch.matmul(attn, v_expanded)

    diff = torch.norm(out - ref_out).item() / (batch * num_q_heads * seq_len * head_dim)
    assert diff < 1e-4, f"GQA dequant diff: {diff}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA device required")
def test_chunked_linear_attn_correctness():
    so_path = "csrc/fused_blackwell_chunked_linear_attn.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_chunked_linear_attn.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_float, ctypes.c_float, ctypes.c_void_p
    ]

    batch = 2
    num_heads = 4
    seq_len = 16
    head_dim = 64
    decay = 0.95
    scale = 1.0 / math.sqrt(head_dim)

    q = torch.randn(batch, num_heads, seq_len, head_dim, device='cuda', dtype=torch.float32)
    k = torch.randn(batch, num_heads, seq_len, head_dim, device='cuda', dtype=torch.float32)
    v = torch.randn(batch, num_heads, seq_len, head_dim, device='cuda', dtype=torch.float32)
    out = torch.zeros_like(q)

    lib.launch_fused_blackwell_chunked_linear_attn(
        ctypes.c_void_p(q.data_ptr()),
        ctypes.c_void_p(k.data_ptr()),
        ctypes.c_void_p(v.data_ptr()),
        ctypes.c_void_p(out.data_ptr()),
        batch, num_heads, seq_len, head_dim, decay, scale, None
    )
    torch.cuda.synchronize()

    # Analytical reference:
    t_idx = torch.arange(seq_len, device='cuda').unsqueeze(1)
    j_idx = torch.arange(seq_len, device='cuda').unsqueeze(0)
    delta = t_idx - j_idx
    decay_weights = torch.where(delta >= 0, decay ** delta.float(), torch.zeros_like(delta, dtype=torch.float32))

    scores = torch.matmul(q, k.transpose(-1, -2)) * scale
    weighted_scores = scores * decay_weights
    ref_out = torch.matmul(weighted_scores, v)

    diff = torch.norm(out - ref_out).item() / (batch * num_heads * seq_len * head_dim)
    assert diff < 1e-4, f"Linear attn diff: {diff}"





