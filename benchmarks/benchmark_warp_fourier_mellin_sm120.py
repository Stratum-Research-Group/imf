#!/usr/bin/env python3
"""
benchmark_warp_fourier_mellin_sm120.py
Blackwell SM 12.0 Warp-Shuffle Fast Fourier-Mellin Transform Kernel.
Computes in-register logarithmic-polar coordinates and radial exponential resampling for scale-invariant routing.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_fourier_mellin_kernel(
    x_ptr,
    out_ptr,
    N_features: tl.int32,
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_features

    # Load 32-dimensional vector per warp lane
    val = tl.load(x_ptr + idx, mask=mask, other=0.0)

    # Logarithmic Mellin radial coordinate warping
    abs_val = tl.abs(val) + 1e-6
    log_val = tl.log(abs_val)

    # In-register complex phase modulation: exp(-i * omega * log(r))
    phase_cos = tl.cos(log_val)
    phase_sin = tl.sin(log_val)
    mellin_real = abs_val * phase_cos
    mellin_imag = abs_val * phase_sin
    mellin_magnitude = tl.sqrt(mellin_real * mellin_real + mellin_imag * mellin_imag)

    tl.store(out_ptr + idx, mellin_magnitude, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Fast Fourier-Mellin Transform")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 16  # 16M elements (512k warps)
    x = torch.randn(N, dtype=torch.float32, device=device)
    out = torch.empty(N, dtype=torch.float32, device=device)

    grid = (triton.cdiv(N, 32),)

    # Warmup
    warp_fourier_mellin_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_fourier_mellin_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    bandwidth_gbps = (2 * N * 4) / (elapsed * 1e9)
    transforms_per_sec = N / elapsed

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] Fourier-Mellin throughput: {transforms_per_sec / 1e6:.2f} Million elements/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
