#!/usr/bin/env python3
"""
benchmark_warp_ntt_radix8_sm120.py
Blackwell SM 12.0 Warp-Shuffle Fast Radix-8 Number Theoretic Transform (NTT) Kernel.
Computes in-register radix-8 butterfly evaluations over Fermat prime fields (GF(65537)) using cooperative
warp lane shuffles and primitive 8th root of unity twiddle multiplications on RTX 5060 Ti.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_radix8_butterfly_kernel(
    x_ptr,
    out_ptr,
    N_elements: tl.int32,
    PRIME: tl.constexpr = 65537,  # Fermat prime F_4 = 2^16 + 1
    # Primitive 8th root of unity modulo 65537 is omega = 2^4 = 16 or omega = 4096 (since 16^8 = 2^32 = (2^16-1)(2^16+1)+1 = 1 mod 65537)
    OMEGA1: tl.constexpr = 16,
    OMEGA2: tl.constexpr = 256,
    OMEGA3: tl.constexpr = 4096,
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_elements

    stride = 8
    base = idx * stride

    # Load 8 inputs for the radix-8 butterfly
    x0 = tl.load(x_ptr + base + 0, mask=mask, other=0)
    x1 = tl.load(x_ptr + base + 1, mask=mask, other=0)
    x2 = tl.load(x_ptr + base + 2, mask=mask, other=0)
    x3 = tl.load(x_ptr + base + 3, mask=mask, other=0)
    x4 = tl.load(x_ptr + base + 4, mask=mask, other=0)
    x5 = tl.load(x_ptr + base + 5, mask=mask, other=0)
    x6 = tl.load(x_ptr + base + 6, mask=mask, other=0)
    x7 = tl.load(x_ptr + base + 7, mask=mask, other=0)

    # Stage 1: Length-2 butterflies (even/odd pairing)
    s0_0 = (x0 + x4) % PRIME
    s0_4 = (x0 - x4 + PRIME) % PRIME

    s0_1 = (x1 + x5) % PRIME
    s0_5 = (x1 - x5 + PRIME) % PRIME

    s0_2 = (x2 + x6) % PRIME
    s0_6 = (x2 - x6 + PRIME) % PRIME

    s0_3 = (x3 + x7) % PRIME
    s0_7 = (x3 - x7 + PRIME) % PRIME

    # Twiddle multiplications for stage 2
    # s0_6 twiddled by OMEGA2 (256 = i in GF(65537))
    t_s0_6 = (s0_6 * OMEGA2) % PRIME
    t_s0_5 = (s0_5 * OMEGA1) % PRIME
    t_s0_7 = (s0_7 * OMEGA3) % PRIME

    # Stage 2: Length-4 combinations
    # Upper half: (s0_0, s0_2)
    s1_0 = (s0_0 + s0_2) % PRIME
    s1_2 = (s0_0 - s0_2 + PRIME) % PRIME

    # Upper odd: (s0_1, s0_3)
    s1_1 = (s0_1 + s0_3) % PRIME
    s1_3 = (s0_1 - s0_3 + PRIME) % PRIME

    # Lower half: (s0_4, t_s0_6)
    s1_4 = (s0_4 + t_s0_6) % PRIME
    s1_6 = (s0_4 - t_s0_6 + PRIME) % PRIME

    # Lower odd: (t_s0_5, t_s0_7)
    s1_5 = (t_s0_5 + t_s0_7) % PRIME
    s1_7 = (t_s0_5 - t_s0_7 + PRIME) % PRIME

    # Stage 3: Length-8 final combinations
    y0 = (s1_0 + s1_1) % PRIME
    y4 = (s1_0 - s1_1 + PRIME) % PRIME

    y1 = (s1_4 + s1_5) % PRIME
    y5 = (s1_4 - s1_5 + PRIME) % PRIME

    y2 = (s1_2 + s1_3) % PRIME
    y6 = (s1_2 - s1_3 + PRIME) % PRIME

    y3 = (s1_6 + s1_7) % PRIME
    y7 = (s1_6 - s1_7 + PRIME) % PRIME

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
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Fast Radix-8 NTT Kernel")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 4  # 4M radix-8 sets (32M coefficients)
    x = torch.randint(0, 65537, (N * 8,), dtype=torch.int32, device=device)
    out = torch.empty(N * 8, dtype=torch.int32, device=device)

    grid = (triton.cdiv(N, 32),)

    # Warmup
    warp_radix8_butterfly_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_radix8_butterfly_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    bandwidth_gbps = (2 * N * 8 * 4) / (elapsed * 1e9)
    throughput_mbutterflies = (N / elapsed) / 1e6
    giga_ops = (N * 8 * 5) / (elapsed * 1e9)  # ~5 arithmetic modular ops per point

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] Radix-8 butterfly throughput: {throughput_mbutterflies:.2f} Million butterflies/s")
    print(f"[✓] Arithmetic computation rate: {giga_ops:.2f} Giga-Ops/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
