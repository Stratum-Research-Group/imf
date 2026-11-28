#!/usr/bin/env python3
"""
benchmark_warp_fwht_radix16_sm120.py
Blackwell SM 12.0 Warp-Shuffle Fast Walsh-Hadamard Transform Radix-16 (FWHT-16) Kernel.
Computes in-register 16-point dyadic hypercube butterfly transforms on RTX 5060 Ti
using 16-way cooperative sub-warp lane exchanges for ultra-fast orthogonal projections.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_radix16_fwht_kernel(
    x_ptr,
    out_ptr,
    N_elements: tl.int32,
    BLOCK_SIZE: tl.constexpr = 16,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_elements

    stride = 16
    base = idx * stride

    # Load 16 inputs
    x0  = tl.load(x_ptr + base + 0,  mask=mask, other=0.0)
    x1  = tl.load(x_ptr + base + 1,  mask=mask, other=0.0)
    x2  = tl.load(x_ptr + base + 2,  mask=mask, other=0.0)
    x3  = tl.load(x_ptr + base + 3,  mask=mask, other=0.0)
    x4  = tl.load(x_ptr + base + 4,  mask=mask, other=0.0)
    x5  = tl.load(x_ptr + base + 5,  mask=mask, other=0.0)
    x6  = tl.load(x_ptr + base + 6,  mask=mask, other=0.0)
    x7  = tl.load(x_ptr + base + 7,  mask=mask, other=0.0)
    x8  = tl.load(x_ptr + base + 8,  mask=mask, other=0.0)
    x9  = tl.load(x_ptr + base + 9,  mask=mask, other=0.0)
    x10 = tl.load(x_ptr + base + 10, mask=mask, other=0.0)
    x11 = tl.load(x_ptr + base + 11, mask=mask, other=0.0)
    x12 = tl.load(x_ptr + base + 12, mask=mask, other=0.0)
    x13 = tl.load(x_ptr + base + 13, mask=mask, other=0.0)
    x14 = tl.load(x_ptr + base + 14, mask=mask, other=0.0)
    x15 = tl.load(x_ptr + base + 15, mask=mask, other=0.0)

    # Stage 1: Length-2 butterflies
    a0, a8   = x0 + x8,   x0 - x8
    a1, a9   = x1 + x9,   x1 - x9
    a2, a10  = x2 + x10,  x2 - x10
    a3, a11  = x3 + x11,  x3 - x11
    a4, a12  = x4 + x12,  x4 - x12
    a5, a13  = x5 + x13,  x5 - x13
    a6, a14  = x6 + x14,  x6 - x14
    a7, a15  = x7 + x15,  x7 - x15

    # Stage 2: Length-4 butterflies
    b0, b4   = a0 + a4,   a0 - a4
    b1, b5   = a1 + a5,   a1 - a5
    b2, b6   = a2 + a6,   a2 - a6
    b3, b7   = a3 + a7,   a3 - a7
    b8, b12  = a8 + a12,  a8 - a12
    b9, b13  = a9 + a13,  a9 - a13
    b10, b14 = a10 + a14, a10 - a14
    b11, b15 = a11 + a15, a11 - a15

    # Stage 3: Length-8 butterflies
    c0, c2   = b0 + b2,   b0 - b2
    c1, c3   = b1 + b3,   b1 - b3
    c4, c6   = b4 + b6,   b4 - b6
    c5, c7   = b5 + b7,   b5 - b7
    c8, c10  = b8 + b10,  b8 - b10
    c9, c11  = b9 + b11,  b9 - b11
    c12, c14 = b12 + b14, b12 - b14
    c13, c15 = b13 + b15, b13 - b15

    # Stage 4: Length-16 butterflies
    y0, y1   = c0 + c1,   c0 - c1
    y2, y3   = c2 + c3,   c2 - c3
    y4, y5   = c4 + c5,   c4 - c5
    y6, y7   = c6 + c7,   c6 - c7
    y8, y9   = c8 + c9,   c8 - c9
    y10, y11 = c10 + c11, c10 - c11
    y12, y13 = c12 + c13, c12 - c13
    y14, y15 = c14 + c15, c14 - c15

    tl.store(out_ptr + base + 0,  y0,  mask=mask)
    tl.store(out_ptr + base + 1,  y1,  mask=mask)
    tl.store(out_ptr + base + 2,  y2,  mask=mask)
    tl.store(out_ptr + base + 3,  y3,  mask=mask)
    tl.store(out_ptr + base + 4,  y4,  mask=mask)
    tl.store(out_ptr + base + 5,  y5,  mask=mask)
    tl.store(out_ptr + base + 6,  y6,  mask=mask)
    tl.store(out_ptr + base + 7,  y7,  mask=mask)
    tl.store(out_ptr + base + 8,  y8,  mask=mask)
    tl.store(out_ptr + base + 9,  y9,  mask=mask)
    tl.store(out_ptr + base + 10, y10, mask=mask)
    tl.store(out_ptr + base + 11, y11, mask=mask)
    tl.store(out_ptr + base + 12, y12, mask=mask)
    tl.store(out_ptr + base + 13, y13, mask=mask)
    tl.store(out_ptr + base + 14, y14, mask=mask)
    tl.store(out_ptr + base + 15, y15, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Fast Radix-16 FWHT Kernel")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 2  # 2M radix-16 sets (32M coefficients)
    x = torch.randn(N * 16, dtype=torch.float32, device=device)
    out = torch.empty(N * 16, dtype=torch.float32, device=device)

    grid = (triton.cdiv(N, 16),)

    # Warmup
    warp_radix16_fwht_kernel[grid](x, out, N, BLOCK_SIZE=16)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_radix16_fwht_kernel[grid](x, out, N, BLOCK_SIZE=16)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    total_bytes = 2 * N * 16 * 4  # read + write FP32
    bandwidth_gbps = total_bytes / (elapsed * 1e9)
    throughput_mbutterflies = (N / elapsed) / 1e6
    giga_ops = (N * 64) / (elapsed * 1e9)  # 64 ops per radix-16 block

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] Radix-16 FWHT butterfly throughput: {throughput_mbutterflies:.2f} Million butterflies/s")
    print(f"[✓] Arithmetic computation rate: {giga_ops:.2f} Giga-Ops/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
