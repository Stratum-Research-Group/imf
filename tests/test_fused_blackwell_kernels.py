import pytest
import torch
import ctypes
import math
import os

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






@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_fused_cross_entropy_correctness():
    so_path = "csrc/fused_blackwell_cross_entropy.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_cross_entropy.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_void_p
    ]

    N = 32
    V = 128
    logits = torch.randn(N, V, device='cuda', dtype=torch.float32, requires_grad=True)
    targets = torch.randint(0, V, (N,), device='cuda', dtype=torch.int32)

    loss_out = torch.zeros(N, device='cuda', dtype=torch.float32)
    grad_out = torch.zeros(N, V, device='cuda', dtype=torch.float32)

    lib.launch_fused_blackwell_cross_entropy(
        ctypes.c_void_p(logits.data_ptr()),
        ctypes.c_void_p(targets.data_ptr()),
        ctypes.c_void_p(loss_out.data_ptr()),
        ctypes.c_void_p(grad_out.data_ptr()),
        N, V, 0.0, None
    )
    torch.cuda.synchronize()

    # PyTorch reference
    ref_loss = torch.nn.functional.cross_entropy(logits, targets.long(), reduction='none')
    loss_diff = torch.max(torch.abs(loss_out - ref_loss)).item()
    assert loss_diff < 1e-4, f"Loss mismatch: {loss_diff}"

    # Verify gradients
    ref_loss.sum().backward()
    grad_diff = torch.max(torch.abs(grad_out - logits.grad)).item()
    assert grad_diff < 1e-4, f"Grad mismatch: {grad_diff}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_chunked_ssm_correctness():
    so_path = "csrc/fused_blackwell_chunked_ssm.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_chunked_ssm.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_void_p
    ]

    batch = 4
    seq_len = 32
    dim = 64
    delta = 0.05

    X = torch.randn(batch, seq_len, dim, device='cuda', dtype=torch.float32)
    A_diag = -torch.rand(dim, device='cuda', dtype=torch.float32) - 0.1
    B_vec = torch.randn(dim, device='cuda', dtype=torch.float32)
    C_vec = torch.randn(dim, device='cuda', dtype=torch.float32)
    Y_out = torch.zeros_like(X)

    lib.launch_fused_blackwell_chunked_ssm(
        ctypes.c_void_p(X.data_ptr()),
        ctypes.c_void_p(A_diag.data_ptr()),
        ctypes.c_void_p(B_vec.data_ptr()),
        ctypes.c_void_p(C_vec.data_ptr()),
        ctypes.c_void_p(Y_out.data_ptr()),
        batch, seq_len, dim, delta, None
    )
    torch.cuda.synchronize()

    # Analytical CPU reference
    a_bar = torch.exp(delta * A_diag)
    b_bar = delta * B_vec
    ref_Y = torch.zeros_like(X)
    h = torch.zeros(batch, dim, device='cuda', dtype=torch.float32)
    for t in range(seq_len):
        h = a_bar * h + b_bar * X[:, t, :]
        ref_Y[:, t, :] = C_vec * h

    diff = torch.max(torch.abs(Y_out - ref_Y)).item()
    assert diff < 1e-4, f"SSM output diff too large: {diff}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_mope_router_correctness():
    so_path = "csrc/fused_blackwell_mope_router.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_mope_router.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.c_float, ctypes.c_void_p
    ]

    batch_size = 16
    dim = 64
    num_experts = 32
    top_k = 4
    temperature = 1.0

    tokens = torch.randn(batch_size, dim, device='cuda', dtype=torch.float32)
    polytope_centroids = torch.randn(num_experts, dim, device='cuda', dtype=torch.float32)
    # Normalize centroids to lie on sphere
    polytope_centroids = polytope_centroids / torch.norm(polytope_centroids, dim=-1, keepdim=True)

    selected_experts = torch.zeros(batch_size, top_k, device='cuda', dtype=torch.int32)
    routing_weights = torch.zeros(batch_size, top_k, device='cuda', dtype=torch.float32)

    ret = lib.launch_fused_blackwell_mope_router(
        ctypes.c_void_p(tokens.data_ptr()),
        ctypes.c_void_p(polytope_centroids.data_ptr()),
        ctypes.c_void_p(selected_experts.data_ptr()),
        ctypes.c_void_p(routing_weights.data_ptr()),
        batch_size, dim, num_experts, top_k, temperature, None
    )
    torch.cuda.synchronize()
    assert ret == 0

    # Verify with PyTorch reference
    scores = torch.matmul(tokens, polytope_centroids.T) / temperature
    ref_weights, ref_indices = torch.topk(scores, top_k, dim=-1)
    ref_probs = torch.softmax(ref_weights, dim=-1)

    # Check top indices match
    assert torch.equal(selected_experts, ref_indices.to(torch.int32))
    # Check softmax weights match
    weight_diff = torch.max(torch.abs(routing_weights - ref_probs)).item()
    assert weight_diff < 1e-4, f"Routing weights diff: {weight_diff}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_bit_linear_residual_correctness():
    so_path = "csrc/fused_blackwell_bit_linear_residual.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_bit_linear_residual.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p
    ]

    batch_size = 8
    in_dim = 64
    out_dim = 32

    x = torch.randn(batch_size, in_dim, device='cuda', dtype=torch.float32)
    residual = torch.randn(batch_size, out_dim, device='cuda', dtype=torch.float32)
    scales = torch.rand(out_dim, device='cuda', dtype=torch.float32) + 0.5
    y_out = torch.zeros(batch_size, out_dim, device='cuda', dtype=torch.float32)

    # Generate random 2-bit codes in {0, 1, 3} mapped to {0, +1, -1}
    # 4 codes per byte
    packed_w = torch.randint(0, 256, (out_dim, in_dim // 4), device='cuda', dtype=torch.uint8)

    ret = lib.launch_fused_blackwell_bit_linear_residual(
        ctypes.c_void_p(x.data_ptr()),
        ctypes.c_void_p(packed_w.data_ptr()),
        ctypes.c_void_p(residual.data_ptr()),
        ctypes.c_void_p(scales.data_ptr()),
        ctypes.c_void_p(y_out.data_ptr()),
        batch_size, in_dim, out_dim, None
    )
    torch.cuda.synchronize()
    assert ret == 0

    # CPU / PyTorch unpack reference
    w_unpacked = torch.zeros(out_dim, in_dim, device='cuda', dtype=torch.float32)
    for p in range(in_dim // 4):
        byte_col = packed_w[:, p]
        for i in range(4):
            code = (byte_col >> (i * 2)) & 0x03
            # Map code: 1 -> +1, 3 -> -1, else 0
            w_unpacked[:, p * 4 + i] = torch.where(code == 1, 1.0, torch.where(code == 3, -1.0, 0.0))

    # Analytical reference: y = (x @ W.T) * scales + residual
    ref_y = torch.matmul(x, w_unpacked.T) * scales.unsqueeze(0) + residual
    diff = torch.max(torch.abs(y_out - ref_y)).item()
    assert diff < 1e-4, f"Bit-linear output diff: {diff}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_fused_swiglu_mlp_correctness():
    so_path = "csrc/fused_blackwell_swiglu_mlp.so"
    lib = ctypes.CDLL(so_path)
    lib.launch_fused_blackwell_swiglu_mlp.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_void_p
    ]

    batch_size = 16
    hidden_dim = 128
    beta = 1.0

    gate = torch.randn(batch_size, hidden_dim, device='cuda', dtype=torch.float32)
    up = torch.randn(batch_size, hidden_dim, device='cuda', dtype=torch.float32)
    residual = torch.randn(batch_size, hidden_dim, device='cuda', dtype=torch.float32)
    y_out = torch.zeros(batch_size, hidden_dim, device='cuda', dtype=torch.float32)

    ret = lib.launch_fused_blackwell_swiglu_mlp(
        ctypes.c_void_p(gate.data_ptr()),
        ctypes.c_void_p(up.data_ptr()),
        ctypes.c_void_p(residual.data_ptr()),
        ctypes.c_void_p(y_out.data_ptr()),
        batch_size, hidden_dim, beta, None
    )
    torch.cuda.synchronize()
    assert ret == 0

    # PyTorch reference: silu(gate) * up + residual
    ref_y = (gate * torch.sigmoid(beta * gate)) * up + residual
    diff = torch.max(torch.abs(y_out - ref_y)).item()
    assert diff < 1e-4, f"SwiGLU output diff: {diff}"

def test_fused_spinning_polytope_torque_correctness():
    so_path = "csrc/fused_blackwell_spinning_polytope_torque.so"
    assert os.path.exists(so_path), "Shared library does not exist"
    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_spinning_polytope_torque_forward.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_float, ctypes.c_float
    ]

    B = 4
    D = 16
    eta = 0.05
    dt = 0.01

    # Use CPU tensors for broad compatibility and verification
    torch.manual_seed(42)
    x = torch.randn(B, D, dtype=torch.float32)
    h_in = torch.randn(B, D, dtype=torch.float32)
    omega = torch.zeros(B, D, D, dtype=torch.float32)
    h_out = torch.zeros(B, D, dtype=torch.float32)

    ret = lib.fused_blackwell_spinning_polytope_torque_forward(
        ctypes.c_void_p(x.data_ptr()),
        ctypes.c_void_p(h_in.data_ptr()),
        ctypes.c_void_p(omega.data_ptr()),
        ctypes.c_void_p(h_out.data_ptr()),
        B, D, eta, dt
    )
    assert ret == 0

    # Reference Python/PyTorch computation
    # tau = x.unsqueeze(2) @ h_in.unsqueeze(1) - h_in.unsqueeze(2) @ x.unsqueeze(1)
    ref_omega = torch.zeros(B, D, D, dtype=torch.float32)
    for b in range(B):
        tau = torch.outer(x[b], h_in[b]) - torch.outer(h_in[b], x[b])
        ref_omega[b] += eta * tau

    diff_omega = torch.max(torch.abs(omega - ref_omega)).item()
    assert diff_omega < 1e-5, f"Omega torque diff: {diff_omega}"

    # Verify skew-symmetry: omega + omega.T == 0
    for b in range(B):
        skew_err = torch.max(torch.abs(omega[b] + omega[b].T)).item()
        assert skew_err < 1e-5, f"Skew-symmetry violation: {skew_err}"

    # Verify h_out: h + dt * Omega @ h + 0.5 * dt^2 * Omega @ Omega @ h
    ref_h_out = torch.zeros(B, D, dtype=torch.float32)
    for b in range(B):
        v1 = torch.mv(ref_omega[b], h_in[b])
        v2 = torch.mv(ref_omega[b], v1)
        ref_h_out[b] = h_in[b] + dt * v1 + 0.5 * dt * dt * v2

    diff_h = torch.max(torch.abs(h_out - ref_h_out)).item()
    assert diff_h < 1e-5, f"Rotated state diff: {diff_h}"

def test_fused_padic_tree_routing_correctness():
    so_path = "csrc/fused_blackwell_ultrametric_padic_tree_routing.so"
    assert os.path.exists(so_path), "Shared library does not exist"
    lib = ctypes.CDLL(so_path)

    lib.fused_blackwell_padic_tree_routing_forward.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int
    ]

    B = 8
    D = 16
    K = 4
    p = 2

    tokens = torch.randint(0, 1000, (B, D), dtype=torch.int32)
    centers = torch.randint(0, 1000, (K, D), dtype=torch.int32)
    # Give token 0 an exact match with center 2
    centers[2] = tokens[0].clone()

    best_branch = torch.zeros(B, dtype=torch.int32)
    min_dist = torch.zeros(B, dtype=torch.float32)

    ret = lib.fused_blackwell_padic_tree_routing_forward(
        ctypes.c_void_p(tokens.data_ptr()),
        ctypes.c_void_p(centers.data_ptr()),
        ctypes.c_void_p(best_branch.data_ptr()),
        ctypes.c_void_p(min_dist.data_ptr()),
        B, D, K, p
    )
    assert ret == 0
    # Token 0 should route to center 2 with near zero distance
    assert best_branch[0].item() == 2
    assert min_dist[0].item() < 1e-4

