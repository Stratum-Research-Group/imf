"""
Triton GPU Kernel: Fused Poincaré Dense MoE Combiner (RTX 5060 Ti)

Implements top-k token recombination in the Poincaré ball using gyrovector addition:
  Given top-k expert outputs X_1, ..., X_k in B^D and routing weights w_1, ..., w_k with sum(w) = 1:
  1. Computes tangent representations v_i = log_0^c(X_i).
  2. Evaluates tangent convex combination:
     v_comb = sum_{i=1}^k w_i * v_i
  3. Retracts combination back to Poincare ball B^D:
     Y = exp_0^c(v_comb) = tanh(sqrt(c) * ||v_comb||) / (sqrt(c) * ||v_comb||) * v_comb

Fuses logarithmic mapping, weighted combination, and exponential retraction in a single register-level pass.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_dense_moe_combiner_kernel(
    Expert_Outs_ptr, # [M, K, D] (fp16)
    Weights_ptr,     # [M, K] (fp32)
    Out_ptr,         # [M, D] (fp16)
    M: tl.constexpr,
    K: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
):
    pid = tl.program_id(0) # Program per token
    if pid >= M:
        return

    offs_d = tl.arange(0, D)
    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))

    v_comb = tl.zeros([D], dtype=tl.float32)

    # Accumulate tangent vectors: sum_i w_i * log_0(x_i)
    for k in range(K):
        w_k = tl.load(Weights_ptr + pid * K + k)
        x_k = tl.load(Expert_Outs_ptr + (pid * K + k) * D + offs_d).to(tl.float32)

        # Compute log_0^c(x_k):
        # norm = sqrt(sum(x_k^2))
        # log_0(x_k) = (1 / sqrt(c)) * artanh(sqrt(c) * norm) / norm * x_k
        sq_norm = tl.sum(x_k * x_k)
        norm = tl.sqrt(sq_norm + 1e-12)
        xi = tl.minimum(sqrt_c * norm, 0.99999)
        artanh_xi = 0.5 * tl.log((1.0 + xi) / (1.0 - xi))
        scale_log = artanh_xi / (sqrt_c * norm)

        v_k = x_k * scale_log
        v_comb += w_k * v_k

    # Retract v_comb via exp_0^c
    sq_norm_comb = tl.sum(v_comb * v_comb)
    norm_comb = tl.sqrt(sq_norm_comb + 1e-12)
    u = sqrt_c * norm_comb
    u_clamped = tl.minimum(u, 15.0)
    exp_2u = tl.exp(2.0 * u_clamped)
    tanh_u = (exp_2u - 1.0) / (exp_2u + 1.0)
    scale_exp = tanh_u / (sqrt_c * norm_comb)

    y_out = v_comb * scale_exp
    tl.store(Out_ptr + pid * D + offs_d, y_out.to(tl.float16))


def poincare_dense_moe_combiner_pytorch(Expert_Outs, Weights, c=1.0):
    """Reference PyTorch implementation."""
    M, K, D = Expert_Outs.shape
    sqrt_c = math.sqrt(c)

    # 1. Log_0 map for all expert outputs
    norm = torch.norm(Expert_Outs.float(), p=2, dim=-1, keepdim=True).clamp(min=1e-8)
    xi = (sqrt_c * norm).clamp(max=0.99999)
    artanh_xi = torch.atanh(xi)
    scale_log = artanh_xi / (sqrt_c * norm)
    v_k = Expert_Outs.float() * scale_log

    # 2. Weighted tangent sum
    v_comb = torch.sum(Weights.unsqueeze(-1) * v_k, dim=1)

    # 3. Exp_0 retraction
    norm_comb = torch.norm(v_comb, p=2, dim=-1, keepdim=True).clamp(min=1e-8)
    scale_exp = torch.tanh(sqrt_c * norm_comb) / (sqrt_c * norm_comb)
    return (v_comb * scale_exp).half()


def poincare_dense_moe_combiner_triton(Expert_Outs, Weights, c=1.0):
    M, K, D = Expert_Outs.shape
    out = torch.empty((M, D), device=Expert_Outs.device, dtype=torch.float16)

    grid = (M,)
    _poincare_dense_moe_combiner_kernel[grid](
        Expert_Outs, Weights, out,
        M=M, K=K, D=D, c=c,
    )
    return out


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré Dense MoE Combiner on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    M = 2048         # Tokens
    K = 4            # Top-4 experts
    D = 64           # Hidden dimension
    c = 1.0

    Expert_Outs = (torch.randn((M, K, D), device=device, dtype=torch.float32) * 0.05).half()
    Weights = torch.softmax(torch.randn((M, K), device=device, dtype=torch.float32), dim=-1)

    # Correctness check
    out_pt = poincare_dense_moe_combiner_pytorch(Expert_Outs, Weights, c)
    out_triton = poincare_dense_moe_combiner_triton(Expert_Outs, Weights, c)

    max_err = (out_pt.float() - out_triton.float()).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-2, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-2 fp16 error)!")

    # Warmup
    for _ in range(50):
        poincare_dense_moe_combiner_pytorch(Expert_Outs, Weights, c)
        poincare_dense_moe_combiner_triton(Expert_Outs, Weights, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 500
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_dense_moe_combiner_pytorch(Expert_Outs, Weights, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_dense_moe_combiner_triton(Expert_Outs, Weights, c)
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
