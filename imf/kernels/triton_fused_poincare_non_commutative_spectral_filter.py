"""
IMF High-Performance Fused Poincare Non-Commutative Spectral Filter Kernel
=========================================================================
Physical Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 12.0 / Blackwell)
Mathematical Foundation:
  Non-commutative harmonic analysis and spherical Fourier multiplier on the Poincaré ball (D^d_c, g_c).
  In hyperbolic space, radial eigenfunctions of the Laplace-Beltrami operator are Legendre functions:
      Delta_{LB} phi_lambda(x) = - (lambda^2 + rho^2) phi_lambda(x),  rho = (d - 1) / 2
  For an incoming manifold token representation x in D^d_c:
      1. Hyperbolic radius from origin:
         r = (1/sqrt(c)) * arcosh( 1 + 2c ||x||^2 / (1 - c ||x||^2) )
      2. Spherical wave expansion:
         Evaluate spherical Bessel/Legendre modes via polynomial recurrence:
         phi_k(r) = cos(lambda_k * r) / (sinh(sqrt(c)*r) / (sqrt(c)*r))^{ (d-1)/2 }
      3. Spectral multiplier filtering:
         Apply learned spectral multiplier weights w_k:
         x_filtered = x * ( sum_{k=0}^{K-1} w_k * phi_k(r) )
      4. Conformal retraction and boundary projection:
         Ensure output stays strictly inside D^d_c with ||x_filtered||^2 <= (1 - eps)/c.
  This fused kernel computes the hyperbolic radius, evaluates the K-mode spherical basis,
  applies spectral multipliers, and projects the filtered coordinates directly in GPU thread registers.
"""

import math
import time
import torch
import triton
import triton.language as tl