def test_fused_coxeter_billiards_correctness():
    so_path = "csrc/fused_blackwell_hyperbolic_coxeter_billiards.so"
    assert os.path.exists(so_path), "Shared library does not exist"
    lib = ctypes.CDLL(so_path)

    lib.fused_blackwell_hyperbolic_coxeter_billiards_forward.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_float
    ]

    B = 4
    D = 8
    K = 2
    dt = 0.1

    # Simple root along axis 0
    roots = torch.zeros(K, D, dtype=torch.float32)
    roots[0, 0] = 1.0 # Hyperplane x_0 = 0
    roots[1, 1] = 1.0 # Hyperplane x_1 = 0
    root_sq = torch.sum(roots * roots, dim=1)

    # Particle moving towards hyperplane x_0 = 0 from positive to negative
    x_in = torch.tensor([[0.05, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                         [0.50, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                         [1.00, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                         [2.00, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]], dtype=torch.float32)
    v_in = torch.tensor([[-1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                         [-0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                         [ 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                         [ 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]], dtype=torch.float32)

    x_out = torch.zeros_like(x_in)
    v_out = torch.zeros_like(v_in)

    ret = lib.fused_blackwell_hyperbolic_coxeter_billiards_forward(
        ctypes.c_void_p(x_in.data_ptr()),
        ctypes.c_void_p(v_in.data_ptr()),
        ctypes.c_void_p(roots.data_ptr()),
        ctypes.c_void_p(root_sq.data_ptr()),
        ctypes.c_void_p(x_out.data_ptr()),
        ctypes.c_void_p(v_out.data_ptr()),
        B, D, K, dt
    )
    assert ret == 0

    # Particle 0: initial x=0.05, v=-1.0, dt=0.1 -> unreflected x = -0.05 < 0.
    # Reflected: v_0 should flip sign to +1.0, x_0 should flip sign to +0.05!
    assert abs(v_out[0, 0].item() - 1.0) < 1e-4
    assert abs(x_out[0, 0].item() - 0.05) < 1e-4

    # Particle 1: x=0.50, v=-0.1, dt=0.1 -> x = 0.49 > 0 (no collision), v stays -0.1
    assert abs(v_out[1, 0].item() - (-0.1)) < 1e-4
    assert abs(x_out[1, 0].item() - 0.49) < 1e-4


def test_fused_bruhat_tits_walk_correctness():
    so_path = "csrc/fused_blackwell_bruhat_tits_walk.so"
    assert os.path.exists(so_path)
    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_bruhat_tits_walk.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_float
    ]

    B = 2
    D = 4
    K = 2
    step_size = 0.2

    # Affine roots: H0 is x_0 = 1.0 (normal [1, 0, 0, 0], offset 1.0)
    roots = torch.tensor([[1.0, 0.0, 0.0, 0.0],
                          [0.0, 1.0, 0.0, 0.0]], dtype=torch.float32)
    offsets = torch.tensor([1.0, 0.5], dtype=torch.float32)
    root_sq = torch.sum(roots * roots, dim=1)

    # Particle 0: pos = [1.1, 0.0, 0.0, 0.0], dir = [-1.0, 0.0, 0.0, 0.0]
    # after step 0.2, pos = [0.9, 0.0, 0.0, 0.0] -> crosses wall at x_0 = 1.0!
    # dist to wall = 0.9 - 1.0 = -0.1.
    # Reflected pos = 0.9 - 2 * (-0.1) * 1.0 = 1.1!
    # Reflected dir = -1.0 - 2 * (-1.0) * 1.0 = +1.0!
    x_in = torch.tensor([[1.1, 0.0, 0.0, 0.0],
                         [2.0, 2.0, 0.0, 0.0]], dtype=torch.float32)
    v_in = torch.tensor([[-1.0, 0.0, 0.0, 0.0],
                         [ 0.1, 0.1, 0.0, 0.0]], dtype=torch.float32)
    x_out = torch.zeros_like(x_in)
    v_out = torch.zeros_like(v_in)
    chamber_ids = torch.tensor([0, 0], dtype=torch.int32)

    ret = lib.fused_blackwell_bruhat_tits_walk(
        ctypes.c_void_p(x_in.data_ptr()),
        ctypes.c_void_p(v_in.data_ptr()),
        ctypes.c_void_p(roots.data_ptr()),
        ctypes.c_void_p(offsets.data_ptr()),
        ctypes.c_void_p(root_sq.data_ptr()),
        ctypes.c_void_p(x_out.data_ptr()),
        ctypes.c_void_p(v_out.data_ptr()),
        ctypes.c_void_p(chamber_ids.data_ptr()),
        B, D, K, step_size
    )
    assert ret == 0

    # Particle 0 reflects back
    assert abs(x_out[0, 0].item() - 1.1) < 1e-4
    assert abs(v_out[0, 0].item() - 1.0) < 1e-4
    assert chamber_ids[0].item() != 0

    # Particle 1 steps without crossing: 2.0 + 0.1*0.2 = 2.02
    assert abs(x_out[1, 0].item() - 2.02) < 1e-4
    assert abs(v_out[1, 0].item() - 0.1) < 1e-4


def test_fused_adelic_product_formula_correctness():
    so_path = "csrc/fused_blackwell_adelic_product_formula.so"
    assert os.path.exists(so_path)
    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_adelic_product_formula.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int
    ]

    B = 2
    D = 4
    x_in = torch.tensor([[6.0, 8.0, 0.0, 0.0],
                         [3.0, 4.0, 0.0, 0.0]], dtype=torch.float32)
    tokens_in = torch.tensor([12, 50], dtype=torch.int32)

    arch_norm_out = torch.zeros(B, dtype=torch.float32)
    padic_norms_out = torch.zeros(B, 4, dtype=torch.float32)
    adelic_product_out = torch.zeros(B, dtype=torch.float32)

    ret = lib.fused_blackwell_adelic_product_formula(
        ctypes.c_void_p(x_in.data_ptr()),
        ctypes.c_void_p(tokens_in.data_ptr()),
        ctypes.c_void_p(arch_norm_out.data_ptr()),
        ctypes.c_void_p(padic_norms_out.data_ptr()),
        ctypes.c_void_p(adelic_product_out.data_ptr()),
        B, D
    )
    assert ret == 0

    # Token 12: |12|_2 = 0.25, |12|_3 = 1/3, |12|_5 = 1.0, |12|_7 = 1.0
    assert abs(arch_norm_out[0].item() - 10.0) < 1e-4
    assert abs(padic_norms_out[0, 0].item() - 0.25) < 1e-4
    assert abs(padic_norms_out[0, 1].item() - 1.0 / 3.0) < 1e-4
    assert abs(padic_norms_out[0, 2].item() - 1.0) < 1e-4
    assert abs(padic_norms_out[0, 3].item() - 1.0) < 1e-4
    expected_prod_0 = 10.0 * 0.25 * (1.0 / 3.0)
    assert abs(adelic_product_out[0].item() - expected_prod_0) < 1e-4

    # Token 50 = 2 * 5^2: |50|_2 = 0.5, |50|_3 = 1.0, |50|_5 = 1/25 = 0.04, |50|_7 = 1.0
    assert abs(arch_norm_out[1].item() - 5.0) < 1e-4
    assert abs(padic_norms_out[1, 0].item() - 0.5) < 1e-4
    assert abs(padic_norms_out[1, 1].item() - 1.0) < 1e-4
    assert abs(padic_norms_out[1, 2].item() - 0.04) < 1e-4
    expected_prod_1 = 5.0 * 0.5 * 0.04
    assert abs(adelic_product_out[1].item() - expected_prod_1) < 1e-4


def test_fused_tate_pairing_curve_correctness():
    so_path = "csrc/fused_blackwell_tate_pairing_curve.so"
    assert os.path.exists(so_path)
    lib = ctypes.CDLL(so_path)

    lib.fused_blackwell_tate_pairing_curve.argtypes = [
        ctypes.c_void_p,  # P_coords
        ctypes.c_void_p,  # Q_coords
        ctypes.c_void_p,  # curve_params
        ctypes.c_void_p,  # pairing_out
        ctypes.c_void_p,  # isogeny_out
        ctypes.c_int      # B
    ]
    lib.fused_blackwell_tate_pairing_curve.restype = ctypes.c_int

    B = 4
    # Points P = (x, y)
    P = torch.tensor([
        [1.0, 2.0],
        [2.0, 3.0],
        [0.5, 1.5],
        [3.0, 4.0]
    ], dtype=torch.float32)

    # Points Q = (x, y)
    Q = torch.tensor([
        [1.5, 2.5],
        [2.5, 3.5],
        [1.0, 2.0],
        [3.5, 4.5]
    ], dtype=torch.float32)

    # curve_params: (a, b, r, ell)
    params = torch.tensor([1.0, 1.0, 5.0, 2.0], dtype=torch.float32)

    pairing_out = torch.zeros(B, dtype=torch.float32)
    isogeny_out = torch.zeros(B, 2, dtype=torch.float32)

    ret = lib.fused_blackwell_tate_pairing_curve(
        ctypes.c_void_p(P.data_ptr()),
        ctypes.c_void_p(Q.data_ptr()),
        ctypes.c_void_p(params.data_ptr()),
        ctypes.c_void_p(pairing_out.data_ptr()),
        ctypes.c_void_p(isogeny_out.data_ptr()),
        B
    )
    assert ret == 0

    # Verify pairing output is non-zero and bounded within [-1, 1] due to tanh normalization
    assert (torch.abs(pairing_out) <= 1.0).all()
    assert (pairing_out != 0).any()

    # Verify isogeny walk: phi(x) = xp + ell * (xp / (xp^2 + 1))
    # For P[0] = (1.0, 2.0), ell = 2.0:
    # isog_x = 1.0 + 2.0 * (1.0 / (1.0 + 1.0)) = 1.0 + 1.0 = 2.0
    # isog_y = 2.0 * (1.0 + 0.5 * 2.0 / 2.0) = 2.0 * 1.5 = 3.0
    assert abs(isogeny_out[0, 0].item() - 2.0) < 1e-4
    assert abs(isogeny_out[0, 1].item() - 3.0) < 1e-4


def test_fused_weil_reciprocity_divisor_correctness():
    so_path = "csrc/fused_blackwell_weil_reciprocity_divisor.so"
    assert os.path.exists(so_path)
    lib = ctypes.CDLL(so_path)

    lib.fused_blackwell_weil_reciprocity_divisor.argtypes = [
        ctypes.c_void_p,  # P_points
        ctypes.c_void_p,  # Q_points
        ctypes.c_void_p,  # curve_params
        ctypes.c_void_p,  # f_div_g_out
        ctypes.c_void_p,  # g_div_f_out
        ctypes.c_void_p,  # reciprocity_diff
        ctypes.c_int      # B
    ]
    lib.fused_blackwell_weil_reciprocity_divisor.restype = ctypes.c_int

    B = 2
    # Construct points P and Q such that f(Q) == g(P) (exact reciprocity)
    # P = (xp, yp) = (2.0, 3.0)
    # Q = (xq, yq) = (3.0, 2.0)
    # params: a = 1.0, b = 0.0, c = 1.0, d = 0.0
    # f(Q) = (3^2 + 1*2 + 1) / (3^2 + 1) = (9 + 2 + 1) / 10 = 12 / 10 = 1.2
    # g(P) = (3^2 + 1*2 + 1) / (3^2 + 1) = (9 + 2 + 1) / 10 = 12 / 10 = 1.2
    # reciprocity diff = |1.2 - 1.2| = 0.0
    P = torch.tensor([
        [2.0, 3.0],
        [1.0, 1.0]
    ], dtype=torch.float32)

    Q = torch.tensor([
        [3.0, 2.0],
        [1.0, 1.0]
    ], dtype=torch.float32)

    params = torch.tensor([1.0, 0.0, 1.0, 0.0], dtype=torch.float32)

    f_out = torch.zeros(B, dtype=torch.float32)
    g_out = torch.zeros(B, dtype=torch.float32)
    diff_out = torch.zeros(B, dtype=torch.float32)

    ret = lib.fused_blackwell_weil_reciprocity_divisor(
        ctypes.c_void_p(P.data_ptr()),
        ctypes.c_void_p(Q.data_ptr()),
        ctypes.c_void_p(params.data_ptr()),
        ctypes.c_void_p(f_out.data_ptr()),
        ctypes.c_void_p(g_out.data_ptr()),
        ctypes.c_void_p(diff_out.data_ptr()),
        B
    )
    assert ret == 0

    assert abs(f_out[0].item() - 1.2) < 1e-4
    assert abs(g_out[0].item() - 1.2) < 1e-4
    assert abs(diff_out[0].item()) < 1e-5

    # For P[1] = (1, 1), Q[1] = (1, 1):
    # f(Q) = (1 + 1 + 1) / (1 + 1) = 3/2 = 1.5
    # g(P) = (1 + 1 + 1) / (1 + 1) = 3/2 = 1.5
    assert abs(f_out[1].item() - 1.5) < 1e-4
    assert abs(g_out[1].item() - 1.5) < 1e-4
    assert abs(diff_out[1].item()) < 1e-5


def test_fused_arakelov_intersection_correctness():
    so_path = "csrc/libfused_blackwell_arakelov_intersection.so"
    if not os.path.exists(so_path):
        so_path = "csrc/fused_blackwell_arakelov_intersection.so"
    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_arakelov_intersection.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int
    ]

    B = 2
    D1 = torch.tensor([
        [1.0, 2.0],
        [3.0, 4.0]
    ], dtype=torch.float32)

    D2 = torch.tensor([
        [2.0, 1.0],
        [1.0, 1.0]
    ], dtype=torch.float32)

    fin = torch.tensor([1.5, 2.0], dtype=torch.float32)
    params = torch.tensor([0.5, 1e-4], dtype=torch.float32)

    g_pq = torch.zeros(B, dtype=torch.float32)
    g_qp = torch.zeros(B, dtype=torch.float32)
    arakelov = torch.zeros(B, dtype=torch.float32)
    sym_diff = torch.zeros(B, dtype=torch.float32)

    ret = lib.fused_blackwell_arakelov_intersection(
        ctypes.c_void_p(D1.data_ptr()),
        ctypes.c_void_p(D2.data_ptr()),
        ctypes.c_void_p(fin.data_ptr()),
        ctypes.c_void_p(params.data_ptr()),
        ctypes.c_void_p(g_pq.data_ptr()),
        ctypes.c_void_p(g_qp.data_ptr()),
        ctypes.c_void_p(arakelov.data_ptr()),
        ctypes.c_void_p(sym_diff.data_ptr()),
        B
    )
    assert ret == 0

    # Symmetry check g_infty(P, Q) == g_infty(Q, P)
    for i in range(B):
        assert abs(g_pq[i].item() - g_qp[i].item()) < 1e-5
        assert sym_diff[i].item() < 1e-5
        # Arithmetic intersection is sum of finite + archimedean
        assert abs(arakelov[i].item() - (fin[i].item() + g_pq[i].item())) < 1e-5


def test_fused_grr_todd_chern_correctness():
    so_path = "csrc/libfused_blackwell_grr_todd_chern.so"
    if not os.path.exists(so_path):
        so_path = "csrc/fused_blackwell_grr_todd_chern.so"
    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_grr_todd_chern.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int
    ]

    B = 2
    # sheaf_params: rank, c1_e, c2_e
    sheaf = torch.tensor([
        [2.0, 3.0, 1.0],
        [1.0, 0.0, 0.0]
    ], dtype=torch.float32)

    # manifold_params: c1_x, c2_x
    manifold = torch.tensor([
        [1.0, 2.0],
        [2.0, 4.0]
    ], dtype=torch.float32)

    ch_out = torch.zeros(B, 3, dtype=torch.float32)
    td_out = torch.zeros(B, 3, dtype=torch.float32)
    chi_out = torch.zeros(B, dtype=torch.float32)
    add_res = torch.zeros(B, dtype=torch.float32)

    ret = lib.fused_blackwell_grr_todd_chern(
        ctypes.c_void_p(sheaf.data_ptr()),
        ctypes.c_void_p(manifold.data_ptr()),
        ctypes.c_void_p(ch_out.data_ptr()),
        ctypes.c_void_p(td_out.data_ptr()),
        ctypes.c_void_p(chi_out.data_ptr()),
        ctypes.c_void_p(add_res.data_ptr()),
        B
    )
    assert ret == 0

    # Sheaf 0: rank=2, c1=3, c2=1. ch0=2, ch1=3, ch2=0.5*(9 - 2)=3.5
    assert abs(ch_out[0, 0].item() - 2.0) < 1e-5
    assert abs(ch_out[0, 1].item() - 3.0) < 1e-5
    assert abs(ch_out[0, 2].item() - 3.5) < 1e-5

    # td0=1, td1=0.5*1=0.5, td2=(1+2)/12 = 0.25
    assert abs(td_out[0, 0].item() - 1.0) < 1e-5
    assert abs(td_out[0, 1].item() - 0.5) < 1e-5
    assert abs(td_out[0, 2].item() - 0.25) < 1e-5

    # chi = ch2*1 + ch1*td1 + ch0*td2 = 3.5*1 + 3*0.5 + 2*0.25 = 3.5 + 1.5 + 0.5 = 5.5
    assert abs(chi_out[0].item() - 5.5) < 1e-4

    # Additivity residual == 0
    assert abs(add_res[0].item()) < 1e-5


def test_fused_serre_duality_trace_correctness():
    so_path = "csrc/libfused_blackwell_serre_duality_trace.so"
    if not os.path.exists(so_path):
        so_path = "csrc/fused_blackwell_serre_duality_trace.so"
    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_serre_duality_trace.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int
    ]

    B = 2
    D = 4
    alpha = torch.tensor([
        [1.0, 2.0, 3.0, 4.0],
        [0.5, 1.0, 1.5, 2.0]
    ], dtype=torch.float32)

    beta = torch.tensor([
        [2.0, 1.0, 0.0, 1.0],
        [1.0, 1.0, 1.0, 1.0]
    ], dtype=torch.float32)

    scale = torch.tensor([1.5, 2.0], dtype=torch.float32)

    pair_out = torch.zeros(B, dtype=torch.float32)
    norm_out = torch.zeros(B, dtype=torch.float32)
    non_deg_res = torch.zeros(B, dtype=torch.float32)

    ret = lib.fused_blackwell_serre_duality_trace(
        ctypes.c_void_p(alpha.data_ptr()),
        ctypes.c_void_p(beta.data_ptr()),
        ctypes.c_void_p(scale.data_ptr()),
        ctypes.c_void_p(pair_out.data_ptr()),
        ctypes.c_void_p(norm_out.data_ptr()),
        ctypes.c_void_p(non_deg_res.data_ptr()),
        B, D
    )
    assert ret == 0

    # For batch 0: alpha=[1,2,3,4], beta=[2,1,0,1]
    # dot = 1*2 + 2*1 + 3*0 + 4*1 = 2 + 2 + 0 + 4 = 8
    # trace = 8 * 1.5 = 12.0
    assert abs(pair_out[0].item() - 12.0) < 1e-4

    # Non-degeneracy ratio > 0
    assert non_deg_res[0].item() > 0.0

def test_fused_kodaira_vanishing_filter_correctness():
    so_path = "csrc/fused_blackwell_kodaira_vanishing_filter.so"
    assert os.path.exists(so_path), "Shared library does not exist"
    lib = ctypes.CDLL(so_path)

    lib.fused_blackwell_kodaira_vanishing_filter.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int
    ]
    lib.fused_blackwell_kodaira_vanishing_filter.restype = ctypes.c_int

    B = 4
    D = 4
    n_dim = 2

    # Cohomological modes
    modes = torch.ones(B, D, dtype=torch.float32)
    # p degrees: [1, 2, 0, 2]
    # q degrees: [2, 1, 1, 0]
    # p+q:       [3, 3, 1, 2]
    # Since n_dim = 2:
    # Batch 0: p+q = 3 > 2 -> should vanish (if c1 > 0)
    # Batch 1: p+q = 3 > 2 -> should vanish
    # Batch 2: p+q = 1 <= 2 -> should NOT vanish
    # Batch 3: p+q = 2 <= 2 -> should NOT vanish
    p_deg = torch.tensor([1, 2, 0, 2], dtype=torch.int32)
    q_deg = torch.tensor([2, 1, 1, 0], dtype=torch.int32)
    c1 = torch.tensor([1.0, 2.5, 1.0, 0.5], dtype=torch.float32)

    filtered = torch.zeros(B, D, dtype=torch.float32)
    vanishing_flag = torch.zeros(B, dtype=torch.float32)
    res_energy = torch.zeros(B, dtype=torch.float32)

    ret = lib.fused_blackwell_kodaira_vanishing_filter(
        ctypes.c_void_p(modes.data_ptr()),
        ctypes.c_void_p(p_deg.data_ptr()),
        ctypes.c_void_p(q_deg.data_ptr()),
        ctypes.c_void_p(c1.data_ptr()),
        ctypes.c_void_p(filtered.data_ptr()),
        ctypes.c_void_p(vanishing_flag.data_ptr()),
        ctypes.c_void_p(res_energy.data_ptr()),
        B, D, n_dim
    )
    assert ret == 0

    # Check vanishing
    assert vanishing_flag[0].item() == 1.0
    assert vanishing_flag[1].item() == 1.0
    assert vanishing_flag[2].item() == 0.0
    assert vanishing_flag[3].item() == 0.0

    # Filtered modes for batch 0 and 1 must be exactly zero
    assert torch.all(filtered[0] == 0.0)
    assert torch.all(filtered[1] == 0.0)
    # Filtered modes for batch 2 and 3 must be intact (ones)
    assert torch.all(filtered[2] == 1.0)
    assert torch.all(filtered[3] == 1.0)

