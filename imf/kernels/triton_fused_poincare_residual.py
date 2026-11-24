r"""
IMF Triton Fused Poincaré Gyrovector Residual & Gated Skip Connection Kernel
=============================================================================
Hardware-accelerated Möbius gyrovector addition and conformal gated skip connection
directly on the Poincaré ball \mathbb{B}_c^D.

Given:
  Layer input x \in \mathbb{B}^D (with ||x|| < 1)
  Layer update \Delta x \in \mathbb{B}^D (with ||\Delta x|| < 1)
  Learnable gating factor \alpha \in \mathbb{R}

The Möbius addition x \oplus_c y is given by:
  x \oplus y = \frac{(1 + 2\langle x, y\rangle + \|y\|^2) x + (1 - \|x\|^2) y}{1 + 2\langle x, y\rangle + \|x\|^2 \|y\|^2}

The gated residual update performs scalar Möbius multiplication:
  \Delta \tilde{x} = \tanh(\alpha \operatorname{artanh}(\|\Delta x\|)) \frac{\Delta x}{\|\Delta x\|}
followed by the geodesic addition:
  x_{\text{out}} = x \oplus \Delta \tilde{x}

This kernel executes the Möbius scaling, inner products, denominator evaluation,
and gyrovector addition in a single fused pass directly in registers on the GPU.
"""

import time
import torch
import triton
import triton.language as tl


@torch.no_grad()
def poincare_residual_torch(
    x: torch.Tensor,        # [B, D]
    dx: torch.Tensor,       # [B, D]
    alpha: float = 1.0,
    eps: float = 1e-5,
) -> torch.Tensor:
    """
    Reference PyTorch implementation.
    """
    B, D = x.shape

    # 1. Möbius scalar multiplication of dx by alpha
    norm_dx = torch.norm(dx, dim=-1, keepdim=True).clamp(min=1e-7, max=1.0 - eps)
    v_dx = torch.atanh(norm_dx) * alpha
    scaled_norm = torch.tanh(v_dx)
    dx_scaled = scaled_norm * (dx / norm_dx)

    # 2. Möbius gyrovector addition: x \oplus dx_scaled
    x_sq = torch.sum(x ** 2, dim=-1, keepdim=True)
    y_sq = torch.sum(dx_scaled ** 2, dim=-1, keepdim=True)
    xy = torch.sum(x * dx_scaled, dim=-1, keepdim=True)

    denom = 1.0 + 2.0 * xy + x_sq * y_sq
    numer = (1.0 + 2.0 * xy + y_sq) * x + (1.0 - x_sq) * dx_scaled
    out = numer / denom.clamp(min=eps)

    # Conformal boundary clamp
    norm_out = torch.norm(out, dim=-1, keepdim=True)
    out = torch.where(norm_out >= 1.0 - eps, out / norm_out * (1.0 - eps), out)
    return out


