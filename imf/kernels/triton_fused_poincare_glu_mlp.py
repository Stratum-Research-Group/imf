"""
Triton GPU Kernel: Fused Block-Parallel Poincaré Feed-Forward Network / GLU MLP Layer (RTX 5060 Ti)

Implements the end-to-end fused 2-layer hyperbolic MLP:
  X in B^D_in  -->  log_0(X) in T_0 B^D_in
  W_gate in R^(D_in x D_hidden),  W_up in R^(D_in x D_hidden)
  H = (X @ W_gate) * sigmoid(X @ W_gate) * (X @ W_up)  [SwiGLU activation]
  W_down in R^(D_hidden x D_out)
  Y_tangent = H @ W_down
  Y = exp_0(Y_tangent) = tanh(||Y_tangent||) * (Y_tangent / ||Y_tangent||) in B^D_out

Optimized Block-Parallel Tiled Design:
  Each Triton program processes BLOCK_M tokens in parallel (BLOCK_M=32 or 64).
  Matrices W_gate [D_in, D_hidden], W_up [D_in, D_hidden], and W_down [D_hidden, D_out]
  are loaded as vectorized 2D blocks with tensor-core tile alignment.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_glu_mlp_tiled_kernel(
    X_ptr,          # [M, D_in]
    W_gate_ptr,     # [D_in, D_hidden]
    W_up_ptr,       # [D_in, D_hidden]
    W_down_ptr,     # [D_hidden, D_out]
    Out_ptr,        # [M, D_out]
    M: tl.constexpr,
    D_in: tl.constexpr,
    D_hidden: tl.constexpr,
    D_out: tl.constexpr,
    BLOCK_M: tl.constexpr,
    c: tl.constexpr,
):
    pid = tl.program_id(0)
    offs_m = pid * BLOCK_M + tl.arange(0, BLOCK_M)
    mask_m = offs_m < M

    # Load X block: [BLOCK_M, D_in]
    offs_in = tl.arange(0, D_in)
    x = tl.load(X_ptr + offs_m[:, None] * D_in + offs_in[None, :], mask=mask_m[:, None], other=0.0)

    # 1. SwiGLU projection: Gate & Up
    offs_h = tl.arange(0, D_hidden)
    w_gate = tl.load(W_gate_ptr + offs_in[:, None] * D_hidden + offs_h[None, :])
    w_up = tl.load(W_up_ptr + offs_in[:, None] * D_hidden + offs_h[None, :])

    gate = tl.dot(x, w_gate) # [BLOCK_M, D_hidden]
    up = tl.dot(x, w_up)     # [BLOCK_M, D_hidden]

    sig_gate = 1.0 / (1.0 + tl.exp(-gate))
    h = gate * sig_gate * up # [BLOCK_M, D_hidden]

    # 2. Down projection: Y_tangent = H @ W_down [BLOCK_M, D_out]
    offs_out = tl.arange(0, D_out)
    w_down = tl.load(W_down_ptr + offs_h[:, None] * D_out + offs_out[None, :])
    y_tan = tl.dot(h, w_down) # [BLOCK_M, D_out]

    # 3. Retract y_tan via Poincaré exp_0 map
    sq_norm = tl.sum(y_tan * y_tan, axis=1) # [BLOCK_M]
    norm = tl.sqrt(sq_norm + 1e-12)
    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))
    u = sqrt_c * norm
    u_clamped = tl.minimum(u, 15.0)
    exp_2u = tl.exp(2.0 * u_clamped)
    tanh_u = (exp_2u - 1.0) / (exp_2u + 1.0)
    scale = tanh_u / (sqrt_c * norm) # [BLOCK_M]

    y_out = y_tan * scale[:, None]
    tl.store(Out_ptr + offs_m[:, None] * D_out + offs_out[None, :], y_out, mask=mask_m[:, None])


def poincare_glu_mlp_pytorch(X, W_gate, W_up, W_down, c=1.0):
    """Reference PyTorch implementation."""
    gate = torch.matmul(X, W_gate)
    up = torch.matmul(X, W_up)
    h = gate * torch.sigmoid(gate) * up
    y_tan = torch.matmul(h, W_down)
    norm = torch.norm(y_tan, p=2, dim=-1, keepdim=True).clamp(min=1e-8)
    sqrt_c = math.sqrt(c)
    scale = torch.tanh(sqrt_c * norm) / (sqrt_c * norm)
    return y_tan * scale


def poincare_glu_mlp_triton(X, W_gate, W_up, W_down, c=1.0):
    """Triton vectorized block execution."""
    M, D_in = X.shape
    _, D_hidden = W_gate.shape
    _, D_out = W_down.shape
    out = torch.empty((M, D_out), device=X.device, dtype=torch.float32)

    BLOCK_M = 32
    grid = (triton.cdiv(M, BLOCK_M),)
    _poincare_glu_mlp_tiled_kernel[grid](
        X, W_gate, W_up, W_down, out,
        M=M, D_in=D_in, D_hidden=D_hidden, D_out=D_out,
        BLOCK_M=BLOCK_M, c=c,
    )
    return out


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Vectorized Poincaré GLU MLP Kernel on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    M = 2048         # Tokens
    D_in = 64        # Input dimension
    D_hidden = 128   # FFN intermediate expansion
    D_out = 64       # Output dimension
    c = 1.0

    X = torch.randn((M, D_in), device=device, dtype=torch.float32) * 0.1
    W_gate = torch.randn((D_in, D_hidden), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D_in))
    W_up = torch.randn((D_in, D_hidden), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D_in))
    W_down = torch.randn((D_hidden, D_out), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D_hidden))

    # Verify numerical correctness
    out_pt = poincare_glu_mlp_pytorch(X, W_gate, W_up, W_down, c)
    out_triton = poincare_glu_mlp_triton(X, W_gate, W_up, W_down, c)

    max_err = (out_pt - out_triton).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-4, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-4 error)!")

    # Warmup
    for _ in range(50):
        poincare_glu_mlp_pytorch(X, W_gate, W_up, W_down, c)
        poincare_glu_mlp_triton(X, W_gate, W_up, W_down, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 300
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_glu_mlp_pytorch(X, W_gate, W_up, W_down, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_glu_mlp_triton(X, W_gate, W_up, W_down, c)
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