def test_fused_hardy_littlewood_circle_method_correctness():
    so_path = "csrc/fused_blackwell_hardy_littlewood_circle_method.so"
    assert os.path.exists(so_path), "Shared library does not exist"
    lib = ctypes.CDLL(so_path)

    lib.fused_blackwell_hardy_littlewood_circle_method.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int
    ]
    lib.fused_blackwell_hardy_littlewood_circle_method.restype = ctypes.c_int

    B = 3
    M_terms = 10

    # Batch 0: alpha = 0.0 (near 0/1 -> major arc)
    # Batch 1: alpha = 0.5 (near 1/2 -> major arc)
    # Batch 2: alpha = 0.29166 (midpoint between 1/4 and 1/3 -> minor arc)
    alphas = torch.tensor([0.0, 0.5, 0.29166], dtype=torch.float32)
    k_powers = torch.tensor([1, 2, 2], dtype=torch.int32)
    target_n = torch.tensor([0, 0, 5], dtype=torch.int32)

    exp_real = torch.zeros(B, dtype=torch.float32)
    exp_imag = torch.zeros(B, dtype=torch.float32)
    major_flags = torch.zeros(B, dtype=torch.float32)
    arc_energy = torch.zeros(B, dtype=torch.float32)

    ret = lib.fused_blackwell_hardy_littlewood_circle_method(
        ctypes.c_void_p(alphas.data_ptr()),
        ctypes.c_void_p(k_powers.data_ptr()),
        ctypes.c_void_p(target_n.data_ptr()),
        ctypes.c_void_p(exp_real.data_ptr()),
        ctypes.c_void_p(exp_imag.data_ptr()),
        ctypes.c_void_p(major_flags.data_ptr()),
        ctypes.c_void_p(arc_energy.data_ptr()),
        B, M_terms
    )
    assert ret == 0

    # For alpha = 0: phase = 0 -> cos(0)=1 -> exp_real = 1.0, exp_imag = 0.0
    assert abs(exp_real[0].item() - 1.0) < 1e-4
    assert abs(exp_imag[0].item()) < 1e-4
    assert major_flags[0].item() == 1.0
    assert major_flags[1].item() == 1.0
    assert major_flags[2].item() == 0.0

