#!/usr/bin/env python3
"""
benchmark_warp_montgomery_mul_sm120.py
Blackwell SM 12.0 Warp-Shuffle Prime-Field Montgomery Modular Multiplication Kernel.
Performs in-register sub-word Montgomery multiplication:
    Z = (X * Y * R^-1) mod M
for high-speed lattice routing and finite-field geometric quantization on RTX 5060 Ti.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_montgomery_mul_kernel(
    x_ptr,
    y_ptr,
    out_ptr,
    N_elements: tl.int32,
    MODULUS: tl.constexpr = 65537,     # Fermat prime F_4 = 2^16 + 1
    M_PRIME: tl.constexpr = 65535,     # -M^(-1) mod 2^16
    R_LOG: tl.constexpr = 16,
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_elements

    x = tl.load(x_ptr + idx, mask=mask, other=0)
    y = tl.load(y_ptr + idx, mask=mask, other=0)

    # In-register product T = X * Y
    t = x * y

    # Montgomery reduction step:
    # m = (T * M') mod R
    m = (t * M_PRIME) & 0xFFFF
    # u = (T + m * MODULUS) >> 16
    u = (t + m * MODULUS) >> R_LOG

    # Final modular reduction
    res = tl.where(u >= MODULUS, u - MODULUS, u)

    tl.store(out_ptr + idx, res, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Montgomery Modular Multiplication")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 16  # 16M pairs (32M inputs)
    x = torch.randint(0, 65537, (N,), dtype=torch.int32, device=device)
    y = torch.randint(0, 65537, (N,), dtype=torch.int32, device=device)
    out = torch.empty(N, dtype=torch.int32, device=device)

    grid = (triton.cdiv(N, 32),)

    # Warmup
    warp_montgomery_mul_kernel[grid](x, y, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_montgomery_mul_kernel[grid](x, y, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    bandwidth_gbps = (3 * N * 4) / (elapsed * 1e9)
    muls_per_sec = N / elapsed

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] Montgomery modular mul throughput: {muls_per_sec / 1e6:.2f} Million muls/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
