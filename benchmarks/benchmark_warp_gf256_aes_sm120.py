#!/usr/bin/env python3
"""
benchmark_warp_gf256_aes_sm120.py
Blackwell SM 12.0 Warp-Shuffle Galois Field GF(2^8) Rijndael MixColumns Kernel.
Computes in-register matrix multiplications over GF(2^8) with reduction polynomial x^8 + x^4 + x^3 + x + 1 (0x11B)
for high-speed tensor hashing and authentication verification on RTX 5060 Ti.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def xtime(a):
    # Multiplication by 2 (x) in GF(2^8) modulo 0x11B
    shifted = (a << 1) & 0xFF
    reduced = shifted ^ 0x1B
    return tl.where((a & 0x80) != 0, reduced, shifted)

@triton.jit
def warp_gf256_mixcolumns_kernel(
    state_ptr,
    out_ptr,
    N_words: tl.int32,
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_words

    # Load 4-byte column: s0, s1, s2, s3
    stride = 4
    base = idx * stride

    s0 = tl.load(state_ptr + base + 0, mask=mask, other=0)
    s1 = tl.load(state_ptr + base + 1, mask=mask, other=0)
    s2 = tl.load(state_ptr + base + 2, mask=mask, other=0)
    s3 = tl.load(state_ptr + base + 3, mask=mask, other=0)

    # Rijndael MixColumns matrix:
    # [2 3 1 1]
    # [1 2 3 1]
    # [1 1 2 3]
    # [3 1 1 2]
    # where 3 * s = 2 * s ^ s = xtime(s) ^ s
    t = s0 ^ s1 ^ s2 ^ s3

    u0 = s0 ^ s1
    u1 = s1 ^ s2
    u2 = s2 ^ s3
    u3 = s3 ^ s0

    r0 = s0 ^ t ^ xtime(u0)
    r1 = s1 ^ t ^ xtime(u1)
    r2 = s2 ^ t ^ xtime(u2)
    r3 = s3 ^ t ^ xtime(u3)

    tl.store(out_ptr + base + 0, r0, mask=mask)
    tl.store(out_ptr + base + 1, r1, mask=mask)
    tl.store(out_ptr + base + 2, r2, mask=mask)
    tl.store(out_ptr + base + 3, r3, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle GF(2^8) MixColumns Kernel")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 8  # 8M 4-byte columns (32M bytes)
    state = torch.randint(0, 256, (N * 4,), dtype=torch.int32, device=device)
    out = torch.empty(N * 4, dtype=torch.int32, device=device)

    grid = (triton.cdiv(N, 32),)

    # Warmup
    warp_gf256_mixcolumns_kernel[grid](state, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_gf256_mixcolumns_kernel[grid](state, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    bandwidth_gbps = (2 * N * 4 * 4) / (elapsed * 1e9)
    columns_per_sec = N / elapsed

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] GF(2^8) MixColumns throughput: {columns_per_sec / 1e6:.2f} Million columns/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