def test_fused_bsd_lfunction_euler_product_correctness():
    so_path = "csrc/fused_blackwell_bsd_lfunction_euler_product.so"
    assert os.path.exists(so_path), "Shared library does not exist"
    lib = ctypes.CDLL(so_path)

    lib.fused_blackwell_bsd_lfunction_euler_product.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int
    ]
    lib.fused_blackwell_bsd_lfunction_euler_product.restype = ctypes.c_int

    B = 2
    num_primes = 4
    primes = torch.tensor([2, 3, 5, 7], dtype=torch.int32)
    # Batch 0: a_p = [0, 0, 0, 0], s = 2.0 (pure Riemann zeta factors: (1 + p^{-3})^{-1})
    # Batch 1: a_p = [2, 0, 1, -1], s = 1.0
    traces_ap = torch.tensor([
        [0.0, 0.0, 0.0, 0.0],
        [2.0, 0.0, 1.0, -1.0]
    ], dtype=torch.float32)
    s_points = torch.tensor([2.0, 1.0], dtype=torch.float32)

    l_vals = torch.zeros(B, dtype=torch.float32)
    log_norms = torch.zeros(B, dtype=torch.float32)
    ranks = torch.zeros(B, dtype=torch.int32)

    ret = lib.fused_blackwell_bsd_lfunction_euler_product(
        ctypes.c_void_p(traces_ap.data_ptr()),
        ctypes.c_void_p(primes.data_ptr()),
        ctypes.c_void_p(s_points.data_ptr()),
        ctypes.c_void_p(l_vals.data_ptr()),
        ctypes.c_void_p(log_norms.data_ptr()),
        ctypes.c_void_p(ranks.data_ptr()),
        B, num_primes
    )
    assert ret == 0

    # L-value must be positive for batch 0
    assert l_vals[0].item() > 0.0
    # For batch 0 (s = 2.0), analytic rank is 0
    assert ranks[0].item() == 0


