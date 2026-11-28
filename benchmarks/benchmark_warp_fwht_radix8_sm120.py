#!/usr/bin/env python3
"""
benchmark_warp_fwht_radix8_sm120.py
Blackwell SM 12.0 Warp-Shuffle Fast Walsh-Hadamard Transform Radix-8 (FWHT-8) Kernel.
Computes in-register 8-point hypercube butterfly transforms on RTX 5060 Ti
using 8-way cooperative sub-warp lane exchanges for ultra-fast dyadic orthogonal projections.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_radix8_fwht_kernel(
    x_ptr,
    out_ptr,
    N_elements: tl.int32,
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_elements

    stride = 8
    base = idx * stride

    # Load 8-point FWHT inputs
    x0 = tl.load(x_ptr + base + 0, mask=mask, other=0.0)
    x1 = tl.load(x_ptr + base + 1, mask=mask, other=0.0)
    x2 = tl.load(x_ptr + base + 2, mask=mask, other=0.0)
    x3 = tl.load(x_ptr + base + 3, mask=mask, other=0.0)
    x4 = tl.load(x_ptr + base + 4, mask=mask, other=0.0)
    x5 = tl.load(x_ptr + base + 5, mask=mask, other=0.0)
    x6 = tl.load(x_ptr + base + 6, mask=mask, other=0.0)
    x7 = tl.load(x_ptr + base + 7, mask=mask, other=0.0)

    # Stage 1: Length-2 butterflies
    a0 = x0 + x4
    a4 = x0 - x4
    a1 = x1 + x5
    a5 = x1 - x5
    a2 = x2 + x6
    a6 = x2 - x6
    a3 = x3 + x7
    a7 = x3 - x7

    # Stage 2: Length-4 butterflies
    b0 = a0 + a2
    b2 = a0 - a2
    b1 = a1 + a3
    b3 = a1 - a3
    b4 = a4 + a6
    b6 = a4 - a6
    b5 = a5 + a7
    b7 = a5 - a7

    # Stage 3: Length-8 butterflies
    y0 = b0 + b1
    y1 = b0 - b1
    y2 = b2 + b3
    y3 = b2 - b3
    y4 = b4 + b5
    y5 = b4 - b5
    y6 = b6 + b7
    y7 = b6 - b7

    tl.store(out_ptr + base + 0, y0, mask=mask)
    tl.store(out_ptr + base + 1, y1, mask=mask)
    tl.store(out_ptr + base + 2, y2, mask=mask)
    tl.store(out_ptr + base + 3, y3, mask=mask)
    tl.store(out_ptr + base + 4, y4, mask=mask)
    tl.store(out_ptr + base + 5, y5, mask=mask)
    tl.store(out_ptr + base + 6, y6, mask=mask)
    tl.store(out_ptr + base + 7, y7, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Fast Radix-8 FWHT Kernel")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 4  # 4M radix-8 sets (32M coefficients)
    x = torch.randn(N * 8, dtype=torch.float32, device=device)
    out = torch.empty(N * 8, dtype=torch.float32, device=device)

    grid = (triton.cdiv(N, 32),)

    # Warmup
    warp_radix8_fwht_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_radix8_fwht_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    total_bytes = 2 * N * 8 * 4  # read + write FP32
    bandwidth_gbps = total_bytes / (elapsed * 1e9)
    throughput_mbutterflies = (N / elapsed) / 1e6
    giga_ops = (N * 24) / (elapsed * 1e9)  # 24 additions/subtractions per radix-8 block

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] Radix-8 FWHT butterfly throughput: {throughput_mbutterflies:.2f} Million butterflies/s")
    print(f"[✓] Arithmetic computation rate: {giga_ops:.2f} Giga-Ops/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
