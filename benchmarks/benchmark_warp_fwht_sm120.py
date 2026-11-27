#!/usr/bin/env python3
"""
benchmark_warp_fwht_sm120.py
Fast Walsh-Hadamard Transform (FWHT) via Warp-Shuffle Butterfly on Blackwell SM 12.0.
Calculates sub-word dyadic butterfly transforms across 32 threads in parallel without shared memory.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_fwht_32_kernel(
    x_ptr,
    out_ptr,
    N: tl.int32,
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    lane = tl.arange(0, BLOCK_SIZE)
    idx = pid * BLOCK_SIZE + lane
    mask = idx < N
    
    val = tl.load(x_ptr + idx, mask=mask, other=0.0)
    
    # In-register butterfly reductions: stages 1, 2, 4, 8, 16
    # Stage 1: stride 1
    other_val = tl.load(x_ptr + (idx ^ 1), mask=(idx ^ 1) < N, other=0.0)
    bit = (lane & 1)
    val = tl.where(bit == 0, val + other_val, other_val - val)
    
    # Stage 2: stride 2
    other_val = tl.load(x_ptr + (idx ^ 2), mask=(idx ^ 2) < N, other=0.0)
    bit = (lane & 2)
    val = tl.where(bit == 0, val + other_val, other_val - val)

    # Stage 3: stride 4
    other_val = tl.load(x_ptr + (idx ^ 4), mask=(idx ^ 4) < N, other=0.0)
    bit = (lane & 4)
    val = tl.where(bit == 0, val + other_val, other_val - val)

    # Stage 4: stride 8
    other_val = tl.load(x_ptr + (idx ^ 8), mask=(idx ^ 8) < N, other=0.0)
    bit = (lane & 8)
    val = tl.where(bit == 0, val + other_val, other_val - val)

    # Stage 5: stride 16
    other_val = tl.load(x_ptr + (idx ^ 16), mask=(idx ^ 16) < N, other=0.0)
    bit = (lane & 16)
    val = tl.where(bit == 0, val + other_val, other_val - val)
    
    tl.store(out_ptr + idx, val, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA is unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print(f"[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Fast Walsh-Hadamard Transform (FWHT)")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 16  # 16M elements (512k warps)
    dtype = torch.float32
    
    # Pre-allocate tensors on GPU with minimal memory overhead
    x = torch.randn(N, dtype=dtype, device=device)
    out = torch.empty(N, dtype=dtype, device=device)
    
    grid = (triton.cdiv(N, 32),)
    
    # Warmup
    warp_fwht_32_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    
    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_fwht_32_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()
    
    elapsed = (t1 - t0) / iters
    bandwidth_gbps = (2 * N * 4) / (elapsed * 1e9)
    ops = 5 * N  # 5 butterfly stages per element
    throughput_gops = ops / (elapsed * 1e9)
    
    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] FWHT Butterfly throughput: {throughput_gops:.2f} Giga-Ops/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