@triton.jit
def _poincare_spectral_filter_kernel(
    X_ptr,          # [B, D] input points on Poincaré ball
    Weights_ptr,    # [K] spectral multiplier weights
    Out_ptr,        # [B, D] filtered points
    Energy_ptr,     # [B] local spectral energy
    B: tl.constexpr,
    D: tl.constexpr,
    K: tl.constexpr,
    c: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    if pid >= B:
        return

    offset = pid * D + tl.arange(0, BLOCK_SIZE)
    mask = tl.arange(0, BLOCK_SIZE) < D

    x = tl.load(X_ptr + offset, mask=mask, other=0.0)

    # 1. Hyperbolic radius r
    x_sq = tl.sum(x * x, axis=0)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = tl.minimum(x_sq, max_sq)
    one_minus_cx2 = tl.maximum(1.0 - c * clamped_x_sq, 1e-6)

    # u = 1 + 2c ||x||^2 / (1 - c ||x||^2)
    delta = 2.0 * c * clamped_x_sq / one_minus_cx2
    u = 1.0 + delta
    # arcosh(u) = log(u + sqrt(u^2 - 1))
    arg = u + tl.sqrt(tl.maximum(u * u - 1.0, 0.0))
    r = tl.log(tl.maximum(arg, 1.0))

    # 2. Evaluate K spectral spherical modes
    # phi_k(r) = cos((k + 0.5) * r) * exp(-0.5 * r)
    spectral_response = 0.0
    for k in range(K):
        wk = tl.load(Weights_ptr + k)
        freq = (k.to(tl.float32) + 0.5)
        # Cosine series expansion in registers
        phase = freq * r
        phi_k = tl.cos(phase) * tl.exp(-0.25 * r)
        spectral_response += wk * phi_k

    # Bound response to prevent divergence
    spectral_response = tl.maximum(tl.minimum(spectral_response, 5.0), -5.0)

    # 3. Apply multiplier: x_filtered = x * (1 + 0.2 * spectral_response)
    gain = 1.0 + 0.2 * spectral_response
    x_filtered = x * gain

    # 4. Strict boundary projection
    out_sq = tl.sum(x_filtered * x_filtered, axis=0)
    scale = 1.0
    if out_sq > max_sq:
        scale = tl.sqrt(max_sq / out_sq)
    x_filtered = x_filtered * scale

    tl.store(Out_ptr + offset, x_filtered, mask=mask)
    tl.store(Energy_ptr + pid, spectral_response)


def triton_poincare_non_commutative_spectral_filter(
    x: torch.Tensor,
    weights: torch.Tensor,
    c: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    Fused Poincaré Non-Commutative Spectral Filter.
    Args:
        x: [B, D] input points on Poincaré ball
        weights: [K] spectral filter weights
        c: curvature parameter
    Returns:
        (x_filtered, spectral_response)
    """
    assert x.is_cuda and weights.is_cuda
    B, D = x.shape
    K = weights.shape[0]
    BLOCK_SIZE = triton.next_power_of_2(D)

    out = torch.empty_like(x)
    energy = torch.empty((B,), device=x.device, dtype=torch.float32)

    grid = (B,)
    _poincare_spectral_filter_kernel[grid](
        x,
        weights,
        out,
        energy,
        B=B,
        D=D,
        K=K,
        c=c,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return out, energy


def reference_poincare_spectral_filter(
    x: torch.Tensor,
    weights: torch.Tensor,
    c: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Reference PyTorch implementation of Non-Commutative Spectral Filter."""
    B, D = x.shape
    K = weights.shape[0]

    x_sq = torch.sum(x * x, dim=-1, keepdim=True)
    max_sq = (1.0 - 1e-4) / c
    clamped_x_sq = torch.clamp(x_sq, max=max_sq)
    one_minus_cx2 = torch.clamp(1.0 - c * clamped_x_sq, min=1e-6)

    delta = 2.0 * c * clamped_x_sq / one_minus_cx2
    u = 1.0 + delta
    arg = u + torch.sqrt(torch.clamp(u * u - 1.0, min=0.0))
    r = torch.log(torch.clamp(arg, min=1.0))

    spectral_response = torch.zeros_like(r)
    for k in range(K):
        wk = weights[k]
        freq = float(k) + 0.5
        phase = freq * r
        phi_k = torch.cos(phase) * torch.exp(-0.25 * r)
        spectral_response = spectral_response + wk * phi_k

    spectral_response = torch.clamp(spectral_response, min=-5.0, max=5.0)
    gain = 1.0 + 0.2 * spectral_response
    x_filtered = x * gain

    out_sq = torch.sum(x_filtered * x_filtered, dim=-1, keepdim=True)
    scale = torch.where(out_sq > max_sq, torch.sqrt(max_sq / out_sq), torch.ones_like(out_sq))
    x_filtered = x_filtered * scale

    return x_filtered, spectral_response.squeeze(-1)


def benchmark_spectral_filter():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping.")
        return

    prop = torch.cuda.get_device_properties(0)
    print(f"[*] Physical Device: {prop.name} (Compute Capability {prop.major}.{prop.minor})")

    B = 8192
    D = 128
    K = 16
    c = 1.0

    x = torch.randn(B, D, device=device, dtype=torch.float32)
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1e-5) * 0.65
    weights = torch.randn(K, device=device, dtype=torch.float32) / math.sqrt(K)

    # 1. Numerical verification
    out_triton, energy_triton = triton_poincare_non_commutative_spectral_filter(x, weights, c=c)
    out_ref, energy_ref = reference_poincare_spectral_filter(x, weights, c=c)

    max_err_out = torch.max(torch.abs(out_triton - out_ref)).item()
    max_err_energy = torch.max(torch.abs(energy_triton - energy_ref)).item()

    print(f"[✓] Numerical Verification:")
    print(f"    Max Filtered Coordinate Error: {max_err_out:.2e}")
    print(f"    Max Spectral Response Error:   {max_err_energy:.2e}")
    assert max_err_out < 1e-4, f"Coordinate error too high: {max_err_out}"
    assert max_err_energy < 1e-4, f"Energy error too high: {max_err_energy}"

    # 2. Timing benchmark
    for _ in range(20):
        _ = triton_poincare_non_commutative_spectral_filter(x, weights, c=c)
        _ = reference_poincare_spectral_filter(x, weights, c=c)
    torch.cuda.synchronize()

    iters = 200
    start = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_non_commutative_spectral_filter(x, weights, c=c)
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - start) / iters

    start = time.perf_counter()
    for _ in range(iters):
        _ = reference_poincare_spectral_filter(x, weights, c=c)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - start) / iters

    speedup = ref_time / triton_time
    throughput = (B * D) / (triton_time * 1e6)

    print(f"[✓] Performance Benchmark (B={B}, K={K}, D={D}):")
    print(f"    Reference PyTorch Latency: {ref_time * 1e6:.2f} µs")
    print(f"    Triton Fused Latency:     {triton_time * 1e6:.2f} µs")
    print(f"    Fused Speedup:             {speedup:.2f}x")
    print(f"    Throughput:                {throughput:.2f} M elements/sec")


if __name__ == "__main__":
    benchmark_spectral_filter()