def test_fused_selmer_group_exact_sequence_correctness():
    so_path = "csrc/libfused_blackwell_selmer_group_exact_sequence.so"
    if not os.path.exists(so_path):
        pytest.skip(f"{so_path} not built")

    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_selmer_group_exact_sequence.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_float
    ]
    lib.fused_blackwell_selmer_group_exact_sequence.restype = ctypes.c_int

    B = 2
    num_places = 4
    weights = torch.tensor([1.0, 1.0, 0.5, 0.25], dtype=torch.float32)

    # Batch 0: cocycles exactly match bases (proj = cocycle, diff = 0 -> admissible, sha = 0)
    # Batch 1: cocycles have large obstruction (diff != 0 -> obstructed, sha > 0)
    cocycles = torch.tensor([
        [1.0, 1.0, 1.0, 1.0],
        [1.0, 2.0, 3.0, 4.0]
    ], dtype=torch.float32)

    bases = torch.tensor([
        [1.0, 1.0, 1.0, 1.0],
        [0.0, 0.0, 0.0, 0.0]
    ], dtype=torch.float32)

    proj = torch.zeros(B, num_places, dtype=torch.float32)
    admissibility = torch.zeros(B, dtype=torch.float32)
    sha_energy = torch.zeros(B, dtype=torch.float32)

    ret = lib.fused_blackwell_selmer_group_exact_sequence(
        ctypes.c_void_p(cocycles.data_ptr()),
        ctypes.c_void_p(bases.data_ptr()),
        ctypes.c_void_p(weights.data_ptr()),
        ctypes.c_void_p(proj.data_ptr()),
        ctypes.c_void_p(admissibility.data_ptr()),
        ctypes.c_void_p(sha_energy.data_ptr()),
        B, num_places, 1e-4
    )
    assert ret == 0

    # Batch 0 is admissible (Sha = 0)
    assert admissibility[0].item() == 1.0
    assert sha_energy[0].item() < 1e-5

    # Batch 1 is obstructed (Sha > 0, adm = 0)
    assert admissibility[1].item() == 0.0
    assert sha_energy[1].item() > 0.0


def test_fused_iwasawa_polynomial_quotient_correctness():
    so_path = "csrc/libfused_blackwell_iwasawa_polynomial_quotient.so"
    if not os.path.exists(so_path):
        pytest.skip(f"{so_path} not found")

    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_iwasawa_polynomial_quotient.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_float,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int
    ]
    lib.fused_blackwell_iwasawa_polynomial_quotient.restype = ctypes.c_int

    B = 2
    degree = 3
    div_degree = 1
    # P(T) = T^3 - 1 = (T - 1)(T^2 + T + 1)
    # Divisor: D(T) = T - 1 -> coeffs [-1.0, 1.0]
    # Poly: P(T) = -1 + 0*T + 0*T^2 + 1*T^3 -> coeffs [-1.0, 0.0, 0.0, 1.0]
    # Expected quotient: Q(T) = 1 + T + T^2 -> coeffs [1.0, 1.0, 1.0]
    poly = torch.tensor([
        [-1.0, 0.0, 0.0, 1.0],
        [-1.0, 0.0, 0.0, 1.0]
    ], dtype=torch.float32)

    div = torch.tensor([
        [-1.0, 1.0],
        [-1.0, 1.0]
    ], dtype=torch.float32)

    q_len = degree - div_degree + 1
    q_out = torch.zeros(B, q_len, dtype=torch.float32)
    rem_out = torch.zeros(B, dtype=torch.float32)
    mu_out = torch.zeros(B, dtype=torch.int32)
    lambda_out = torch.zeros(B, dtype=torch.int32)

    ret = lib.fused_blackwell_iwasawa_polynomial_quotient(
        ctypes.c_void_p(poly.data_ptr()),
        ctypes.c_void_p(div.data_ptr()),
        degree, div_degree, 3.0,
        ctypes.c_void_p(q_out.data_ptr()),
        ctypes.c_void_p(rem_out.data_ptr()),
        ctypes.c_void_p(mu_out.data_ptr()),
        ctypes.c_void_p(lambda_out.data_ptr()),
        B
    )
    assert ret == 0

    # Remainder norm should be 0.0 (exact division)
    assert rem_out[0].item() < 1e-4
    # Quotient coefficients: [1.0, 1.0, 1.0]
    assert torch.allclose(q_out[0], torch.tensor([1.0, 1.0, 1.0]), atol=1e-4)
    # Lambda invariant equals degree of quotient = 2
    assert lambda_out[0].item() == 2


def test_fused_tate_duality_pairing_correctness():
    so_path = "csrc/libfused_blackwell_tate_duality_pairing.so"
    if not os.path.exists(so_path):
        pytest.skip(f"{so_path} not found")

    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_tate_duality_pairing.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_float,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int
    ]
    lib.fused_blackwell_tate_duality_pairing.restype = ctypes.c_int

    B = 2
    dim = 4
    mod_m = 5.0

    # Batch 0: orthogonal cocycles (a . b = 0 -> pairing = 0, isometry norm > 0)
    # Batch 1: parallel non-zero cocycles (a . b = 4 -> pairing = 4, isometry norm = 0)
    cocycles_a = torch.tensor([
        [1.0, 0.0, 0.0, 0.0],
        [1.0, 1.0, 1.0, 1.0]
    ], dtype=torch.float32)

    cocycles_b = torch.tensor([
        [0.0, 1.0, 0.0, 0.0],
        [1.0, 1.0, 1.0, 1.0]
    ], dtype=torch.float32)

    p_vals = torch.zeros(B, dtype=torch.float32)
    iso_norms = torch.zeros(B, dtype=torch.float32)
    flags = torch.zeros(B, dtype=torch.float32)

    ret = lib.fused_blackwell_tate_duality_pairing(
        ctypes.c_void_p(cocycles_a.data_ptr()),
        ctypes.c_void_p(cocycles_b.data_ptr()),
        dim, mod_m,
        ctypes.c_void_p(p_vals.data_ptr()),
        ctypes.c_void_p(iso_norms.data_ptr()),
        ctypes.c_void_p(flags.data_ptr()),
        B
    )
    assert ret == 0

    # Batch 0: inner product is 0 -> p_vals[0] == 0, iso_norm = 1.0 * 1.0 = 1.0
    assert p_vals[0].item() < 1e-4
    assert abs(iso_norms[0].item() - 1.0) < 1e-4
    assert flags[0].item() == 1.0

    # Batch 1: inner product is 4.0 -> p_vals[1] == 4.0, iso_norm == 0.0
    assert abs(p_vals[1].item() - 4.0) < 1e-4
    assert iso_norms[1].item() < 1e-4
    assert flags[1].item() == 1.0


def test_fused_galois_deformation_ring_correctness():
    so_path = "csrc/libfused_blackwell_galois_deformation_ring.so"
    if not os.path.exists(so_path):
        pytest.skip(f"{so_path} not found")

    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_galois_deformation_ring.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_float
    ]
    lib.fused_blackwell_galois_deformation_ring.restype = ctypes.c_int

    batch_size = 2
    dim_tangent = 2
    dim_obstruction = 1
    lam = 0.1

    # Tangent basis: [B, dim_tangent, 4]
    # For batch 0: zeros
    # For batch 1: identity-like
    tangent_basis = torch.zeros(batch_size, dim_tangent * 4, dtype=torch.float32)
    tangent_basis[1, :4] = torch.tensor([1.0, 0.0, 0.0, 1.0])

    obstruction_coeffs = torch.zeros(batch_size, dim_obstruction * dim_tangent, dtype=torch.float32)
    obstruction_coeffs[1, 0] = 0.5

    deformation_matrix_out = torch.zeros(batch_size, 16, dtype=torch.float32)
    tangent_energy_norm = torch.zeros(batch_size, dtype=torch.float32)

    ret = lib.fused_blackwell_galois_deformation_ring(
        ctypes.c_void_p(tangent_basis.data_ptr()),
        ctypes.c_void_p(obstruction_coeffs.data_ptr()),
        ctypes.c_void_p(deformation_matrix_out.data_ptr()),
        ctypes.c_void_p(tangent_energy_norm.data_ptr()),
        batch_size,
        dim_tangent,
        dim_obstruction,
        lam
    )
    assert ret == 0

    # Batch 0: tangent is 0, so deformation matrix is identity
    mat0 = deformation_matrix_out[0].reshape(4, 4)
    assert torch.allclose(mat0, torch.eye(4), atol=1e-4)
    assert tangent_energy_norm[0].item() < 1e-3

    # Batch 1: has non-zero tangent norm and deformation
    assert tangent_energy_norm[1].item() > 0.0
    mat1 = deformation_matrix_out[1].reshape(4, 4)
    assert not torch.allclose(mat1, torch.eye(4), atol=1e-3)


