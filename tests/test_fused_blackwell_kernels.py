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










