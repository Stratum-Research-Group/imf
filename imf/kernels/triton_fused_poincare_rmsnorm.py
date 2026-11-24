r"""
IMF Triton Fused Poincaré Hyperbolic RMSNorm Kernel
===================================================
Hardware-accelerated Root-Mean-Square Normalization (RMSNorm) and boundary-confinement
projection directly on the Poincaré ball \mathbb{B}_c^D.

Given token embeddings x \in \mathbb{B}^D (with ||x|| < 1):
1. Riemannian Logarithmic Map to origin tangent space T_0 \mathbb{B}^D:
   v = \log_0(x) = \operatorname{artanh}(||x||) \frac{x}{||x||}
2. Tangent-Space Root-Mean-Square Normalization:
   \operatorname{RMS}(v) = \sqrt{\frac{1}{D} \sum_{i=1}^D v_i^2 + \epsilon}
   \tilde{v}_i = \frac{v_i}{\operatorname{RMS}(v)} \cdot \gamma_i
3. Geodesic Exponential Retraction back to Poincaré Ball:
   \tilde{x} = \exp_0(\tilde{v}) = \tanh(||\tilde{v}||) \frac{\tilde{v}}{||\tilde{v}||}

This kernel computes the entire pipeline in-register in a single fused pass,
preventing token drift toward the horizon boundary and eliminating HBM round-trips.
"""

import time
import torch
import triton
import triton.language as tl


@torch.no_grad()
def poincare_rmsnorm_torch(
    x: torch.Tensor,        # [B, D]
    gamma: torch.Tensor,    # [D]
    eps: float = 1e-5,
) -> torch.Tensor:
    """
    Reference PyTorch implementation.
    """
    B, D = x.shape
    norm_x = torch.norm(x, dim=-1, keepdim=True).clamp(min=1e-7, max=1.0 - 1e-5)
    
    # 1. Log map to tangent space: v = artanh(||x||) * x / ||x||
    v = torch.atanh(norm_x) * (x / norm_x)
    
    # 2. RMSNorm in tangent space: v_norm = v / rms(v) * gamma
    rms = torch.sqrt(torch.mean(v ** 2, dim=-1, keepdim=True) + eps)
    v_norm = (v / rms) * gamma.unsqueeze(0)
    
    # 3. Exp map back to ball: x_out = tanh(||v_norm||) * v_norm / ||v_norm||
    norm_v = torch.norm(v_norm, dim=-1, keepdim=True).clamp(min=1e-7)
    x_out = torch.tanh(norm_v) * (v_norm / norm_v)
    
    return x_out


@triton.jit
def _poincare_rmsnorm_fused_kernel(
    X_ptr,          # [B, D]
    Gamma_ptr,      # [D]
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

    # 1. Load x and compute norm_x
    x_ptrs = X_ptr + pid * D + offs_d
    x = tl.load(x_ptrs, mask=mask_d, other=0.0)
    
    x_sq = tl.sum(tl.where(mask_d, x * x, 0.0))
    norm_x = tl.sqrt(x_sq)
    # Clamp norm_x to [1e-7, 1.0 - 1e-5]
    norm_x_clamped = tl.maximum(norm_x, 1e-7)
    norm_x_clamped = tl.minimum(norm_x_clamped, 1.0 - 1e-5)

    # atanh(u) = 0.5 * log((1 + u) / (1 - u))
    artanh_norm = 0.5 * tl.log((1.0 + norm_x_clamped) / (1.0 - norm_x_clamped))
    scale_log = artanh_norm / norm_x_clamped
    v = x * scale_log

    # 2. RMSNorm in tangent space
    v_sq = tl.sum(tl.where(mask_d, v * v, 0.0))
    rms = tl.sqrt(v_sq / D + eps)

    gamma = tl.load(Gamma_ptr + offs_d, mask=mask_d, other=1.0)
    v_scaled = (v / rms) * gamma

    # 3. Exp map back to Poincaré manifold
    v_scaled_sq = tl.sum(tl.where(mask_d, v_scaled * v_scaled, 0.0))
    norm_v_scaled = tl.sqrt(v_scaled_sq)
    norm_v_clamped = tl.maximum(norm_v_scaled, 1e-7)

    # tanh(u) = (exp(2u) - 1) / (exp(2u) + 1)
    exp_2u = tl.exp(2.0 * norm_v_clamped)
    tanh_norm_v = (exp_2u - 1.0) / (exp_2u + 1.0)
    scale_exp = tanh_norm_v / norm_v_clamped

    x_out = v_scaled * scale_exp

    out_ptrs = Out_ptr + pid * D + offs_d
    tl.store(out_ptrs, x_out, mask=mask_d)


def triton_fused_poincare_rmsnorm(
    x: torch.Tensor,        # [B, D]
    gamma: torch.Tensor,    # [D]
    eps: float = 1e-5,
) -> torch.Tensor:
    """
    High-performance Triton fused Poincaré RMSNorm kernel.
    """
    B, D = x.shape
    assert x.is_cuda and gamma.is_cuda, "Tensors must be on CUDA"
    assert gamma.shape[0] == D, "Gamma must have size D"

    x = x.contiguous()
    gamma = gamma.contiguous()
    out = torch.empty_like(x)

    BLOCK_D = 1
    while BLOCK_D < D:
        BLOCK_D *= 2

    _poincare_rmsnorm_fused_kernel[(B,)](
        x,
        gamma,
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
    print("IMF Triton Fused Poincaré Hyperbolic RMSNorm Benchmark")
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print("=" * 80)

    torch.manual_seed(42)
    device = "cuda"

    B = 16384
    D = 128

    # Initialize inside Poincaré ball: ||x|| < 0.95
    x = torch.randn((B, D), device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * torch.rand((B, 1), device=device) * 0.90
    gamma = torch.ones((D,), device=device, dtype=torch.float32) + torch.randn((D,), device=device) * 0.1

    # 1. Numerical Correctness
    print(f"1. Validating Numerical Equivalence against PyTorch Reference (B={B}, D={D})...")
    out_ref = poincare_rmsnorm_torch(x, gamma)
    out_tri = triton_fused_poincare_rmsnorm(x, gamma)

    max_err = torch.max(torch.abs(out_ref - out_tri)).item()
    print(f"   Max Abs Error: {max_err:.2e}")
    assert max_err < 1e-4, f"Numerical divergence in RMSNorm: {max_err}"
    print("   ✓ 100.0% Numerical Parity Confirmed.")

    # 2. Hardware Benchmarking
    print("\n2. Executing Workstation Hardware Benchmark (RTX 5060 Ti)...")
    warmup = 10
    iters = 50

    for _ in range(warmup):
        _ = poincare_rmsnorm_torch(x, gamma)
        _ = triton_fused_poincare_rmsnorm(x, gamma)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_rmsnorm_torch(x, gamma)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_fused_poincare_rmsnorm(x, gamma)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    tp_torch = B / t_torch
    tp_triton = B / t_triton
    speedup = t_torch / t_triton

    print(f"   PyTorch Baseline Latency: {t_torch*1e6:8.2f} us | Throughput: {tp_torch/1e6:6.2f} M tokens/s")
    print(f"   Triton Fused Latency:     {t_triton*1e6:8.2f} us | Throughput: {tp_triton/1e6:6.2f} M tokens/s")
    print(f"   Hardware Speedup:         {speedup:8.2f}x")
    print("=" * 80)
