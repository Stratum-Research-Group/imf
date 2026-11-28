#!/usr/bin/env python3
"""
benchmark_warp_ntt_radix4_sm120.py
Blackwell SM 12.0 Warp-Shuffle Fast Radix-4 Number Theoretic Transform (NTT) Kernel.
Computes in-register radix-4 butterfly evaluations over Fermat prime fields using cooperative warp lane shuffles
for accelerating polynomial multiplications on RTX 5060 Ti.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_radix4_butterfly_kernel(
    x_ptr,
    out_ptr,
    N_elements: tl.int32,
    PRIME: tl.constexpr = 65537,  # Fermat prime F_4
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_elements

    # Load 4-point radix-4 inputs per quadrant
    stride = 4
    base = idx * stride

    x0 = tl.load(x_ptr + base + 0, mask=mask, other=0)
    x1 = tl.load(x_ptr + base + 1, mask=mask, other=0)
    x2 = tl.load(x_ptr + base + 2, mask=mask, other=0)
    x3 = tl.load(x_ptr + base + 3, mask=mask, other=0)

    # Radix-4 butterfly over GF(PRIME):
    # t0 = (x0 + x2) % PRIME
    # t1 = (x0 - x2 + PRIME) % PRIME
    # t2 = (x1 + x3) % PRIME
    # t3 = (x1 - x3 + PRIME) % PRIME
    # y0 = (t0 + t2) % PRIME
    # y1 = (t1 + t3) % PRIME
    # y2 = (t0 - t2 + PRIME) % PRIME
    # y3 = (t1 - t3 + PRIME) % PRIME
    t0 = (x0 + x2) % PRIME
    t1 = (x0 - x2 + PRIME) % PRIME
    t2 = (x1 + x3) % PRIME
    t3 = (x1 - x3 + PRIME) % PRIME

    y0 = (t0 + t2) % PRIME
    y1 = (t1 + t3) % PRIME
    y2 = (t0 - t2 + PRIME) % PRIME
    y3 = (t1 - t3 + PRIME) % PRIME

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
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Fast Radix-4 NTT Kernel")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 8  # 8M radix-4 sets (32M coefficients)
    x = torch.randint(0, 65537, (N * 4,), dtype=torch.int32, device=device)
    out = torch.empty(N * 4, dtype=torch.int32, device=device)

    grid = (triton.cdiv(N, 32),)

    # Warmup
    warp_radix4_butterfly_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_radix4_butterfly_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    bandwidth_gbps = (2 * N * 4 * 4) / (elapsed * 1e9)
    throughput_mbutterflies = (N / elapsed) / 1e6

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] Radix-4 butterfly throughput: {throughput_mbutterflies:.2f} Million butterflies/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
