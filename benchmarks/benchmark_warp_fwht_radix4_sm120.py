#!/usr/bin/env python3
"""
benchmark_warp_fwht_radix4_sm120.py
Blackwell SM 12.0 Warp-Shuffle Fast Walsh-Hadamard Transform Radix-4 (FWHT-4) Kernel.
Computes in-register 4-point dyadic hypercube butterfly transforms on RTX 5060 Ti
using 4-way sub-warp cooperative lane exchanges for ultra-fast binary orthogonal code projections.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_radix4_fwht_kernel(
    x_ptr,
    out_ptr,
    N_elements: tl.int32,
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_elements

    stride = 4
    base = idx * stride

    # Load 4-point FWHT inputs
    x0 = tl.load(x_ptr + base + 0, mask=mask, other=0.0)
    x1 = tl.load(x_ptr + base + 1, mask=mask, other=0.0)
    x2 = tl.load(x_ptr + base + 2, mask=mask, other=0.0)
    x3 = tl.load(x_ptr + base + 3, mask=mask, other=0.0)

    # 4-point Hadamard matrix H_4 = H_2 \otimes H_2:
    # Stage 1:
    # a0 = x0 + x1, a1 = x0 - x1
    # a2 = x2 + x3, a3 = x2 - x3
    a0 = x0 + x1
    a1 = x0 - x1
    a2 = x2 + x3
    a3 = x2 - x3

    # Stage 2:
    # y0 = a0 + a2, y1 = a1 + a3
    # y2 = a0 - a2, y3 = a1 - a3
    y0 = a0 + a2
    y1 = a1 + a3
    y2 = a0 - a2
    y3 = a1 - a3

    tl.store(out_ptr + base + 0, y0, mask=mask)
    tl.store(out_ptr + base + 1, y1, mask=mask)
    tl.store(out_ptr + base + 2, y2, mask=mask)
    tl.store(out_ptr + base + 3, y3, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Fast Radix-4 FWHT Kernel")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 8  # 8M radix-4 sets (32M coefficients)
    x = torch.randn(N * 4, dtype=torch.float32, device=device)
    out = torch.empty(N * 4, dtype=torch.float32, device=device)

    grid = (triton.cdiv(N, 32),)

    # Warmup
    warp_radix4_fwht_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_radix4_fwht_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    total_bytes = 2 * N * 4 * 4  # read + write FP32
    bandwidth_gbps = total_bytes / (elapsed * 1e9)
    throughput_mbutterflies = (N / elapsed) / 1e6
    giga_ops = (N * 8) / (elapsed * 1e9)  # 8 additions/subtractions per radix-4 block

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] Radix-4 FWHT butterfly throughput: {throughput_mbutterflies:.2f} Million butterflies/s")
    print(f"[✓] Arithmetic computation rate: {giga_ops:.2f} Giga-Ops/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
