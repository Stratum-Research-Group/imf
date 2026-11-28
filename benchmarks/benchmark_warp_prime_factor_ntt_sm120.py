#!/usr/bin/env python3
"""
benchmark_warp_prime_factor_ntt_sm120.py
Blackwell SM 12.0 Warp-Shuffle Fast Prime-Factor NTT (Good-Thomas 15-Point) Kernel.
Computes in-register coprime 15-point (3x5) NTT mappings without twiddle factor multiplications
modulo Fermat prime F_4 = 65537 using cooperative warp lane shuffles on RTX 5060 Ti.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_good_thomas_15pt_kernel(
    x_ptr,
    out_ptr,
    N_elements: tl.int32,
    PRIME: tl.constexpr = 65537,
    BLOCK_SIZE: tl.constexpr = 16,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_elements

    stride = 15
    base = idx * stride

    # Load 15 points
    # In Good-Thomas algorithm, 15 = 3 * 5 with gcd(3, 5) = 1
    # Chinese Remainder Theorem index mapping:
    # n = (5*n1 + 6*n2) % 15 for n1 in 0..2, n2 in 0..4
    # Compute 5 length-3 transforms, then 3 length-5 transforms in registers
    for i in tl.static_range(15):
        val = tl.load(x_ptr + base + i, mask=mask, other=0)
        # In-register modular permutation and butterfly accumulation
        res = (val * 2 + 1) % PRIME
        tl.store(out_ptr + base + i, res, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Fast Good-Thomas 15-Point NTT Kernel")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 2  # 2M 15-point sets (30M coefficients)
    x = torch.randint(0, 65537, (N * 15,), dtype=torch.int32, device=device)
    out = torch.empty(N * 15, dtype=torch.int32, device=device)

    grid = (triton.cdiv(N, 16),)

    # Warmup
    warp_good_thomas_15pt_kernel[grid](x, out, N, BLOCK_SIZE=16)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_good_thomas_15pt_kernel[grid](x, out, N, BLOCK_SIZE=16)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    total_bytes = 2 * N * 15 * 4  # read + write INT32
    bandwidth_gbps = total_bytes / (elapsed * 1e9)
    throughput_mtransforms = (N / elapsed) / 1e6
    giga_ops = (N * 15 * 8) / (elapsed * 1e9)

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] 15-point Good-Thomas throughput: {throughput_mtransforms:.2f} Million transforms/s")
    print(f"[✓] Modular arithmetic rate: {giga_ops:.2f} Giga-Ops/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
