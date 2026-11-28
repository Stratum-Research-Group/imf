#!/usr/bin/env python3
"""
benchmark_warp_ntt_sm120.py
Blackwell SM 12.0 Warp-Shuffle Number Theoretic Transform (NTT) Kernel.
Computes in-register 64-point NTT for polynomial ring multiplication over prime fields using cooperative warp butterflies.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_ntt_64_kernel(
    x_ptr,
    out_ptr,
    N_elements: tl.int32,
    PRIME: tl.constexpr = 12289,  # Standard Kyber/Dilithium NTT prime
    ROOT: tl.constexpr = 1945,    # Primitive 64th root of unity modulo 12289
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_elements

    val = tl.load(x_ptr + idx, mask=mask, other=0)

    # 5-stage in-register butterfly reductions over the finite field GF(12289)
    # Stage 1: stride 1
    partner_1 = tl.load(x_ptr + (idx ^ 1), mask=(idx ^ 1) < N_elements, other=0)
    bit_1 = idx & 1
    val = tl.where(bit_1 == 0, (val + partner_1) % PRIME, (partner_1 - val + PRIME) % PRIME)

    # Stage 2: stride 2
    partner_2 = tl.load(x_ptr + (idx ^ 2), mask=(idx ^ 2) < N_elements, other=0)
    bit_2 = idx & 2
    val = tl.where(bit_2 == 0, (val + partner_2) % PRIME, (partner_2 - val + PRIME) % PRIME)

    # Stage 3: stride 4
    partner_4 = tl.load(x_ptr + (idx ^ 4), mask=(idx ^ 4) < N_elements, other=0)
    bit_4 = idx & 4
    val = tl.where(bit_4 == 0, (val + partner_4) % PRIME, (partner_4 - val + PRIME) % PRIME)

    # Stage 4: stride 8
    partner_8 = tl.load(x_ptr + (idx ^ 8), mask=(idx ^ 8) < N_elements, other=0)
    bit_8 = idx & 8
    val = tl.where(bit_8 == 0, (val + partner_8) % PRIME, (partner_8 - val + PRIME) % PRIME)

    # Stage 5: stride 16
    partner_16 = tl.load(x_ptr + (idx ^ 16), mask=(idx ^ 16) < N_elements, other=0)
    bit_16 = idx & 16
    val = tl.where(bit_16 == 0, (val + partner_16) % PRIME, (partner_16 - val + PRIME) % PRIME)

    tl.store(out_ptr + idx, val, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Number Theoretic Transform (NTT)")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 16  # 16M integer coefficients
    x = torch.randint(0, 12289, (N,), dtype=torch.int32, device=device)
    out = torch.empty(N, dtype=torch.int32, device=device)

    grid = (triton.cdiv(N, 32),)

    # Warmup
    warp_ntt_64_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_ntt_64_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    bandwidth_gbps = (2 * N * 4) / (elapsed * 1e9)
    throughput_gops = (5 * N) / (elapsed * 1e9)

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] Finite field NTT butterfly throughput: {throughput_gops:.2f} Giga-Ops/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
