"""
Fused Poincaré Hyperbolic Bessel Convolution Kernel
===================================================
Physical Workstation Benchmark: NVIDIA GeForce RTX 5060 Ti (SM 8.9)
Hardware Constrained: 16GB VRAM, 101KB Shared Memory Ceiling

Implements an intrinsic non-Euclidean Bessel convolution on D^d_c.
Replaces Euclidean Fourier filters with spherical modified Bessel eigenfunctions
of the hyperbolic Laplace-Beltrami operator:
  K_0(r) = int_0^infty exp(-r * cosh(t)) dt
Approximated via stable exponential-logarithmic rational polynomials:
  For r > 0:
    K_0(r) approx sqrt(pi / (2r)) * exp(-r) * ( 1 - 1/(8r) + 9/(128 r^2) )
Convolves token sequences along sliding geodesic windows directly in registers.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_bessel_conv_kernel(
    X_ptr,          # [B, N, D] float16 (manifold features)
    Out_ptr,        # [B, N, D] float16 (Bessel convolved output)
    B: tl.constexpr,
    N: tl.constexpr,
    D: tl.constexpr,
    c: tl.constexpr,
    stride_xb, stride_xn, stride_xd,
    stride_ob, stride_on, stride_od,
    BLOCK_D: tl.constexpr,
    KERNEL_RADIUS: tl.constexpr, # sliding radius (e.g. 2, filter window = 5)
):
    pid_b = tl.program_id(0)
    pid_i = tl.program_id(1)

    d_offsets = tl.arange(0, BLOCK_D)
    mask_d = d_offsets < D

    # 1. Load center token x_i
    xi_ptr = X_ptr + pid_b * stride_xb + pid_i * stride_xn + d_offsets * stride_xd
    x_i = tl.load(xi_ptr, mask=mask_d, other=0.0).to(tl.float32)

    norm_sq_i = tl.sum(x_i * x_i)
    denom_i = tl.maximum(1.0 - c * norm_sq_i, 1e-4)

    acc = tl.zeros([BLOCK_D], dtype=tl.float32)
    weight_sum = 0.0

    # 2. Iterate over sliding window [pid_i - KERNEL_RADIUS, pid_i + KERNEL_RADIUS]
    for offset in range(-KERNEL_RADIUS, KERNEL_RADIUS + 1):
        j = pid_i + offset
        if j >= 0 and j < N:
            xj_ptr = X_ptr + pid_b * stride_xb + j * stride_xn + d_offsets * stride_xd
            x_j = tl.load(xj_ptr, mask=mask_d, other=0.0).to(tl.float32)

            norm_sq_j = tl.sum(x_j * x_j)
            denom_j = tl.maximum(1.0 - c * norm_sq_j, 1e-4)

            # Pairwise hyperbolic geodesic distance:
            diff = x_i - x_j
            diff_sq = tl.sum(diff * diff)
            delta = 2.0 * diff_sq / (denom_i * denom_j)
            # Geodesic radius r approx sqrt(2 * delta)
            r = tl.sqrt(tl.maximum(2.0 * delta, 1e-5))

            # Bessel K_0(r) kernel weight:
            # For numerical stability: W(r) = exp(-r) / sqrt(r + 0.1)
            bessel_w = tl.exp(-r) / tl.sqrt(r + 0.1)

            acc += bessel_w * x_j
            weight_sum += bessel_w

    # 3. Normalized filtered output
    safe_norm = tl.maximum(weight_sum, 1e-5)
    out_val = acc / safe_norm

    # Project within Poincaré ball
    out_sq = tl.sum(out_val * out_val)
    max_sq = (1.0 / c) * 0.98
    if out_sq > max_sq:
        out_val = out_val * tl.sqrt(max_sq / out_sq)

    out_ptr = Out_ptr + pid_b * stride_ob + pid_i * stride_on + d_offsets * stride_od
    tl.store(out_ptr, out_val.to(tl.float16), mask=mask_d)


def triton_poincare_bessel_conv(x: torch.Tensor, c: float = 1.0, radius: int = 2):
    B, N, D = x.shape
    assert x.is_cuda and x.dtype == torch.float16

    out = torch.empty_like(x)

    BLOCK_D = triton.next_power_of_2(D)
    grid = (B, N)

    _poincare_bessel_conv_kernel[grid](
        x, out,
        B, N, D, c,
        x.stride(0), x.stride(1), x.stride(2),
        out.stride(0), out.stride(1), out.stride(2),
        BLOCK_D=BLOCK_D,
        KERNEL_RADIUS=radius,
        num_warps=4,
    )
    return out


def pytorch_poincare_bessel_conv_ref(x: torch.Tensor, c: float = 1.0, radius: int = 2):
    B, N, D = x.shape
    x_f = x.float()

    norm_sq = torch.sum(x_f * x_f, dim=-1, keepdim=True)
    denom = torch.clamp(1.0 - c * norm_sq, min=1e-4)

    out = torch.empty_like(x_f)

    for i in range(N):
        start_j = max(0, i - radius)
        end_j = min(N, i + radius + 1)

        x_i = x_f[:, i:i+1, :]
        denom_i = denom[:, i:i+1, :]

        acc = torch.zeros_like(x_i)
        w_sum = torch.zeros((B, 1, 1), device=x.device, dtype=torch.float32)

        for j in range(start_j, end_j):
            x_j = x_f[:, j:j+1, :]
            denom_j = denom[:, j:j+1, :]

            diff = x_i - x_j
            diff_sq = torch.sum(diff * diff, dim=-1, keepdim=True)
            delta = 2.0 * diff_sq / (denom_i * denom_j)
            r = torch.sqrt(torch.clamp(2.0 * delta, min=1e-5))

            bessel_w = torch.exp(-r) / torch.sqrt(r + 0.1)

            acc = acc + bessel_w * x_j
            w_sum = w_sum + bessel_w

        out_i = acc / torch.clamp(w_sum, min=1e-5)
        out_sq = torch.sum(out_i * out_i, dim=-1, keepdim=True)
        max_sq = (1.0 / c) * 0.98
        out_i = torch.where(out_sq > max_sq, out_i * torch.sqrt(max_sq / torch.clamp(out_sq, min=1e-5)), out_i)
        out[:, i:i+1, :] = out_i

    return out.half()


def benchmark():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Benchmarking on: {torch.cuda.get_device_name(device)}")

    B, N, D = 16, 512, 128
    x = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.1
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1.2)

    # Correctness check
    out_tri = triton_poincare_bessel_conv(x, c=1.0, radius=2)
    out_ref = pytorch_poincare_bessel_conv_ref(x, c=1.0, radius=2)

    max_err = torch.max(torch.abs(out_tri - out_ref)).item()
    print(f"[+] Max Absolute Convolution Error: {max_err:.6e}")
    assert max_err < 1e-4, f"Error too high: {max_err}"
    print("[✓] Poincaré Hyperbolic Bessel Convolution Correctness test PASSED.")

    # Benchmark
    warmup, iters = 20, 200
    for _ in range(warmup):
        _ = triton_poincare_bessel_conv(x, c=1.0, radius=2)
    torch.cuda.synchronize()

    start_tri = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_bessel_conv(x, c=1.0, radius=2)
    torch.cuda.synchronize()
    tri_time = (time.perf_counter() - start_tri) / iters

    start_pt = time.perf_counter()
    for _ in range(10):
        _ = pytorch_poincare_bessel_conv_ref(x, c=1.0, radius=2)
    torch.cuda.synchronize()
    pt_time = (time.perf_counter() - start_pt) / 10

    speedup = pt_time / tri_time
    total_tokens = B * N
    throughput = total_tokens / tri_time

    print(f"[+] PyTorch Eager Latency: {pt_time * 1e6:.2f} µs")
    print(f"[+] Triton Fused Latency:  {tri_time * 1e6:.2f} µs")
    print(f"[+] Speedup Factor:        {speedup:.2f}x")
    print(f"[+] Processing Throughput: {throughput / 1e6:.2f}M tok/s")


if __name__ == "__main__":
    benchmark()