@triton.jit
def _poincare_residual_fused_kernel(
    X_ptr,          # [B, D]
    Dx_ptr,         # [B, D]
    Out_ptr,        # [B, D]
    alpha,          # float
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

    # Load x and dx
    x = tl.load(X_ptr + pid * D + offs_d, mask=mask_d, other=0.0)
    dx = tl.load(Dx_ptr + pid * D + offs_d, mask=mask_d, other=0.0)

    # 1. Möbius scalar multiplication of dx by alpha in-register
    dx_sq = tl.sum(tl.where(mask_d, dx * dx, 0.0))
    norm_dx = tl.sqrt(dx_sq)
    norm_dx_clamped = tl.maximum(norm_dx, 1e-7)
    norm_dx_clamped = tl.minimum(norm_dx_clamped, 1.0 - eps)

    # atanh(u) = 0.5 * log((1 + u) / (1 - u))
    artanh_dx = 0.5 * tl.log((1.0 + norm_dx_clamped) / (1.0 - norm_dx_clamped))
    scaled_v = artanh_dx * alpha

    # tanh(u) = (exp(2u) - 1) / (exp(2u) + 1)
    exp_2u = tl.exp(2.0 * scaled_v)
    tanh_scaled = (exp_2u - 1.0) / (exp_2u + 1.0)
    scale_factor = tanh_scaled / norm_dx_clamped
    dx_scaled = dx * scale_factor

    # 2. Möbius gyrovector addition: x \oplus dx_scaled
    x_sq = tl.sum(tl.where(mask_d, x * x, 0.0))
    y_sq = tl.sum(tl.where(mask_d, dx_scaled * dx_scaled, 0.0))
    xy = tl.sum(tl.where(mask_d, x * dx_scaled, 0.0))

    denom = 1.0 + 2.0 * xy + x_sq * y_sq
    denom_clamped = tl.maximum(denom, eps)

    term1 = (1.0 + 2.0 * xy + y_sq) * x
    term2 = (1.0 - x_sq) * dx_scaled
    out = (term1 + term2) / denom_clamped

    # Safety horizon confinement check
    out_sq = tl.sum(tl.where(mask_d, out * out, 0.0))
    norm_out = tl.sqrt(out_sq)
    out_final = tl.where(norm_out >= (1.0 - eps), out / norm_out * (1.0 - eps), out)

    tl.store(Out_ptr + pid * D + offs_d, out_final, mask=mask_d)


def triton_fused_poincare_residual(
    x: torch.Tensor,        # [B, D]
    dx: torch.Tensor,       # [B, D]
    alpha: float = 1.0,
    eps: float = 1e-5,
) -> torch.Tensor:
    """
    High-performance Triton fused Poincaré gyrovector residual kernel.
    """
    B, D = x.shape
    assert x.is_cuda and dx.is_cuda, "Tensors must be on CUDA"

    x = x.contiguous()
    dx = dx.contiguous()
    out = torch.empty_like(x)

    BLOCK_D = 1
    while BLOCK_D < D:
        BLOCK_D *= 2

    _poincare_residual_fused_kernel[(B,)](
        x,
        dx,
        out,
        alpha=float(alpha),
        eps=float(eps),
        B=B,
        D=D,
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )

    return out


if __name__ == "__main__":
    print("=" * 80)
    print("IMF Triton Fused Poincaré Gyrovector Residual Benchmark")
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print("=" * 80)

    torch.manual_seed(42)
    device = "cuda"

    B = 16384
    D = 128
    alpha = 0.8

    # Inside ball: ||x|| < 0.90, ||dx|| < 0.80
    x = torch.randn((B, D), device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * torch.rand((B, 1), device=device) * 0.85

    dx = torch.randn((B, D), device=device, dtype=torch.float32)
    dx = dx / (torch.norm(dx, dim=-1, keepdim=True) + 1e-5) * torch.rand((B, 1), device=device) * 0.70

    # 1. Numerical Correctness
    print(f"1. Validating Numerical Equivalence against PyTorch Reference (B={B}, D={D})...")
    out_ref = poincare_residual_torch(x, dx, alpha=alpha)
    out_tri = triton_fused_poincare_residual(x, dx, alpha=alpha)

    max_err = torch.max(torch.abs(out_ref - out_tri)).item()
    print(f"   Max Abs Error: {max_err:.2e}")
    assert max_err < 1e-4, f"Numerical divergence in gyrovector residual: {max_err}"
    print("   ✓ 100.0% Numerical Parity Confirmed.")

    # 2. Hardware Benchmarking
    print("\n2. Executing Workstation Hardware Benchmark (RTX 5060 Ti)...")
    warmup = 10
    iters = 50

    for _ in range(warmup):
        _ = poincare_residual_torch(x, dx, alpha=alpha)
        _ = triton_fused_poincare_residual(x, dx, alpha=alpha)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = poincare_residual_torch(x, dx, alpha=alpha)
    torch.cuda.synchronize()
    t_torch = (time.perf_counter() - t0) / iters

    t0 = time.perf_counter()
    for _ in range(iters):
        _ = triton_fused_poincare_residual(x, dx, alpha=alpha)
    torch.cuda.synchronize()
    t_triton = (time.perf_counter() - t0) / iters

    tp_torch = B / t_torch
    tp_triton = B / t_triton
    speedup = t_torch / t_triton

    print(f"   PyTorch Baseline Latency: {t_torch*1e6:8.2f} us | Throughput: {tp_torch/1e6:6.2f} M tokens/s")
    print(f"   Triton Fused Latency:     {t_triton*1e6:8.2f} us | Throughput: {tp_triton/1e6:6.2f} M tokens/s")
    print(f"   Hardware Speedup:         {speedup:8.2f}x")
    print("=" * 80)