def test_fused_fontaine_mazur_weights_correctness():
    so_path = "csrc/libfused_blackwell_fontaine_mazur_weights.so"
    if not os.path.exists(so_path):
        pytest.skip(f"{so_path} not found")

    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_fontaine_mazur_weights.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_float
    ]
    lib.fused_blackwell_fontaine_mazur_weights.restype = ctypes.c_int

    batch_size = 2
    dim_n = 2
    p_prime = 5.0

    # Representation matrix: [B, 2, 2]
    # Batch 0: weights are 0 and 1 (eigenvalues 1.0 and 5.0)
    rep_mat = torch.zeros(batch_size, dim_n * dim_n, dtype=torch.float32)
    rep_mat[0, 0] = 1.0  # log_5(1) = 0
    rep_mat[0, 3] = 5.0  # log_5(5) = 1

    # Frobenius matrix: [B, 2, 2]
    frob_mat = torch.zeros(batch_size, dim_n * dim_n, dtype=torch.float32)
    frob_mat[0, 0] = 2.0
    frob_mat[0, 3] = 3.0  # Trace = 2 + 3 = 5.0

    weights_out = torch.zeros(batch_size, dim_n, dtype=torch.float32)
    trace_out = torch.zeros(batch_size, dtype=torch.float32)
    purity_out = torch.zeros(batch_size, dtype=torch.float32)

    ret = lib.fused_blackwell_fontaine_mazur_weights(
        ctypes.c_void_p(rep_mat.data_ptr()),
        ctypes.c_void_p(frob_mat.data_ptr()),
        ctypes.c_void_p(weights_out.data_ptr()),
        ctypes.c_void_p(trace_out.data_ptr()),
        ctypes.c_void_p(purity_out.data_ptr()),
        batch_size,
        dim_n,
        p_prime
    )
    assert ret == 0

    # Verify Hodge-Tate weights for batch 0
    assert abs(weights_out[0, 0].item() - 0.0) < 1e-4
    assert abs(weights_out[0, 1].item() - 1.0) < 1e-4
    # Verify Frobenius trace
    assert abs(trace_out[0].item() - 5.0) < 1e-4
    # Verify geometric purity
    assert purity_out[0].item() == 1.0


def test_fused_serre_modularity_conductor_correctness():
    so_path = "csrc/libfused_blackwell_serre_modularity_conductor.so"
    if not os.path.exists(so_path):
        pytest.skip(f"{so_path} not found")

    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_serre_modularity_conductor.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_float
    ]
    lib.fused_blackwell_serre_modularity_conductor.restype = ctypes.c_int

    batch_size = 2
    num_primes = 2
    p_prime = 7.0

    # Conjugation matrix: [B, 4]
    # Batch 0: diag(1, -1) -> det = -1 (odd)
    # Batch 1: diag(1, 1) -> det = 1 (even)
    conj_mat = torch.tensor([
        [1.0, 0.0, 0.0, -1.0],
        [1.0, 0.0, 0.0, 1.0]
    ], dtype=torch.float32)

    # Primes and exponents: q1=2, q2=3; e1=1, e2=2 -> N = 2^1 * 3^2 = 18 -> log(18) ~ 2.89037
    primes = torch.tensor([
        [2.0, 3.0],
        [2.0, 3.0]
    ], dtype=torch.float32)

    exps = torch.tensor([
        [1.0, 2.0],
        [0.0, 0.0]
    ], dtype=torch.float32)

    odd_flags = torch.zeros(batch_size, dtype=torch.float32)
    level_logs = torch.zeros(batch_size, dtype=torch.float32)
    weights = torch.zeros(batch_size, dtype=torch.float32)

    ret = lib.fused_blackwell_serre_modularity_conductor(
        ctypes.c_void_p(conj_mat.data_ptr()),
        ctypes.c_void_p(primes.data_ptr()),
        ctypes.c_void_p(exps.data_ptr()),
        ctypes.c_void_p(odd_flags.data_ptr()),
        ctypes.c_void_p(level_logs.data_ptr()),
        ctypes.c_void_p(weights.data_ptr()),
        batch_size,
        num_primes,
        p_prime
    )
    assert ret == 0

    # Batch 0: Odd representation
    assert odd_flags[0].item() == 1.0
    expected_log = math.log(18.0)
    assert abs(level_logs[0].item() - expected_log) < 1e-4
    assert weights[0].item() >= 2.0

    # Batch 1: Even representation
    assert odd_flags[1].item() == 0.0


def test_fused_langlands_tunnell_base_change_correctness():
    so_path = "csrc/libfused_blackwell_langlands_tunnell_base_change.so"
    if not os.path.exists(so_path):
        pytest.skip("Langlands-Tunnell base change kernel library not compiled")

    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_langlands_tunnell_base_change.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int
    ]
    lib.fused_blackwell_langlands_tunnell_base_change.restype = ctypes.c_int

    batch_size = 2
    num_places = 3
    cyclic_degree = 2

    # base_traces: [2, 3]
    # batch 0: a_v = [2.0, 0.0, -1.0], inertia d_v = [1.0, 2.0, 3.0]
    # deg 1: a_v = 2.0 -> 2.0
    # deg 2: a_v^2 - 2 = 0 - 2 = -2.0
    # deg 3: a_v^3 - 3*a_v = (-1)^3 - 3*(-1) = -1 + 3 = 2.0
    base_traces = torch.tensor([
        [2.0, 0.0, -1.0],
        [1.0, 2.0, 0.0]
    ], dtype=torch.float32)

    inertia = torch.tensor([
        [1.0, 2.0, 3.0],
        [1.0, 1.0, 2.0]
    ], dtype=torch.float32)

    # cond(pi) = 15, disc(K/F) = 5
    # log(cond(Pi)) = 2 * log(15) + 2 * log(5) = log(15^2 * 5^2) = log(225 * 25) = log(5625)
    base_cond = torch.tensor([15.0, 1.0], dtype=torch.float32)
    rel_disc = torch.tensor([5.0, 1.0], dtype=torch.float32)

    # Order of projective image: 12 (tetrahedral A_4), 60 (icosahedral A_5, not solvable by radicals!)
    proj_orders = torch.tensor([12.0, 60.0], dtype=torch.float32)

    lifted_traces = torch.zeros(batch_size, num_places, dtype=torch.float32)
    lifted_cond_log = torch.zeros(batch_size, dtype=torch.float32)
    solvability = torch.zeros(batch_size, dtype=torch.float32)

    ret = lib.fused_blackwell_langlands_tunnell_base_change(
        ctypes.c_void_p(base_traces.data_ptr()),
        ctypes.c_void_p(inertia.data_ptr()),
        ctypes.c_void_p(base_cond.data_ptr()),
        ctypes.c_void_p(rel_disc.data_ptr()),
        ctypes.c_void_p(proj_orders.data_ptr()),
        ctypes.c_void_p(lifted_traces.data_ptr()),
        ctypes.c_void_p(lifted_cond_log.data_ptr()),
        ctypes.c_void_p(solvability.data_ptr()),
        batch_size,
        num_places,
        cyclic_degree
    )
    assert ret == 0

    # Batch 0 checks:
    assert solvability[0].item() == 1.0
    assert abs(lifted_traces[0, 0].item() - 2.0) < 1e-4
    assert abs(lifted_traces[0, 1].item() - (-2.0)) < 1e-4
    assert abs(lifted_traces[0, 2].item() - 2.0) < 1e-4
    expected_log_cond = math.log(5625.0)
    assert abs(lifted_cond_log[0].item() - expected_log_cond) < 1e-3

    # Batch 1 checks (A_5 is not solvable):
    assert solvability[1].item() == 0.0


def test_fused_taylor_wiles_patching_correctness():
    so_path = "csrc/libfused_blackwell_taylor_wiles_patching.so"
    if not os.path.exists(so_path):
        pytest.skip("Taylor-Wiles patching kernel library not compiled")

    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_taylor_wiles_patching.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int, ctypes.c_int, ctypes.c_int
    ]
    lib.fused_blackwell_taylor_wiles_patching.restype = ctypes.c_int

    batch_size = 2
    num_primes = 4
    required_r = 2

    # Batch 0: p=3, p^n = 9. Candidates: 19 (19 = 1 mod 9), 37 (37 = 1 mod 9), 7 (7 = 1 mod 3, but not mod 9), 11
    # For 19: a_q = 2, delta = 4 - 4*19 = 4 - 76 = -72 = 0 mod 3 -> NOT distinct (mod 3 = 0)
    # Let's pick a_q such that delta != 0 mod 3:
    # For q=19: if a_q = 1, delta = 1 - 76 = -75 = 0 mod 3. If a_q = 0, delta = -76 = -1 = 2 mod 3 != 0!
    # For q=37: 37 = 1 mod 9. a_q = 0, delta = -4*37 = -148 = -1 = 2 mod 3 != 0!
    candidates = torch.tensor([
        [19.0, 37.0, 7.0, 11.0],
        [5.0, 7.0, 11.0, 13.0]
    ], dtype=torch.float32)

    traces = torch.tensor([
        [0.0, 0.0, 1.0, 2.0],
        [1.0, 1.0, 1.0, 1.0]
    ], dtype=torch.float32)

    p_powers = torch.tensor([9.0, 25.0], dtype=torch.float32)
    primes = torch.tensor([3.0, 5.0], dtype=torch.float32)

    valid_counts = torch.zeros(batch_size, dtype=torch.float32)
    defects = torch.zeros(batch_size, dtype=torch.float32)
    flags = torch.zeros(batch_size, dtype=torch.float32)

    ret = lib.fused_blackwell_taylor_wiles_patching(
        ctypes.c_void_p(candidates.data_ptr()),
        ctypes.c_void_p(traces.data_ptr()),
        ctypes.c_void_p(p_powers.data_ptr()),
        ctypes.c_void_p(primes.data_ptr()),
        ctypes.c_void_p(valid_counts.data_ptr()),
        ctypes.c_void_p(defects.data_ptr()),
        ctypes.c_void_p(flags.data_ptr()),
        batch_size,
        num_primes,
        required_r
    )
    assert ret == 0

    # Batch 0: primes 19 and 37 both satisfy q = 1 mod 9 and delta != 0 mod 3 -> valid = 2
    assert valid_counts[0].item() == 2.0
    assert flags[0].item() == 1.0
    assert defects[0].item() == 0.0

    # Batch 1: no candidate = 1 mod 25 -> valid = 0, defect = 2
    assert valid_counts[1].item() == 0.0
    assert flags[1].item() == 0.0
    assert defects[1].item() == 2.0


