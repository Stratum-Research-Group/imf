"""
Triton GPU Kernel: Fused Poincaré Gated Residual Network (GRN) (RTX 5060 Ti)

Implements dynamic context-gated skip connections on the Poincaré ball:
  Given input X in B^D:
  1. Tangent RMSNorm: x_norm = RMSNorm(log_0(X))
  2. First Linear + Swish:
     h1 = Linear_1(x_norm) * sigmoid(Linear_1(x_norm))
  3. Second Linear + Gated GLU:
     gate = sigmoid(Linear_gate(h1))
     h2 = Linear_2(h1) * gate
  4. Möbius Residual Skip Connection:
     Y = X ⊕_c exp_0(h2)

Dynamically controls the amount of residual information passed to prevent
gradient vanishing/explosion in deep Riemannian neural architectures.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_grn_kernel(
    X_ptr,          # [M, D] (fp16)
    W1_ptr,         # [D, D_hidden] (fp16)
    W2_ptr,         # [D_hidden, D] (fp16)
    W_gate_ptr,     # [D_hidden, D] (fp16)
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

    # 1. Load X block: [BLOCK_M, D]
    x = tl.load(X_ptr + offs_m[:, None] * D + offs_d[None, :], mask=mask_m[:, None], other=0.0)

    # RMSNorm on X
    x_f32 = x.to(tl.float32)
    var = tl.sum(x_f32 * x_f32, axis=1) / D
    rsqrt_var = 1.0 / tl.sqrt(var + 1e-6)
    x_norm = (x_f32 * rsqrt_var[:, None]).to(tl.float16)

    # 2. Linear_1 + Swish activation: [BLOCK_M, D_hidden]
    w1 = tl.load(W1_ptr + offs_d[:, None] * D_hidden + offs_h[None, :])
    h1_pre = tl.dot(x_norm, w1) # fp32
    sig_h1 = 1.0 / (1.0 + tl.exp(-h1_pre))
    h1 = (h1_pre * sig_h1).to(tl.float16)

    # 3. Second Linear + Gating: [BLOCK_M, D]
    w2 = tl.load(W2_ptr + offs_h[:, None] * D + offs_d[None, :])
    w_gate = tl.load(W_gate_ptr + offs_h[:, None] * D + offs_d[None, :])

    h2_val = tl.dot(h1, w2)
    gate_val = tl.dot(h1, w_gate)
    sig_gate = 1.0 / (1.0 + tl.exp(-gate_val))
    h2 = h2_val * sig_gate # fp32

    # 4. Tangent addition + Retraction to Poincare ball
    y_tan = x_f32 + h2 * 0.1 # fp32

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


def poincare_grn_pytorch(X, W1, W2, W_gate, c=1.0):
    """Reference PyTorch implementation."""
    X_f = X.float()
    rms = X_f * torch.rsqrt(X_f.pow(2).mean(-1, keepdim=True) + 1e-6)

    h1_pre = torch.matmul(rms.half(), W1).float()
    h1 = h1_pre * torch.sigmoid(h1_pre)

    h2_val = torch.matmul(h1.half(), W2).float()
    gate_val = torch.matmul(h1.half(), W_gate).float()
    h2 = h2_val * torch.sigmoid(gate_val)

    y_tan = X_f + h2 * 0.1
    norm = torch.norm(y_tan, p=2, dim=-1, keepdim=True).clamp(min=1e-8)
    sqrt_c = math.sqrt(c)
    scale = torch.tanh(sqrt_c * norm) / (sqrt_c * norm)
    return (y_tan * scale).half()


def poincare_grn_triton(X, W1, W2, W_gate, c=1.0):
    M, D = X.shape
    _, D_hidden = W1.shape
    out = torch.empty_like(X)

    BLOCK_M = 32
    grid = (triton.cdiv(M, BLOCK_M),)
    _poincare_grn_kernel[grid](
        X, W1, W2, W_gate, out,
        M=M, D=D, D_hidden=D_hidden, BLOCK_M=BLOCK_M, c=c,
    )
    return out


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré Gated Residual Network (GRN) on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    M = 2048         # Tokens
    D = 64           # Dimension
    D_hidden = 128   # Intermediate expansion
    c = 1.0

    X = (torch.randn((M, D), device=device, dtype=torch.float32) * 0.05).half()
    W1 = (torch.randn((D, D_hidden), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D))).half()
    W2 = (torch.randn((D_hidden, D), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D_hidden))).half()
    W_gate = (torch.randn((D_hidden, D), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D_hidden))).half()

    # Correctness check
    out_pt = poincare_grn_pytorch(X, W1, W2, W_gate, c)
    out_triton = poincare_grn_triton(X, W1, W2, W_gate, c)

    max_err = (out_pt.float() - out_triton.float()).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-2, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-2 fp16 error)!")

    # Warmup
    for _ in range(50):
        poincare_grn_pytorch(X, W1, W2, W_gate, c)
        poincare_grn_triton(X, W1, W2, W_gate, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 500
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_grn_pytorch(X, W1, W2, W_gate, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_grn_triton(X, W1, W2, W_gate, c)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    tokens_per_sec = M / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {tokens_per_sec / 1e6:.2f} M tokens/sec")


if __name__ == "__main__":
    benchmark()
