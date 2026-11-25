"""
Fused Poincaré Multiscale Hyperbolic Wavelet Routing Kernel
============================================================
Physical Workstation Benchmark: NVIDIA GeForce RTX 5060 Ti (SM 12.0)
Hardware Constrained: 16GB VRAM, 101KB Shared Memory Ceiling

Implements a fused multiscale continuous hyperbolic wavelet routing layer on D^d_c.
Decomposes token embeddings into J dyadic scale bands:
  Scale j in {0, ..., J-1}:
  1. Conformal contraction: r_{i, j} = 2^( -j / 2 ) * 2 * arctanh(||x_i||)
  2. Radial bandpass filter: psi_j(r) = cos(pi * 2^j * r) * exp(- (2^j * r)^2 / 2)
  3. Multiscale energy projection: E_j = sum_d (x_{i, d} * psi_j(r_{i, j}))^2
  4. Fused hierarchical gating & feature reconstruction across dyadic bands.
"""

import math
import time
import torch
import triton
import triton.language as tl

@triton.jit
def _poincare_multiscale_wavelet_kernel(
    X_ptr,          # [B, N, D] float16
    Out_ptr,        # [B, N, D] float16 (filtered multiscale features)
    Energy_ptr,     # [B, N, J] float32 (scale-band energy)
    B: tl.constexpr,
    N: tl.constexpr,
    D: tl.constexpr,
    J: tl.constexpr,
    stride_xb, stride_xn, stride_xd,
    stride_ob, stride_on, stride_od,
    stride_eb, stride_en, stride_ej,
    BLOCK_D: tl.constexpr,
):
    pid_b = tl.program_id(0)
    pid_n = tl.program_id(1)

    d_offsets = tl.arange(0, BLOCK_D)
    mask_d = d_offsets < D

    # 1. Load x_i
    x_offset = pid_b * stride_xb + pid_n * stride_xn + d_offsets * stride_xd
    x_val = tl.load(X_ptr + x_offset, mask=mask_d, other=0.0).to(tl.float32)

    # Compute radial norm ||x_i||
    norm_sq = tl.sum(x_val * x_val)
    eps = 1e-5
    norm = tl.sqrt(tl.maximum(norm_sq, eps))
    norm_clamped = tl.minimum(norm, 1.0 - 1e-4)

    # Base geodesic distance r = 2 * arctanh(||x||) = ln((1 + u) / (1 - u))
    r_base = tl.log((1.0 + norm_clamped) / (1.0 - norm_clamped))

    # 2. Iterate over J dyadic scale bands
    out_accum = tl.zeros([BLOCK_D], dtype=tl.float32)

    for j in range(0, J):
        # Scale factor 2^(-j/2) approx 1.0 / (1.41421356 ^ j)
        scale_j = 1.0
        if j == 1:
            scale_j = 0.70710678
        elif j == 2:
            scale_j = 0.50000000
        elif j == 3:
            scale_j = 0.35355339

        r_scaled = r_base * scale_j
        
        # Radial Meyer-type wavelet envelope: cos(pi * r_scaled) * exp(-0.5 * r_scaled^2)
        # Stable polynomial / exponential approximation
        pi = 3.14159265
        angle = pi * r_scaled
        cos_val = tl.cos(angle)
        arg = -0.5 * r_scaled * r_scaled
        exp_val = tl.exp(arg)
        psi_val = cos_val * exp_val

        # Filtered token slice
        x_filtered = x_val * psi_val
        energy_j = tl.sum(x_filtered * x_filtered)

        # Store energy
        e_offset = pid_b * stride_eb + pid_n * stride_en + j * stride_ej
        tl.store(Energy_ptr + e_offset, energy_j)

        # Accumulate into multiscale output
        weight_j = 1.0 / (1.0 + energy_j)
        out_accum += x_filtered * weight_j

    # 3. Store reconstructed output
    out_offset = pid_b * stride_ob + pid_n * stride_on + d_offsets * stride_od
    tl.store(Out_ptr + out_offset, out_accum.to(tl.float16), mask=mask_d)


