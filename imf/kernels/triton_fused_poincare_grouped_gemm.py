"""
Triton GPU Kernel: Fused Poincaré Grouped GEMM for Mixture of Hyperbolic Experts (MoE) (RTX 5060 Ti)

Implements parallel multi-expert dispatch and linear transformation on the Poincaré ball:
  Given tokens partitioned across E experts, where expert e processes N_e tokens with weight W_e in R^(D_in x D_out):
  1. Identifies expert slice boundaries via offsets buffer.
  2. Executes blocked matrix multiplication for expert e:
     Y_tangent = X_e @ W_e
  3. Fuses origin-tangent retraction exp_0^c directly into output registers:
     Y_e = tanh(sqrt(c) * ||Y_tangent||) / (sqrt(c) * ||Y_tangent||) * Y_tangent

Eliminates kernel launch overhead per expert and eliminates global memory round-trips for retraction.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_grouped_gemm_kernel(
    X_ptr,          # [Total_Tokens, D_in] (fp16)
    Weights_ptr,    # [E, D_in, D_out] (fp16)
    Out_ptr,        # [Total_Tokens, D_out] (fp16)
    Offsets_ptr,    # [E + 1] (int32 token offsets)
    Total_Tokens: tl.constexpr,
    D_in: tl.constexpr,
    D_out: tl.constexpr,
    BLOCK_M: tl.constexpr,
    c: tl.constexpr,
):
    pid = tl.program_id(0) # Program per token block
    expert_id = tl.program_id(1) # Program per expert

    start_idx = tl.load(Offsets_ptr + expert_id)
    end_idx = tl.load(Offsets_ptr + expert_id + 1)
    num_tokens = end_idx - start_idx

    offs_m = pid * BLOCK_M + tl.arange(0, BLOCK_M)
    mask_m = offs_m < num_tokens

    token_indices = start_idx + offs_m

    offs_in = tl.arange(0, D_in)
    offs_out = tl.arange(0, D_out)

    # 1. Load X block for this expert: [BLOCK_M, D_in]
    x = tl.load(X_ptr + token_indices[:, None] * D_in + offs_in[None, :], mask=mask_m[:, None], other=0.0)

    # 2. Load Weight for this expert: [D_in, D_out]
    w_offset = expert_id * D_in * D_out
    w = tl.load(Weights_ptr + w_offset + offs_in[:, None] * D_out + offs_out[None, :])

    # 3. Compute GEMM in fp32
    y_tan = tl.dot(x, w) # [BLOCK_M, D_out]

    # 4. Retract via exp_0^c
    sq_norm = tl.sum(y_tan * y_tan, axis=1)
    norm = tl.sqrt(sq_norm + 1e-12)
    sqrt_c = tl.sqrt(tl.full([], c, dtype=tl.float32))
    u = sqrt_c * norm
    u_clamped = tl.minimum(u, 15.0)
    exp_2u = tl.exp(2.0 * u_clamped)
    tanh_u = (exp_2u - 1.0) / (exp_2u + 1.0)
    scale = tanh_u / (sqrt_c * norm)

    y_out = y_tan * scale[:, None]
    tl.store(Out_ptr + token_indices[:, None] * D_out + offs_out[None, :], y_out.to(tl.float16), mask=mask_m[:, None])


def poincare_grouped_gemm_pytorch(X, Weights, offsets, c=1.0):
    """Reference PyTorch loop per expert."""
    E = len(offsets) - 1
    Total_Tokens, _ = X.shape
    _, _, D_out = Weights.shape
    out = torch.empty((Total_Tokens, D_out), device=X.device, dtype=torch.float16)
    sqrt_c = math.sqrt(c)

    for e in range(E):
        start = offsets[e].item()
        end = offsets[e + 1].item()
        if start < end:
            x_e = X[start:end].float()
            w_e = Weights[e].float()
            y_tan = torch.matmul(x_e, w_e)
            norm = torch.norm(y_tan, p=2, dim=-1, keepdim=True).clamp(min=1e-8)
            scale = torch.tanh(sqrt_c * norm) / (sqrt_c * norm)
            out[start:end] = (y_tan * scale).half()

    return out


def poincare_grouped_gemm_triton(X, Weights, offsets, c=1.0):
    Total_Tokens, D_in = X.shape
    E, _, D_out = Weights.shape
    out = torch.empty((Total_Tokens, D_out), device=X.device, dtype=torch.float16)

    BLOCK_M = 32
    # Find max tokens across experts to size the grid
    tokens_per_expert = (offsets[1:] - offsets[:-1]).max().item()
    grid_m = triton.cdiv(max(tokens_per_expert, 1), BLOCK_M)

    grid = (grid_m, E)
    _poincare_grouped_gemm_kernel[grid](
        X, Weights, out, offsets,
        Total_Tokens=Total_Tokens, D_in=D_in, D_out=D_out,
        BLOCK_M=BLOCK_M, c=c,
    )
    return out


def benchmark():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"[*] Benchmarking Fused Poincaré Grouped GEMM Kernel on {torch.cuda.get_device_name(0)}")

    torch.manual_seed(42)
    E = 8            # 8 Experts
    Total_Tokens = 2048 # Total dispatched tokens
    D_in = 64
    D_out = 64
    c = 1.0

    # Distribute tokens across experts
    counts = torch.multinomial(torch.ones(E), Total_Tokens, replacement=True).bincount(minlength=E)
    offsets = torch.zeros(E + 1, device=device, dtype=torch.int32)
    offsets[1:] = torch.cumsum(counts, dim=0).to(torch.int32)

    X = (torch.randn((Total_Tokens, D_in), device=device, dtype=torch.float32) * 0.05).half()
    Weights = (torch.randn((E, D_in, D_out), device=device, dtype=torch.float32) * (1.0 / math.sqrt(D_in))).half()

    # Correctness check
    out_pt = poincare_grouped_gemm_pytorch(X, Weights, offsets, c)
    out_triton = poincare_grouped_gemm_triton(X, Weights, offsets, c)

    max_err = (out_pt.float() - out_triton.float()).abs().max().item()
    print(f"[*] Max absolute error between PyTorch and Triton: {max_err:.4e}")
    assert max_err < 1e-2, f"Numerical mismatch exceeds tolerance: {max_err}"
    print("[✓] Correctness check passed (< 1e-2 fp16 error)!")

    # Warmup
    for _ in range(50):
        poincare_grouped_gemm_pytorch(X, Weights, offsets, c)
        poincare_grouped_gemm_triton(X, Weights, offsets, c)
    torch.cuda.synchronize()

    # Timing PyTorch
    n_iters = 300
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_grouped_gemm_pytorch(X, Weights, offsets, c)
    torch.cuda.synchronize()
    t_pt = (time.perf_counter() - t0) / n_iters

    # Timing Triton
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = poincare_grouped_gemm_triton(X, Weights, offsets, c)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / n_iters

    tokens_per_sec = Total_Tokens / t_triton
    speedup = t_pt / t_triton

    print(f"[*] PyTorch Latency : {t_pt * 1e6:.2f} µs")
    print(f"[*] Triton Latency  : {t_triton * 1e6:.2f} µs")
    print(f"[*] Speedup         : {speedup:.2f}x")
    print(f"[*] Throughput      : {tokens_per_sec / 1e6:.2f} M tokens/sec")


if __name__ == "__main__":
    benchmark()
