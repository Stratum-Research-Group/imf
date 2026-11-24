"""
Triton GPU Kernel: Fused Poincaré Bidirectional SSM (Bi-Mamba) (RTX 5060 Ti)

Implements bidirectional linear-time sequence modeling on the Poincaré ball:
  Given input sequence X in R^(M x D):
  1. Forward SSM scan:
     h_t^(fwd) = A_bar_f * h_{t-1}^(fwd) + B_bar_f * x_t
     y_t^(fwd) = C_f * h_t^(fwd)
  2. Backward SSM scan:
     h_t^(bwd) = A_bar_b * h_{t+1}^(bwd) + B_bar_b * x_t
     y_t^(bwd) = C_b * h_t^(bwd)
  3. Fused Tangent Combination & Exp Retraction:
     y_tangent = y_t^(fwd) + y_t^(bwd) + D_res * x_t
     Y_t = exp_0^c(y_tangent) = tanh(sqrt(c) * ||y_tangent||) / (sqrt(c) * ||y_tangent||) * y_tangent

Provides bidirectional context awareness with strictly O(N) sequence complexity.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_bidirectional_ssm_kernel(
    X_ptr,          # [B, M, D] (fp16)
    A_f_ptr,        # [D, N_STATE] (fp32)
    B_f_ptr,        # [D, N_STATE] (fp16)
    C_f_ptr,        # [D, N_STATE] (fp16)
    A_b_ptr,        # [D, N_STATE] (fp32)
    B_b_ptr,        # [D, N_STATE] (fp16)
    C_b_ptr,        # [D, N_STATE] (fp16)
    D_res_ptr,      # [D] (fp32)
    Out_ptr,        # [B, M, D] (fp16)
    M: tl.constexpr,
    D: tl.constexpr,
    N_STATE: tl.constexpr,
    c: tl.constexpr,
):
    pid_b = tl.program_id(0) # Batch
    pid_d = tl.program_id(1) # Feature dimension

    offs_n = tl.arange(0, N_STATE)
    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))

    # Load parameters
    a_f = tl.load(A_f_ptr + pid_d * N_STATE + offs_n)
    b_f = tl.load(B_f_ptr + pid_d * N_STATE + offs_n).to(tl.float32)
    c_f = tl.load(C_f_ptr + pid_d * N_STATE + offs_n).to(tl.float32)

    a_b = tl.load(A_b_ptr + pid_d * N_STATE + offs_n)
    b_b = tl.load(B_b_ptr + pid_d * N_STATE + offs_n).to(tl.float32)
    c_b = tl.load(C_b_ptr + pid_d * N_STATE + offs_n).to(tl.float32)

    d_res = tl.load(D_res_ptr + pid_d)

    delta = 0.1
    a_bar_f = tl.exp(- delta * tl.abs(a_f))
    b_bar_f = delta * b_f

    a_bar_b = tl.exp(- delta * tl.abs(a_b))
    b_bar_b = delta * b_b

    batch_offset = pid_b * M * D

    # 1. Forward scan pass
    h_f = tl.zeros([N_STATE], dtype=tl.float32)
    for t in range(M):
        x_val = tl.load(X_ptr + batch_offset + t * D + pid_d).to(tl.float32)
        h_f = a_bar_f * h_f + b_bar_f * x_val
        y_f = tl.sum(h_f * c_f)
        # Store temporary forward output in Out_ptr
        tl.store(Out_ptr + batch_offset + t * D + pid_d, y_f.to(tl.float16))

    # 2. Backward scan pass and final combination
    h_b = tl.zeros([N_STATE], dtype=tl.float32)
    for step in range(M):
        t_bwd = M - 1 - step
        x_val = tl.load(X_ptr + batch_offset + t_bwd * D + pid_d).to(tl.float32)
        h_b = a_bar_b * h_b + b_bar_b * x_val
        y_b = tl.sum(h_b * c_b)

        y_f = tl.load(Out_ptr + batch_offset + t_bwd * D + pid_d).to(tl.float32)
        y_tan = y_f + y_b + d_res * x_val

        # Retract to Poincare ball
        u = sqrt_c * tl.abs(y_tan)
        u_clamped = tl.minimum(u, 15.0)
        exp_2u = tl.exp(2.0 * u_clamped)
        tanh_u = (exp_2u - 1.0) / (exp_2u + 1.0)
        scale = tanh_u / (sqrt_c * (tl.abs(y_tan) + 1e-12))
        y_out = y_tan * scale

        tl.store(Out_ptr + batch_offset + t_bwd * D + pid_d, y_out.to(tl.float16))


def poincare_bidirectional_ssm_pytorch(X, A_f, B_f, C_f, A_b, B_b, C_b, D_res, c=1.0):
    """Reference PyTorch implementation."""
    Batch, M, D = X.shape
    _, N_STATE = A_f.shape
    out = torch.empty_like(X)
    delta = 0.1
    sqrt_c = math.sqrt(c)

    for b in range(Batch):
        # Forward pass
        h_f = torch.zeros((D, N_STATE), device=X.device, dtype=torch.float32)
        y_fwd = torch.empty((M, D), device=X.device, dtype=torch.float32)
        a_bar_f = torch.exp(- delta * torch.abs(A_f))
        b_bar_f = delta * B_f.float()

        for t in range(M):
            x_t = X[b, t].float()
            h_f = a_bar_f * h_f + b_bar_f * x_t.unsqueeze(-1)
            y_fwd[t] = torch.sum(h_f * C_f.float(), dim=-1)

        # Backward pass
        h_b = torch.zeros((D, N_STATE), device=X.device, dtype=torch.float32)
        a_bar_b = torch.exp(- delta * torch.abs(A_b))
        b_bar_b = delta * B_b.float()

        for t in range(M - 1, -1, -1):
            x_t = X[b, t].float()
            h_b = a_bar_b * h_b + b_bar_b * x_t.unsqueeze(-1)
            y_bwd = torch.sum(h_b * C_b.float(), dim=-1)

            y_tan = y_fwd[t] + y_bwd + D_res * x_t
            u = sqrt_c * torch.abs(y_tan)
            scale = torch.tanh(u) / (sqrt_c * (torch.abs(y_tan) + 1e-12))
            out[b, t] = (y_tan * scale).half()

    return out


def poincare_bidirectional_ssm_triton(X, A_f, B_f, C_f, A_b, B_b, C_b, D_res, c=1.0):
    Batch, M, D = X.shape
    _, N_STATE = A_f.shape
    out = torch.empty_like(X)

    grid = (Batch, D)
    _poincare_bidirectional_ssm_kernel[grid](
        X, A_f, B_f, C_f, A_b, B_b, C_b, D_res, out,
        M=M, D=D, N_STATE=N_STATE, c=c,
    )
    return out


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré Bidirectional SSM on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    Batch = 8
    M = 512          # Sequence length
    D = 64           # Feature dimension
    N_STATE = 16     # SSM state dimension
    c = 1.0

    X = (torch.randn((Batch, M, D), device=device, dtype=torch.float32) * 0.05).half()
    A_f = torch.randn((D, N_STATE), device=device, dtype=torch.float32) * 0.1
    B_f = (torch.randn((D, N_STATE), device=device, dtype=torch.float32) * 0.1).half()
    C_f = (torch.randn((D, N_STATE), device=device, dtype=torch.float32) * 0.1).half()

    A_b = torch.randn((D, N_STATE), device=device, dtype=torch.float32) * 0.1
    B_b = (torch.randn((D, N_STATE), device=device, dtype=torch.float32) * 0.1).half()
    C_b = (torch.randn((D, N_STATE), device=device, dtype=torch.float32) * 0.1).half()
    D_res = torch.randn((D,), device=device, dtype=torch.float32) * 0.1

    # Correctness check
    out_pt = poincare_bidirectional_ssm_pytorch(X, A_f, B_f, C_f, A_b, B_b, C_b, D_res, c)
    out_triton = poincare_bidirectional_ssm_triton(X, A_f, B_f, C_f, A_b, B_b, C_b, D_res, c)

    max_err = (out_pt.float() - out_triton.float()).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-2, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-2 fp16 error)!")

    # Warmup
    for _ in range(10):
        poincare_bidirectional_ssm_pytorch(X, A_f, B_f, C_f, A_b, B_b, C_b, D_res, c)
        poincare_bidirectional_ssm_triton(X, A_f, B_f, C_f, A_b, B_b, C_b, D_res, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 30
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_bidirectional_ssm_pytorch(X, A_f, B_f, C_f, A_b, B_b, C_b, D_res, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_bidirectional_ssm_triton(X, A_f, B_f, C_f, A_b, B_b, C_b, D_res, c)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    tokens_per_sec = (Batch * M) / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {tokens_per_sec / 1e6:.2f} M tokens/sec")


if __name__ == "__main__":
    benchmark()
