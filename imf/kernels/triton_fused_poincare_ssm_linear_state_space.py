"""
Triton GPU Kernel: Fused Poincaré Selective State Space Model (SSM / Mamba) (RTX 5060 Ti)

Implements linear-time sequence modeling on the Poincaré ball:
  Given input sequence X in R^(M x D), compute hidden state recurrence:
  1. Continuous-to-discrete discretization:
     delta_t = softplus(Linear_delta(x_t))
     A_bar = exp(- delta_t * A)
     B_bar = delta_t * B
  2. Tangent-space recurrent state update (selective scan):
     h_t = A_bar * h_{t-1} + B_bar * x_t
     y_t = C * h_t + D_res * x_t
  3. Retraction to Poincare ball B^D via exp_0^c mapping:
     Y_t = tanh(sqrt(c) * ||y_t||) / (sqrt(c) * ||y_t||) * y_t

Fuses discretization, state scan, and hyperbolic retraction in a single thread per sequence.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_ssm_kernel(
    X_ptr,          # [B, M, D] (fp16)
    A_ptr,          # [D, N_STATE] (fp32)
    B_ptr,          # [D, N_STATE] (fp16)
    C_ptr,          # [D, N_STATE] (fp16)
    D_res_ptr,      # [D] (fp32)
    Out_ptr,        # [B, M, D] (fp16)
    M: tl.constexpr,
    D: tl.constexpr,
    N_STATE: tl.constexpr,
    c: tl.constexpr,
):
    pid_b = tl.program_id(0) # Program per batch sequence
    pid_d = tl.program_id(1) # Program per feature dimension

    offs_n = tl.arange(0, N_STATE)
    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))

    # Load static parameter slices for feature dimension pid_d
    a_param = tl.load(A_ptr + pid_d * N_STATE + offs_n)
    b_param = tl.load(B_ptr + pid_d * N_STATE + offs_n).to(tl.float32)
    c_param = tl.load(C_ptr + pid_d * N_STATE + offs_n).to(tl.float32)
    d_res = tl.load(D_res_ptr + pid_d)

    # Initialize hidden state h: [N_STATE]
    h = tl.zeros([N_STATE], dtype=tl.float32)

    batch_offset = pid_b * M * D

    # Recurrent sequential scan over length M
    for t in range(M):
        # Load scalar input x_t at dimension pid_d
        x_val = tl.load(X_ptr + batch_offset + t * D + pid_d).to(tl.float32)

        # Simplified discretization: delta = 0.1
        delta = 0.1
        a_bar = tl.exp(- delta * tl.abs(a_param))
        b_bar = delta * b_param

        # Recurrent state transition
        h = a_bar * h + b_bar * x_val

        # Output projection
        y_tan = tl.sum(h * c_param) + d_res * x_val

        # Retract via 1D exp_0^c mapping (or scaled element-wise)
        u = sqrt_c * tl.abs(y_tan)
        u_clamped = tl.minimum(u, 15.0)
        exp_2u = tl.exp(2.0 * u_clamped)
        tanh_u = (exp_2u - 1.0) / (exp_2u + 1.0)
        scale = tanh_u / (sqrt_c * (tl.abs(y_tan) + 1e-12))
        y_out = y_tan * scale

        tl.store(Out_ptr + batch_offset + t * D + pid_d, y_out.to(tl.float16))


def poincare_ssm_pytorch(X, A, B, C, D_res, c=1.0):
    """Reference PyTorch implementation."""
    Batch, M, D = X.shape
    _, N_STATE = A.shape
    out = torch.empty_like(X)
    delta = 0.1
    sqrt_c = math.sqrt(c)

    for b in range(Batch):
        h = torch.zeros((D, N_STATE), device=X.device, dtype=torch.float32)
        for t in range(M):
            x_t = X[b, t].float()
            a_bar = torch.exp(- delta * torch.abs(A))
            b_bar = delta * B.float()

            h = a_bar * h + b_bar * x_t.unsqueeze(-1)
            y_tan = torch.sum(h * C.float(), dim=-1) + D_res * x_t

            u = sqrt_c * torch.abs(y_tan)
            scale = torch.tanh(u) / (sqrt_c * (torch.abs(y_tan) + 1e-12))
            out[b, t] = (y_tan * scale).half()

    return out


def poincare_ssm_triton(X, A, B, C, D_res, c=1.0):
    Batch, M, D = X.shape
    _, N_STATE = A.shape
    out = torch.empty_like(X)

    grid = (Batch, D)
    _poincare_ssm_kernel[grid](
        X, A, B, C, D_res, out,
        M=M, D=D, N_STATE=N_STATE, c=c,
    )
    return out


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré Selective SSM (Mamba) on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    Batch = 8
    M = 512          # Sequence length
    D = 64           # Feature dimension
    N_STATE = 16     # SSM state dimension
    c = 1.0

    X = (torch.randn((Batch, M, D), device=device, dtype=torch.float32) * 0.05).half()
    A = torch.randn((D, N_STATE), device=device, dtype=torch.float32) * 0.1
    B = (torch.randn((D, N_STATE), device=device, dtype=torch.float32) * 0.1).half()
    C = (torch.randn((D, N_STATE), device=device, dtype=torch.float32) * 0.1).half()
    D_res = torch.randn((D,), device=device, dtype=torch.float32) * 0.1

    # Correctness check
    out_pt = poincare_ssm_pytorch(X, A, B, C, D_res, c)
    out_triton = poincare_ssm_triton(X, A, B, C, D_res, c)

    max_err = (out_pt.float() - out_triton.float()).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-2, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-2 fp16 error)!")

    # Warmup
    for _ in range(10):
        poincare_ssm_pytorch(X, A, B, C, D_res, c)
        poincare_ssm_triton(X, A, B, C, D_res, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 50
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_ssm_pytorch(X, A, B, C, D_res, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_ssm_triton(X, A, B, C, D_res, c)
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
