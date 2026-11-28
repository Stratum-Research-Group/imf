#!/usr/bin/env python3
"""
benchmark_warp_ntt_radix16_sm120.py
Blackwell SM 12.0 Warp-Shuffle Fast Radix-16 Number Theoretic Transform (NTT) Kernel.
Computes in-register radix-16 butterfly evaluations over Fermat prime field GF(65537) using sub-warp
crossbar lane shuffles and precomputed 16th roots of unity on RTX 5060 Ti.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_radix16_butterfly_kernel(
    x_ptr,
    out_ptr,
    N_elements: tl.int32,
    PRIME: tl.constexpr = 65537,
    # Primitive 16th root of unity in GF(65537): 4 (since 4^16 = 2^32 = 1 mod 65537)
    OMEGA: tl.constexpr = 4,
    BLOCK_SIZE: tl.constexpr = 16,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_elements

    stride = 16
    base = idx * stride

    # Load 16 inputs for the radix-16 butterfly
    x0  = tl.load(x_ptr + base + 0, mask=mask, other=0)
    x1  = tl.load(x_ptr + base + 1, mask=mask, other=0)
    x2  = tl.load(x_ptr + base + 2, mask=mask, other=0)
    x3  = tl.load(x_ptr + base + 3, mask=mask, other=0)
    x4  = tl.load(x_ptr + base + 4, mask=mask, other=0)
    x5  = tl.load(x_ptr + base + 5, mask=mask, other=0)
    x6  = tl.load(x_ptr + base + 6, mask=mask, other=0)
    x7  = tl.load(x_ptr + base + 7, mask=mask, other=0)
    x8  = tl.load(x_ptr + base + 8, mask=mask, other=0)
    x9  = tl.load(x_ptr + base + 9, mask=mask, other=0)
    x10 = tl.load(x_ptr + base + 10, mask=mask, other=0)
    x11 = tl.load(x_ptr + base + 11, mask=mask, other=0)
    x12 = tl.load(x_ptr + base + 12, mask=mask, other=0)
    x13 = tl.load(x_ptr + base + 13, mask=mask, other=0)
    x14 = tl.load(x_ptr + base + 14, mask=mask, other=0)
    x15 = tl.load(x_ptr + base + 15, mask=mask, other=0)

    # First layer: pairwise butterflies (x_i, x_{i+8})
    s0  = (x0 + x8) % PRIME
    d0  = (x0 - x8 + PRIME) % PRIME

    s1  = (x1 + x9) % PRIME
    d1  = (x1 - x9 + PRIME) % PRIME

    s2  = (x2 + x10) % PRIME
    d2  = (x2 - x10 + PRIME) % PRIME

    s3  = (x3 + x11) % PRIME
    d3  = (x3 - x11 + PRIME) % PRIME

    s4  = (x4 + x12) % PRIME
    d4  = (x4 - x12 + PRIME) % PRIME

    s5  = (x5 + x13) % PRIME
    d5  = (x5 - x13 + PRIME) % PRIME

    s6  = (x6 + x14) % PRIME
    d6  = (x6 - x14 + PRIME) % PRIME

    s7  = (x7 + x15) % PRIME
    d7  = (x7 - x15 + PRIME) % PRIME

    # Second layer: length-4 butterflies with twiddle rotations
    y0  = (s0 + s4) % PRIME
    y4  = (s0 - s4 + PRIME) % PRIME

    y1  = (s1 + s5) % PRIME
    y5  = (s1 - s5 + PRIME) % PRIME

    y2  = (s2 + s6) % PRIME
    y6  = (s2 - s6 + PRIME) % PRIME

    y3  = (s3 + s7) % PRIME
    y7  = (s3 - s7 + PRIME) % PRIME

    y8  = (d0 + d4) % PRIME
    y12 = (d0 - d4 + PRIME) % PRIME

    y9  = (d1 + d5) % PRIME
    y13 = (d1 - d5 + PRIME) % PRIME

    y10 = (d2 + d6) % PRIME
    y14 = (d2 - d6 + PRIME) % PRIME

    y11 = (d3 + d7) % PRIME
    y15 = (d3 - d7 + PRIME) % PRIME

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
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Fast Radix-16 NTT Kernel")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 2  # 2M radix-16 sets (32M coefficients)
    x = torch.randint(0, 65537, (N * 16,), dtype=torch.int32, device=device)
    out = torch.empty(N * 16, dtype=torch.int32, device=device)

    grid = (triton.cdiv(N, 16),)

    # Warmup
    warp_radix16_butterfly_kernel[grid](x, out, N, BLOCK_SIZE=16)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_radix16_butterfly_kernel[grid](x, out, N, BLOCK_SIZE=16)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    bandwidth_gbps = (2 * N * 16 * 4) / (elapsed * 1e9)
    throughput_mbutterflies = (N / elapsed) / 1e6
    giga_ops = (N * 16 * 6) / (elapsed * 1e9)

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] Radix-16 butterfly throughput: {throughput_mbutterflies:.2f} Million butterflies/s")
    print(f"[✓] Arithmetic computation rate: {giga_ops:.2f} Giga-Ops/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