def test_fused_khare_wintenberger_lifting_correctness():
    so_path = "csrc/libfused_blackwell_khare_wintenberger_lifting.so"
    if not os.path.exists(so_path):
        pytest.skip("Khare-Wintenberger lifting kernel library not compiled")

    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_khare_wintenberger_lifting.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int
    ]
    lib.fused_blackwell_khare_wintenberger_lifting.restype = ctypes.c_int

    batch_size = 2

    # Batch 0: a_p = 0.0, p = 3.0, k = 2 (k - 1 = 1), d = 1 ([Q:Q])
    # det(Phi) = 3^1 = 3. disc = 0 - 12 < 0 -> lambda_1 = 0.5, lambda_2 = 0.5 (sum = 1.0)
    # dim(R^\square) = 4 + 3*1 = 7.
    # Batch 1: a_p = 2.0, p = 5.0, k = 3 (k - 1 = 2), d = 2 ([F:Q] = 2)
    # det(Phi) = 5^2 = 25. disc = 4 - 100 < 0 -> lambda_1 = 1.0, lambda_2 = 1.0 (sum = 2.0)
    # dim(R^\square) = 4 + 3*2 = 10.
    ap = torch.tensor([0.0, 2.0], dtype=torch.float32)
    p = torch.tensor([3.0, 5.0], dtype=torch.float32)
    k = torch.tensor([2.0, 3.0], dtype=torch.float32)
    d = torch.tensor([1.0, 2.0], dtype=torch.float32)

    slopes = torch.zeros(batch_size, 2, dtype=torch.float32)
    framed_dims = torch.zeros(batch_size, dtype=torch.float32)
    flags = torch.zeros(batch_size, dtype=torch.float32)

    ret = lib.fused_blackwell_khare_wintenberger_lifting(
        ctypes.c_void_p(ap.data_ptr()),
        ctypes.c_void_p(p.data_ptr()),
        ctypes.c_void_p(k.data_ptr()),
        ctypes.c_void_p(d.data_ptr()),
        ctypes.c_void_p(slopes.data_ptr()),
        ctypes.c_void_p(framed_dims.data_ptr()),
        ctypes.c_void_p(flags.data_ptr()),
        batch_size
    )
    assert ret == 0

    # Batch 0:
    assert framed_dims[0].item() == 7.0
    assert abs(slopes[0, 0].item() - 0.5) < 1e-3
    assert abs(slopes[0, 1].item() - 0.5) < 1e-3
    assert flags[0].item() == 1.0

    # Batch 1:
    assert framed_dims[1].item() == 10.0
    assert abs(slopes[1, 0].item() - 1.0) < 1e-3
    assert abs(slopes[1, 1].item() - 1.0) < 1e-3
    assert flags[1].item() == 1.0


def test_fused_coleman_integration_correctness():
    so_path = "csrc/libfused_blackwell_coleman_integration.so"
    if not os.path.exists(so_path):
        pytest.skip("Coleman integration kernel library not compiled")

    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_coleman_integration.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_int, ctypes.c_int
    ]
    lib.fused_blackwell_coleman_integration.restype = ctypes.c_int

    batch_size = 2
    series_terms = 4

    # Batch 0: p = 5, g = 2, r = 1, #C(F_p) = 6, x = 0.1
    # r < g (1 < 2) -> flag = 1.0
    # bound = 6 + 2*2 - 2 = 8.0
    # det(Phi) = 5^2 = 25.0
    # integral = 0.1/1 + 0.01/2 + 0.001/3 + 0.0001/4 = 0.1053583
    # Batch 1: p = 7, g = 3, r = 3, #C(F_p) = 10, x = 0.0
    # r < g (3 < 3) -> False -> flag = 0.0
    # bound = 10 + 2*3 - 2 = 14.0
    # det(Phi) = 7^3 = 343.0
    # integral = 0.0
    p = torch.tensor([5.0, 7.0], dtype=torch.float32)
    g = torch.tensor([2.0, 3.0], dtype=torch.float32)
    r = torch.tensor([1.0, 3.0], dtype=torch.float32)
    nfp = torch.tensor([6.0, 10.0], dtype=torch.float32)
    x = torch.tensor([0.1, 0.0], dtype=torch.float32)

    integrals = torch.zeros(batch_size, dtype=torch.float32)
    dets = torch.zeros(batch_size, dtype=torch.float32)
    bounds = torch.zeros(batch_size, dtype=torch.float32)
    flags = torch.zeros(batch_size, dtype=torch.float32)

    ret = lib.fused_blackwell_coleman_integration(
        ctypes.c_void_p(p.data_ptr()),
        ctypes.c_void_p(g.data_ptr()),
        ctypes.c_void_p(r.data_ptr()),
        ctypes.c_void_p(nfp.data_ptr()),
        ctypes.c_void_p(x.data_ptr()),
        ctypes.c_void_p(integrals.data_ptr()),
        ctypes.c_void_p(dets.data_ptr()),
        ctypes.c_void_p(bounds.data_ptr()),
        ctypes.c_void_p(flags.data_ptr()),
        batch_size,
        series_terms
    )
    assert ret == 0

    # Batch 0 checks:
    assert flags[0].item() == 1.0
    assert bounds[0].item() == 8.0
    assert dets[0].item() == 25.0
    expected_int_0 = 0.1 + 0.01/2.0 + 0.001/3.0 + 0.0001/4.0
    assert abs(integrals[0].item() - expected_int_0) < 1e-4

    # Batch 1 checks:
    assert flags[1].item() == 0.0
    assert bounds[1].item() == 14.0
    assert dets[1].item() == 343.0
    assert abs(integrals[1].item()) < 1e-5


def test_fused_gross_zagier_height_correctness():
    so_path = "csrc/libfused_blackwell_gross_zagier_height.so"
    if not os.path.exists(so_path):
        pytest.skip("Gross-Zagier height kernel library not compiled")

    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_gross_zagier_height.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int
    ]
    lib.fused_blackwell_gross_zagier_height.restype = ctypes.c_int

    batch_size = 2
    # Batch 0: D = 7, (f, f) = 1.0, \hat{h}(y_K) = 0.5, u = 1.0
    # C = 8 * pi^2 * 1.0 / sqrt(7) = 78.9568 / 2.64575 = 29.8428
    # L'(E/K, 1) = 29.8428 * 0.5 = 14.9214 > 0 -> kolyvagin = 1.0, sha = 1.0
    # Batch 1: D = 11, (f, f) = 1.0, \hat{h}(y_K) = 0.0 (torsion point), u = 1.0
    # L'(E/K, 1) = 0.0 -> kolyvagin = 0.0, sha = 0.0
    d = torch.tensor([7.0, 11.0], dtype=torch.float32)
    f = torch.tensor([1.0, 1.0], dtype=torch.float32)
    h = torch.tensor([0.5, 0.0], dtype=torch.float32)
    u = torch.tensor([1.0, 1.0], dtype=torch.float32)

    lp = torch.zeros(batch_size, dtype=torch.float32)
    rk = torch.zeros(batch_size, dtype=torch.float32)
    sha = torch.zeros(batch_size, dtype=torch.float32)

    ret = lib.fused_blackwell_gross_zagier_height(
        ctypes.c_void_p(d.data_ptr()),
        ctypes.c_void_p(f.data_ptr()),
        ctypes.c_void_p(h.data_ptr()),
        ctypes.c_void_p(u.data_ptr()),
        ctypes.c_void_p(lp.data_ptr()),
        ctypes.c_void_p(rk.data_ptr()),
        ctypes.c_void_p(sha.data_ptr()),
        batch_size
    )
    assert ret == 0

    # Batch 0:
    assert rk[0].item() == 1.0
    assert sha[0].item() == 1.0
    assert abs(lp[0].item() - 14.9214) < 0.1

    # Batch 1:
    assert rk[1].item() == 0.0
    assert sha[1].item() == 0.0
    assert abs(lp[1].item()) < 1e-5


