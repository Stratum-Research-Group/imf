r"""
IMF Triton Fused Poincaré SwiGLU Gated Tangent Activation Kernel
=================================================================
Hardware-accelerated tangent-space SwiGLU (Swish-Gated Linear Unit) activation
and boundary-confined exponential retraction on the Poincaré ball \mathbb{B}_c^D.

Given hidden representation x \in \mathbb{B}^D (with ||x|| < 1):
1. Riemannian Logarithmic Map to origin tangent space T_0 \mathbb{B}^D:
   v = \log_0(x) = \operatorname{artanh}(||x||) \frac{x}{||x||}
2. SwiGLU Gated Activation in tangent space:
   gate = v \odot \sigma(v) = v / (1 + \exp(-v))
   \tilde{v} = gate \odot (v \odot \gamma + \beta)
3. Geodesic Exponential Retraction back to Poincaré Ball:
   x_{\text{out}} = \exp_0(\tilde{v}) = \tanh(||\tilde{v}||) \frac{\tilde{v}}{||\tilde{v}||}

This kernel fuses the log map, swish gate, linear scaling, and exp map in a single pass
directly in GPU registers, eliminating intermediate tensor allocations.
"""

import time
import torch
import triton
import triton.language as tl


@torch.no_grad()
def poincare_swiglu_torch(
    x: torch.Tensor,        # [B, D]
    gamma: torch.Tensor,    # [D]
    beta: torch.Tensor,     # [D]
    eps: float = 1e-5,
) -> torch.Tensor:
    """
    Reference PyTorch implementation.
    """
    B, D = x.shape
    norm_x = torch.norm(x, dim=-1, keepdim=True).clamp(min=1e-7, max=1.0 - eps)

    # 1. Log map: v = artanh(||x||) * x / ||x||
    v = torch.atanh(norm_x) * (x / norm_x)

    # 2. SwiGLU gate: swish(v) * (v * gamma + beta)
    swish = v * torch.sigmoid(v)
    v_tilde = swish * (v * gamma.unsqueeze(0) + beta.unsqueeze(0))

    # 3. Exp map: x_out = tanh(||v_tilde||) * v_tilde / ||v_tilde||
    norm_v = torch.norm(v_tilde, dim=-1, keepdim=True).clamp(min=1e-7)
    x_out = torch.tanh(norm_v) * (v_tilde / norm_v)

    return x_out


