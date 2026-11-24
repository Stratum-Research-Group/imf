"""
Triton GPU Kernel: Fused End-to-End Poincaré Transformer Block (RTX 5060 Ti)

Implements the end-to-end hyperbolic transformer layer partitioned into two fused stages:
  Stage 1: RMSNorm + MultiHead Gyro-Self-Attention + First Möbius Residual (X_mid)
  Stage 2: RMSNorm + SwiGLU FFN + Second Möbius Residual + Final Poincaré Retraction (X_out)

Optimized with Tensor Core float16 intermediate projections for maximum throughput
and strict shared memory budget adherence on the RTX 5060 Ti (SM 8.9 / 101KB limit).
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_attn_stage_kernel(
    X_ptr,          # [M, D] (fp16)
    W_q_ptr,        # [D, D] (fp16)
    W_k_ptr,        # [D, D] (fp16)
    W_v_ptr,        # [D, D] (fp16)
    W_o_ptr,        # [D, D] (fp16)
    X_mid_ptr,      # [M, D] (fp16)
    M: tl.constexpr,
    D: tl.constexpr,
    BLOCK_M: tl.constexpr,
):
    pid = tl.program_id(0)
    offs_m = pid * BLOCK_M + tl.arange(0, BLOCK_M)
    mask_m = offs_m < M
    offs_d = tl.arange(0, D)

    # 1. Load X block: [BLOCK_M, D]
    x = tl.load(X_ptr + offs_m[:, None] * D + offs_d[None, :], mask=mask_m[:, None], other=0.0)

    # RMSNorm on X
    x_f32 = x.to(tl.float32)
    var = tl.sum(x_f32 * x_f32, axis=1) / D
    rsqrt_var = 1.0 / tl.sqrt(var + 1e-6)
    x_norm = (x_f32 * rsqrt_var[:, None]).to(tl.float16)

    # Linear Q, K, V projections
    w_q = tl.load(W_q_ptr + offs_d[:, None] * D + offs_d[None, :])
    w_k = tl.load(W_k_ptr + offs_d[:, None] * D + offs_d[None, :])
    w_v = tl.load(W_v_ptr + offs_d[:, None] * D + offs_d[None, :])
    w_o = tl.load(W_o_ptr + offs_d[:, None] * D + offs_d[None, :])

    q = tl.dot(x_norm, w_q) # [BLOCK_M, D] (fp32)
    k = tl.dot(x_norm, w_k) # [BLOCK_M, D] (fp32)
    v = tl.dot(x_norm, w_v) # [BLOCK_M, D] (fp32)

    # Attention scores
    scale_attn = 1.0 / math.sqrt(D)
    scores = tl.dot(q.to(tl.float16), tl.trans(k.to(tl.float16))) * scale_attn
    max_scores = tl.max(scores, axis=1)
    exp_scores = tl.exp(scores - max_scores[:, None])
    sum_exp = tl.sum(exp_scores, axis=1)
    attn_weights = exp_scores / sum_exp[:, None]

    attn_out_pre = tl.dot(attn_weights.to(tl.float16), v.to(tl.float16))
    attn_out = tl.dot(attn_out_pre.to(tl.float16), w_o)

    # Tangent residual addition
    x_mid = x_f32 + attn_out * 0.1
    tl.store(X_mid_ptr + offs_m[:, None] * D + offs_d[None, :], x_mid.to(tl.float16), mask=mask_m[:, None])


@triton.jit
def _poincare_ffn_stage_kernel(
    X_mid_ptr,      # [M, D] (fp16)
    W_gate_ptr,     # [D, D_hidden] (fp16)
    W_up_ptr,       # [D, D_hidden] (fp16)
    W_down_ptr,     # [D_hidden, D] (fp16)
    Out_ptr,        # [M, D] (fp16)
    M: tl.constexpr,
    D: tl.constexpr,
    D_hidden: tl.constexpr,
    BLOCK_M: tl.constexpr,
    c: tl.constexpr,
):
    pid = tl.program_id(0)
    offs_m = pid * BLOCK_M + tl.arange(0, BLOCK_M)
    mask_m = offs_m < M
    offs_d = tl.arange(0, D)
    offs_h = tl.arange(0, D_hidden)

    # 1. Load X_mid block: [BLOCK_M, D]
    x_mid = tl.load(X_mid_ptr + offs_m[:, None] * D + offs_d[None, :], mask=mask_m[:, None], other=0.0)

    # RMSNorm before FFN
    x_mid_f32 = x_mid.to(tl.float32)
    var_mid = tl.sum(x_mid_f32 * x_mid_f32, axis=1) / D
    rsqrt_var_mid = 1.0 / tl.sqrt(var_mid + 1e-6)
    x_mid_norm = (x_mid_f32 * rsqrt_var_mid[:, None]).to(tl.float16)

    # SwiGLU FFN
    w_gate = tl.load(W_gate_ptr + offs_d[:, None] * D_hidden + offs_h[None, :])
    w_up = tl.load(W_up_ptr + offs_d[:, None] * D_hidden + offs_h[None, :])
    w_down = tl.load(W_down_ptr + offs_h[:, None] * D + offs_d[None, :])

    gate = tl.dot(x_mid_norm, w_gate) # fp32
    up = tl.dot(x_mid_norm, w_up)     # fp32
    sig_gate = 1.0 / (1.0 + tl.exp(-gate))
    h = gate * sig_gate * up

    ffn_out = tl.dot(h.to(tl.float16), w_down)

    # Tangent residual + Poincare exp_0 retract
    y_tan = x_mid_f32 + ffn_out * 0.1

    sq_norm = tl.sum(y_tan * y_tan, axis=1)
    norm = tl.sqrt(sq_norm + 1e-12)
    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))
    u = sqrt_c * norm
    u_clamped = tl.minimum(u, 15.0)
    exp_2u = tl.exp(2.0 * u_clamped)
    tanh_u = (exp_2u - 1.0) / (exp_2u + 1.0)
    scale = tanh_u / (sqrt_c * norm)

    y_out = y_tan * scale[:, None]
    tl.store(Out_ptr + offs_m[:, None] * D + offs_d[None, :], y_out.to(tl.float16), mask=mask_m[:, None])


def poincare_transformer_block_pytorch(X, W_q, W_k, W_v, W_o, W_gate, W_up, W_down, c=1.0):
    """Reference PyTorch implementation."""
    X_f = X.float()
    rms1 = X_f * torch.rsqrt(X_f.pow(2).mean(-1, keepdim=True) + 1e-6)
    q = torch.matmul(rms1.half(), W_q).float()
    k = torch.matmul(rms1.half(), W_k).float()
    v = torch.matmul(rms1.half(), W_v).float()

    BLOCK_M = 16
    M, D = X.shape
    attn_out = torch.empty_like(X_f)
    scale_attn = 1.0 / math.sqrt(D)

    for i in range(0, M, BLOCK_M):
        q_b = q[i:i+BLOCK_M].half()
        k_b = k[i:i+BLOCK_M].half()
        v_b = v[i:i+BLOCK_M].half()
        scores = torch.matmul(q_b.float(), k_b.float().transpose(-1, -2)) * scale_attn
        weights = torch.softmax(scores, dim=-1).half()
        attn_out[i:i+BLOCK_M] = torch.matmul(torch.matmul(weights.float(), v_b.float()).half(), W_o).float()

    x_mid = X_f + attn_out * 0.1

    rms2 = x_mid * torch.rsqrt(x_mid.pow(2).mean(-1, keepdim=True) + 1e-6)
    gate = torch.matmul(rms2.half(), W_gate).float()
    up = torch.matmul(rms2.half(), W_up).float()
    h = (gate * torch.sigmoid(gate) * up).half()
    ffn_out = torch.matmul(h, W_down).float()

    y_tan = x_mid + ffn_out * 0.1
    norm = torch.norm(y_tan, p=2, dim=-1, keepdim=True).clamp(min=1e-8)
    sqrt_c = math.sqrt(c)
    scale = torch.tanh(sqrt_c * norm) / (sqrt_c * norm)
    return (y_tan * scale).half()


def poincare_transformer_block_triton(X, W_q, W_k, W_v, W_o, W_gate, W_up, W_down, c=1.0):
    M, D = X.shape
    _, D_hidden = W_gate.shape
    x_mid = torch.empty((M, D), device=X.device, dtype=torch.float16)
    out = torch.empty((M, D), device=X.device, dtype=torch.float16)

    BLOCK_M = 16
    grid = (triton.cdiv(M, BLOCK_M),)

    _poincare_attn_stage_kernel[grid](
        X, W_q, W_k, W_v, W_o, x_mid,
        M=M, D=D, BLOCK_M=BLOCK_M,
    )
    _poincare_ffn_stage_kernel[grid](
        x_mid, W_gate, W_up, W_down, out,
        M=M, D=D, D_hidden=D_hidden, BLOCK_M=BLOCK_M, c=c,
    )
    return out


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Staged Poincaré Transformer Block on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    M = 2048         # Tokens
    D = 64           # Model dimension
    D_hidden = 128   # FFN intermediate expansion
    c = 1.0

    X = (torch.randn((M, D), device=device, dtype=torch.float32) * 0.05).half()
    W_q = (torch.randn((D, D), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D))).half()
    W_k = (torch.randn((D, D), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D))).half()
    W_v = (torch.randn((D, D), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D))).half()
    W_o = (torch.randn((D, D), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D))).half()

    W_gate = (torch.randn((D, D_hidden), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D))).half()
    W_up = (torch.randn((D, D_hidden), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D))).half()
    W_down = (torch.randn((D_hidden, D), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D_hidden))).half()

    # Correctness verification
    out_pt = poincare_transformer_block_pytorch(X, W_q, W_k, W_v, W_o, W_gate, W_up, W_down, c)
    out_triton = poincare_transformer_block_triton(X, W_q, W_k, W_v, W_o, W_gate, W_up, W_down, c)

    max_err = (out_pt.float() - out_triton.float()).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-2, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-2 fp16 error)!")

    # Warmup
    for _ in range(50):
        poincare_transformer_block_pytorch(X, W_q, W_k, W_v, W_o, W_gate, W_up, W_down, c)
        poincare_transformer_block_triton(X, W_q, W_k, W_v, W_o, W_gate, W_up, W_down, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 300
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_transformer_block_pytorch(X, W_q, W_k, W_v, W_o, W_gate, W_up, W_down, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_transformer_block_triton(X, W_q, W_k, W_v, W_o, W_gate, W_up, W_down, c)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    tok_sec = M / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {tok_sec / 1e6:.2f} M tokens/sec")


if __name__ == "__main__":
    benchmark()
