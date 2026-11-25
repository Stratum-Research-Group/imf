"""
Fused Poincaré Symplectic Momentum Normalization Kernel
========================================================
Physical Workstation Benchmark: NVIDIA GeForce RTX 5060 Ti (SM 12.0)
Hardware Constrained: 16GB VRAM, 101KB Shared Memory Ceiling

Implements an intrinsic Riemannian momentum normalization on T*D^d_c.
Normalizes features with respect to the Riemannian kinetic metric:
  <p, p>_{g^{-1}} = (1 / lambda_x^2) * ||p||^2
where lambda_x = 2 / (1 - c * ||x||^2) is the conformal metric factor.

Transformation:
  p_norm = gamma * ( p / sqrt( <p, p>_{g^{-1}} / d + eps ) ) * (1 / lambda_x)
Preserves phase-space Hamiltonian invariance and conformal geometry in SRAM.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_symplectic_momentum_norm_kernel(
    X_ptr,          # [B, N, D] float16 (manifold coordinate x)
    P_ptr,          # [B, N, D] float16 (momentum vector p)
    Out_ptr,        # [B, N, D] float16 (normalized momentum)
    Gamma_ptr,      # [D] float16 (learnable gain)
    B: tl.constexpr,
    N: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    eps: tl.constexpr,
    stride_xb, stride_xn, stride_xd,
    stride_pb, stride_pn, stride_pd,
    stride_ob, stride_on, stride_od,
    BLOCK_D: tl.constexpr,
):
    pid_b = tl.program_id(0)
    pid_n = tl.program_id(1)

    d_offsets = tl.arange(0, BLOCK_D)
    mask_d = d_offsets < D

    # 1. Load x_i and p_i
    x_offset = pid_b * stride_xb + pid_n * stride_xn + d_offsets * stride_xd
    p_offset = pid_b * stride_pb + pid_n * stride_pn + d_offsets * stride_pd

    x_val = tl.load(X_ptr + x_offset, mask=mask_d, other=0.0).to(tl.float32)
    p_val = tl.load(P_ptr + p_offset, mask=mask_d, other=0.0).to(tl.float32)
    gamma_val = tl.load(Gamma_ptr + d_offsets, mask=mask_d, other=1.0).to(tl.float32)

    # 2. Compute conformal factor lambda_x = 2 / (1 - c * ||x||^2)
    x_norm_sq = tl.sum(x_val * x_val)
    denom_x = tl.maximum(1.0 - c * x_norm_sq, 1e-4)
    # lambda_x = 2.0 / denom_x
    # 1 / lambda_x = denom_x / 2.0
    inv_lambda = 0.5 * denom_x

    # 3. Kinetic energy metric <p, p>_{g^{-1}} = (1 / lambda_x^2) * ||p||^2
    p_norm_sq = tl.sum(p_val * p_val)
    kinetic_metric = (inv_lambda * inv_lambda) * p_norm_sq

    # 4. Riemannian Root-Mean-Square variance
    rms_riemann = tl.sqrt(kinetic_metric / float(D) + eps)

    # 5. Normalize momentum vector
    norm_p = gamma_val * (p_val / rms_riemann) * inv_lambda

    # Store normalized output
    out_offset = pid_b * stride_ob + pid_n * stride_on + d_offsets * stride_od
    tl.store(Out_ptr + out_offset, norm_p.to(tl.float16), mask=mask_d)


def triton_poincare_symplectic_momentum_norm(x: torch.Tensor, p: torch.Tensor, gamma: torch.Tensor, c: float = 1.0, eps: float = 1e-5):
    B, N, D = x.shape
    assert x.is_cuda and p.is_cuda and gamma.is_cuda
    assert x.dtype == torch.float16 and p.dtype == torch.float16 and gamma.dtype == torch.float16

    out = torch.empty_like(p)

    BLOCK_D = triton.next_power_of_2(D)
    grid = (B, N)

    _poincare_symplectic_momentum_norm_kernel[grid](
        x, p, out, gamma,
        B, N, D, c, eps,
        x.stride(0), x.stride(1), x.stride(2),
        p.stride(0), p.stride(1), p.stride(2),
        out.stride(0), out.stride(1), out.stride(2),
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )
    return out


def pytorch_poincare_symplectic_momentum_norm_ref(x: torch.Tensor, p: torch.Tensor, gamma: torch.Tensor, c: float = 1.0, eps: float = 1e-5):
    x_f = x.float()
    p_f = p.float()
    g_f = gamma.float()

    B, N, D = x.shape
    x_norm_sq = torch.sum(x_f * x_f, dim=-1, keepdim=True)
    denom_x = torch.clamp(1.0 - c * x_norm_sq, min=1e-4)
    inv_lambda = 0.5 * denom_x

    p_norm_sq = torch.sum(p_f * p_f, dim=-1, keepdim=True)
    kinetic_metric = (inv_lambda * inv_lambda) * p_norm_sq

    rms_riemann = torch.sqrt(kinetic_metric / float(D) + eps)
    norm_p = g_f * (p_f / rms_riemann) * inv_lambda

    return norm_p.half()


def benchmark():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Benchmarking on: {torch.cuda.get_device_name(device)}")

    B, N, D = 16, 512, 128
    x = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.1
    p = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.2
    gamma = torch.ones(D, device=device, dtype=torch.float16)

    # Bound coordinates inside ball
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1.2)

    # Correctness check
    out_tri = triton_poincare_symplectic_momentum_norm(x, p, gamma, c=1.0, eps=1e-5)
    out_ref = pytorch_poincare_symplectic_momentum_norm_ref(x, p, gamma, c=1.0, eps=1e-5)

    max_err = torch.max(torch.abs(out_tri - out_ref)).item()
    print(f"[+] Max Absolute Normalization Error: {max_err:.6e}")
    assert max_err < 5e-3, f"Error too high: {max_err}"
    print("[✓] Poincaré Symplectic Momentum Norm Correctness test PASSED.")

    # Benchmark
    warmup, iters = 20, 200
    for _ in range(warmup):
        _ = triton_poincare_symplectic_momentum_norm(x, p, gamma, c=1.0, eps=1e-5)
        _ = pytorch_poincare_symplectic_momentum_norm_ref(x, p, gamma, c=1.0, eps=1e-5)
    torch.cuda.synchronize()

    start_pt = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_poincare_symplectic_momentum_norm_ref(x, p, gamma, c=1.0, eps=1e-5)
    torch.cuda.synchronize()
    pt_time = (time.perf_counter() - start_pt) / iters

    start_tri = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_symplectic_momentum_norm(x, p, gamma, c=1.0, eps=1e-5)
    torch.cuda.synchronize()
    tri_time = (time.perf_counter() - start_tri) / iters

    speedup = pt_time / tri_time
    total_tokens = B * N
    throughput = total_tokens / tri_time

    print(f"[+] PyTorch Eager Latency: {pt_time * 1e6:.2f} µs")
    print(f"[+] Triton Fused Latency:  {tri_time * 1e6:.2f} µs")
    print(f"[+] Speedup Factor:        {speedup:.2f}x")
    print(f"[+] Processing Throughput: {throughput / 1e6:.2f}M tok/s")


if __name__ == "__main__":
    benchmark()