@triton.jit
def _poincare_swiglu_fused_kernel(
    X_ptr,          # [B, D]
    Gamma_ptr,      # [D]
    Beta_ptr,       # [D]
    Out_ptr,        # [B, D]
    eps,            # float
    B: tl.constexpr,
    D: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    offs_d = tl.arange(0, BLOCK_D)
    mask_d = offs_d < D

    # 1. Load x and compute log map
    x_ptrs = X_ptr + pid * D + offs_d
    x = tl.load(x_ptrs, mask=mask_d, other=0.0)

    x_sq = tl.sum(tl.where(mask_d, x * x, 0.0))
    norm_x = tl.sqrt(x_sq)
    norm_x_clamped = tl.maximum(norm_x, 1e-7)
    norm_x_clamped = tl.minimum(norm_x_clamped, 1.0 - eps)

    # artanh(u) = 0.5 * log((1 + u) / (1 - u))
    artanh_norm = 0.5 * tl.log((1.0 + norm_x_clamped) / (1.0 - norm_x_clamped))
    scale_log = artanh_norm / norm_x_clamped
    v = x * scale_log

    # 2. SwiGLU in tangent space: swish(v) = v / (1 + exp(-v))
    sig_v = 1.0 / (1.0 + tl.exp(-v))
    swish_v = v * sig_v

    gamma = tl.load(Gamma_ptr + offs_d, mask=mask_d, other=1.0)
    b_val = tl.load(Beta_ptr + offs_d, mask=mask_d, other=0.0)
    v_tilde = swish_v * (v * gamma + b_val)

    # 3. Exp map back to Poincaré manifold
    v_sq = tl.sum(tl.where(mask_d, v_tilde * v_tilde, 0.0))
    norm_v = tl.sqrt(v_sq)
    norm_v_clamped = tl.maximum(norm_v, 1e-7)

    # tanh(u) = (exp(2u) - 1) / (exp(2u) + 1)
    exp_2u = tl.exp(2.0 * norm_v_clamped)
    tanh_norm = (exp_2u - 1.0) / (exp_2u + 1.0)
    scale_exp = tanh_norm / norm_v_clamped

    x_out = v_tilde * scale_exp

    out_ptrs = Out_ptr + pid * D + offs_d
    tl.store(out_ptrs, x_out, mask=mask_d)


def triton_fused_poincare_swiglu(
    x: torch.Tensor,        # [B, D]
    gamma: torch.Tensor,    # [D]
    beta: torch.Tensor,     # [D]
    eps: float = 1e-5,
) -> torch.Tensor:
    """
    High-performance Triton fused Poincaré SwiGLU kernel.
    """
    B, D = x.shape
    assert x.is_cuda and gamma.is_cuda and beta.is_cuda, "Tensors must be on CUDA"
    assert gamma.shape[0] == D and beta.shape[0] == D, "Parameter dimension mismatch"

    x = x.contiguous()
    gamma = gamma.contiguous()
    beta = beta.contiguous()
    out = torch.empty_like(x)

    BLOCK_D = 1
    while BLOCK_D < D:
        BLOCK_D *= 2

    _poincare_swiglu_fused_kernel[(B,)](
        x,
        gamma,
        beta,
        out,
        eps=float(eps),
        B=B,
        D=D,
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )

    return out


if __name__ == "__main__":
    print("=" * 80)
    print("IMF Triton Fused Poincaré SwiGLU Gated Activation Benchmark")
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print("=" * 80)

    torch.manual_seed(42)
    device = "cuda"

    B = 16384
    D = 128

    # Inside ball: ||x|| < 0.90
    x = torch.randn((B, D), device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * torch.rand((B, 1), device=device) * 0.85
    gamma = torch.randn((D,), device=device, dtype=torch.float32) * 0.1 + 1.0
    beta = torch.randn((D,), device=device, dtype=torch.float32) * 0.05

    # 1. Numerical Correctness
    print(f"1. Validating Numerical Equivalence against PyTorch Reference (B={B}, D={D})...")
    out_ref = poincare_swiglu_torch(x, gamma, beta)
    out_tri = triton_fused_poincare_swiglu(x, gamma, beta)

    max_err = torch.max(torch.abs(out_ref - out_tri)).item()
    print(f"   Max Abs Error: {max_err:.2e}")
    assert max_err < 1e-4, f"Numerical divergence in SwiGLU: {max_err}"
    print("   ✓ 100.0% Numerical Parity Confirmed.")

    # 2. Hardware Benchmarking
    print("\n2. Executing Workstation Hardware Benchmark (RTX 5060 Ti)...")
    warmup = 10
    iters = 50

    for _ in range(warmup):
        _ = poincare_swiglu_torch(x, gamma, beta)
        _ = triton_fused_poincare_swiglu(x, gamma, beta)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_swiglu_torch(x, gamma, beta)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_fused_poincare_swiglu(x, gamma, beta)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    tp_torch = B / t_torch
    tp_triton = B / t_triton
    speedup = t_torch / t_triton

    print(f"   PyTorch Baseline Latency: {t_torch*1e6:8.2f} us | Throughput: {tp_torch/1e6:6.2f} M tokens/s")
    print(f"   Triton Fused Latency:     {t_triton*1e6:8.2f} us | Throughput: {tp_triton/1e6:6.2f} M tokens/s")
    print(f"   Hardware Speedup:         {speedup:8.2f}x")
    print("=" * 80)