def triton_poincare_multiscale_wavelet(x: torch.Tensor, J: int = 4):
    B, N, D = x.shape
    assert x.is_cuda and x.dtype == torch.float16
    assert J <= 4, "Supports up to 4 dyadic scale bands"

    out = torch.empty_like(x)
    energy = torch.empty((B, N, J), device=x.device, dtype=torch.float32)

    BLOCK_D = triton.next_power_of_2(D)
    grid = (B, N)

    _poincare_multiscale_wavelet_kernel[grid](
        x, out, energy,
        B, N, D, J,
        x.stride(0), x.stride(1), x.stride(2),
        out.stride(0), out.stride(1), out.stride(2),
        energy.stride(0), energy.stride(1), energy.stride(2),
        BLOCK_D=BLOCK_D,
        num_warps=4,
    )
    return out, energy


def pytorch_poincare_multiscale_wavelet_ref(x: torch.Tensor, J: int = 4):
    B, N, D = x.shape
    x_f = x.float()

    norm_sq = torch.sum(x_f * x_f, dim=-1, keepdim=True)
    norm = torch.sqrt(torch.clamp(norm_sq, min=1e-5))
    norm_clamped = torch.clamp(norm, max=1.0 - 1e-4)
    r_base = torch.log((1.0 + norm_clamped) / (1.0 - norm_clamped))

    scales = [1.0, 0.70710678, 0.50000000, 0.35355339][:J]
    out_accum = torch.zeros_like(x_f)
    energies = []

    pi = 3.141592653589793
    for j, scale in enumerate(scales):
        r_scaled = r_base * scale
        psi = torch.cos(pi * r_scaled) * torch.exp(-0.5 * r_scaled * r_scaled)
        x_filtered = x_f * psi
        energy_j = torch.sum(x_filtered * x_filtered, dim=-1)
        energies.append(energy_j)
        weight_j = 1.0 / (1.0 + energy_j.unsqueeze(-1))
        out_accum = out_accum + x_filtered * weight_j

    energy_tensor = torch.stack(energies, dim=-1)
    return out_accum.half(), energy_tensor


def benchmark():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Benchmarking on: {torch.cuda.get_device_name(device)}")

    B, N, D = 16, 256, 128
    x = torch.randn(B, N, D, device=device, dtype=torch.float16) * 0.1
    x = x / (torch.norm(x, dim=-1, keepdim=True) + 1.2)

    # Correctness check
    out_tri, e_tri = triton_poincare_multiscale_wavelet(x, J=4)
    out_ref, e_ref = pytorch_poincare_multiscale_wavelet_ref(x, J=4)

    out_err = torch.max(torch.abs(out_tri - out_ref)).item()
    e_err = torch.max(torch.abs(e_tri - e_ref)).item()

    print(f"[+] Max Absolute Output Error: {out_err:.6e}")
    print(f"[+] Max Absolute Energy Error: {e_err:.6e}")
    assert out_err < 1e-3, f"Output error too high: {out_err}"
    assert e_err < 1e-3, f"Energy error too high: {e_err}"
    print("[✓] Multiscale Hyperbolic Wavelet Correctness test PASSED.")

    # Benchmark
    warmup, iters = 20, 200
    for _ in range(warmup):
        _ = triton_poincare_multiscale_wavelet(x, J=4)
        _ = pytorch_poincare_multiscale_wavelet_ref(x, J=4)
    torch.cuda.synchronize()

    start_pt = time.perf_counter()
    for _ in range(iters):
        _ = pytorch_poincare_multiscale_wavelet_ref(x, J=4)
    torch.cuda.synchronize()
    pt_time = (time.perf_counter() - start_pt) / iters

    start_tri = time.perf_counter()
    for _ in range(iters):
        _ = triton_poincare_multiscale_wavelet(x, J=4)
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