def test_fused_modular_symbols_manin_correctness():
    so_path = "csrc/libfused_blackwell_modular_symbols_manin.so"
    if not os.path.exists(so_path):
        pytest.skip("Modular symbols Manin kernel library not compiled")

    lib = ctypes.CDLL(so_path)
    lib.fused_blackwell_modular_symbols_manin.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_int
    ]
    lib.fused_blackwell_modular_symbols_manin.restype = ctypes.c_int

    batch_size = 2
    # Batch 0: p = 2, q = 5 (2/5 = [0; 2, 2]), N = 11
    # 2/5 -> steps = 3 (rem_p = 2, rem_q = 5 -> a=0, r=2; a=2, r=1; a=2, r=0)
    # unimodular = 1.0, torsion = 24 * 11 = 264.0, weight = 2/5 = 0.4
    # Batch 1: p = 3, q = 7 (3/7 = [0; 2, 3]), N = 37
    # torsion = 24 * 37 = 888.0, weight = 3/7
    p = torch.tensor([2, 3], dtype=torch.int32)
    q = torch.tensor([5, 7], dtype=torch.int32)
    n = torch.tensor([11, 37], dtype=torch.int32)

    steps = torch.zeros(batch_size, dtype=torch.float32)
    det = torch.zeros(batch_size, dtype=torch.float32)
    tors = torch.zeros(batch_size, dtype=torch.float32)
    wt = torch.zeros(batch_size, dtype=torch.float32)

    ret = lib.fused_blackwell_modular_symbols_manin(
        ctypes.c_void_p(p.data_ptr()),
        ctypes.c_void_p(q.data_ptr()),
        ctypes.c_void_p(n.data_ptr()),
        ctypes.c_void_p(steps.data_ptr()),
        ctypes.c_void_p(det.data_ptr()),
        ctypes.c_void_p(tors.data_ptr()),
        ctypes.c_void_p(wt.data_ptr()),
        batch_size
    )
    assert ret == 0

    # Batch 0:
    assert steps[0].item() >= 2.0
    assert det[0].item() == 1.0
    assert tors[0].item() == 264.0
    assert abs(wt[0].item() - 0.4) < 1e-4

    # Batch 1:
    assert steps[1].item() >= 2.0
    assert det[1].item() == 1.0
    assert tors[1].item() == 888.0
    assert abs(wt[1].item() - 3.0 / 7.0) < 1e-4


def test_fused_mazur_torsion_bound_correctness():
    """Validates the fused Blackwell SM 12.0 kernel for Mazur's torsion theorem bounds."""
    so_path = "csrc/libfused_blackwell_mazur_torsion_bound.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_mazur_torsion_benchmark.argtypes = [ctypes.c_int]
    lib.run_mazur_torsion_benchmark.restype = ctypes.c_int

    n_curves = 1024
    valid_count = lib.run_mazur_torsion_benchmark(n_curves)
    assert valid_count == n_curves, f"Expected all {n_curves} to satisfy Mazur torsion classification, got {valid_count}"


def test_fused_faltings_height_bound_correctness():
    """Validates the fused Blackwell SM 12.0 kernel for Faltings' height and Mordell finiteness."""
    so_path = "csrc/libfused_blackwell_faltings_height_bound.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_faltings_height_benchmark.argtypes = [ctypes.c_int]
    lib.run_faltings_height_benchmark.restype = ctypes.c_int

    n_curves = 1024
    finite_count = lib.run_faltings_height_benchmark(n_curves)
    assert finite_count == n_curves, f"Expected all {n_curves} curves of genus >= 2 to have finite rational locus, got {finite_count}"


def test_fused_abelian_surface_modularity_correctness():
    """Validates the fused Blackwell SM 12.0 kernel for abelian surface modularity and paramodular Siegel eigenspaces."""
    so_path = "csrc/libfused_blackwell_abelian_surface_modularity.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_abelian_surface_benchmark.argtypes = [ctypes.c_int]
    lib.run_abelian_surface_benchmark.restype = ctypes.c_int

    n_surfaces = 1024
    matched_count = lib.run_abelian_surface_benchmark(n_surfaces)
    assert matched_count == n_surfaces, f"Expected all {n_surfaces} surfaces to match paramodular Deligne-Weil bounds, got {matched_count}"


def test_fused_sato_tate_equidistribution_correctness():
    """Validates the fused Blackwell SM 12.0 kernel for Sato-Tate equidistribution and Frobenius angles."""
    so_path = "csrc/libfused_blackwell_sato_tate_equidistribution.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_sato_tate_benchmark.argtypes = [ctypes.c_int]
    lib.run_sato_tate_benchmark.restype = ctypes.c_int

    n_samples = 1024
    valid_count = lib.run_sato_tate_benchmark(n_samples)
    assert valid_count == n_samples, f"Expected all {n_samples} samples to be Sato-Tate admissible, got {valid_count}"


def test_fused_fontaine_mazur_rep_correctness():
    """Validates the fused Blackwell SM 12.0 kernel for Fontaine-Mazur p-adic Galois representations and Hodge-Tate weights."""
    so_path = "csrc/libfused_blackwell_fontaine_mazur_rep.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_fontaine_mazur_benchmark.argtypes = [ctypes.c_int]
    lib.run_fontaine_mazur_benchmark.restype = ctypes.c_int

    n_samples = 1024
    valid_count = lib.run_fontaine_mazur_benchmark(n_samples)
    assert valid_count == n_samples, f"Expected all {n_samples} samples to be geometrically admissible, got {valid_count}"


def test_fused_bloch_kato_tamagawa_correctness():
    """Validates the fused Blackwell SM 12.0 kernel for Bloch-Kato Tamagawa numbers and motivic Selmer groups."""
    so_path = "csrc/libfused_blackwell_bloch_kato_tamagawa.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_bloch_kato_benchmark.argtypes = [ctypes.c_int]
    lib.run_bloch_kato_benchmark.restype = ctypes.c_int

    n_samples = 1024
    valid_count = lib.run_bloch_kato_benchmark(n_samples)
    assert valid_count == n_samples, f"Expected all {n_samples} samples to be Tamagawa admissible, got {valid_count}"


def test_fused_beilinson_regulator_correctness():
    """Validates the fused Blackwell SM 12.0 kernel for the Beilinson conjectures and Deligne regulator volumes."""
    so_path = "csrc/libfused_blackwell_beilinson_regulator.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_beilinson_regulator_benchmark.argtypes = [ctypes.c_int]
    lib.run_beilinson_regulator_benchmark.restype = ctypes.c_int

    n_samples = 1024
    valid_count = lib.run_beilinson_regulator_benchmark(n_samples)
    assert valid_count == n_samples, f"Expected all {n_samples} samples to have non-zero regulator determinants, got {valid_count}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_fused_bsd_analytic_rank_correctness():
    so_path = "csrc/libfused_blackwell_bsd_analytic_rank.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_bsd_analytic_rank_benchmark.argtypes = [ctypes.c_int]
    lib.run_bsd_analytic_rank_benchmark.restype = ctypes.c_int

    n_samples = 1024
    valid_count = lib.run_bsd_analytic_rank_benchmark(n_samples)
    assert valid_count == n_samples, f"Expected all {n_samples} samples to be BSD consistent, got {valid_count}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_fused_hodge_algebraic_cycles_correctness():
    so_path = "csrc/libfused_blackwell_hodge_algebraic_cycles.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_hodge_algebraic_cycles_benchmark.argtypes = [ctypes.c_int]
    lib.run_hodge_algebraic_cycles_benchmark.restype = ctypes.c_int

    n_samples = 1024
    valid_count = lib.run_hodge_algebraic_cycles_benchmark(n_samples)
    assert valid_count == n_samples, f"Expected all {n_samples} samples to be Hodge admissible, got {valid_count}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_fused_tate_etale_cycles_correctness():
    so_path = "csrc/libfused_blackwell_tate_etale_cycles.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_tate_etale_cycles_benchmark.argtypes = [ctypes.c_int]
    lib.run_tate_etale_cycles_benchmark.restype = ctypes.c_int

    n_samples = 1024
    valid_count = lib.run_tate_etale_cycles_benchmark(n_samples)
    assert valid_count == n_samples, f"Expected all {n_samples} samples to satisfy Tate conjecture invariants, got {valid_count}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_fused_standard_conjectures_correctness():
    so_path = "csrc/libfused_blackwell_standard_conjectures_cycles.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_standard_conjectures_benchmark.argtypes = [ctypes.c_int]
    lib.run_standard_conjectures_benchmark.restype = ctypes.c_int

    n_samples = 1024
    valid_count = lib.run_standard_conjectures_benchmark(n_samples)
    assert valid_count == n_samples, f"Expected all {n_samples} samples to satisfy Standard Conjectures invariants, got {valid_count}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_fused_weil_ii_mixed_weights_correctness():
    so_path = "csrc/libfused_blackwell_weil_ii_mixed_weights.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_weil_ii_benchmark.argtypes = [ctypes.c_int]
    lib.run_weil_ii_benchmark.restype = ctypes.c_int

    n_samples = 1024
    valid_count = lib.run_weil_ii_benchmark(n_samples)
    assert valid_count == n_samples, f"Expected all {n_samples} samples to satisfy Weil II weight bounds, got {valid_count}"

@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
def test_fused_voevodsky_motives_correctness():
    so_path = "csrc/libfused_blackwell_voevodsky_motivic_cohomology.so"
    assert os.path.exists(so_path), f"Missing shared object: {so_path}"

    lib = ctypes.CDLL(so_path)
    lib.run_voevodsky_motives_benchmark.argtypes = [ctypes.c_int]
    lib.run_voevodsky_motives_benchmark.restype = ctypes.c_int

    n_samples = 1024
    valid_count = lib.run_voevodsky_motives_benchmark(n_samples)
    assert valid_count == n_samples, f"Expected all {n_samples} samples to satisfy Voevodsky motivic cohomology invariants, got {valid_count}"




































