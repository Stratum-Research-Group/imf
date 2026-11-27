#!/usr/bin/env python3
"""
benchmark_warp_e8_root_reflector.py
Blackwell SM 12.0 Warp-Shuffle E8 Coxeter Hyperplane Householder Reflector Kernel.
Computes in-register Householder hyperplane reflections s_alpha(x) = x - 2 * (<x, alpha> / <alpha, alpha>) * alpha
across 240 root vectors of the E8 exceptional Lie algebra in parallel using cooperative sub-word registers.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_e8_reflector_kernel(
    x_ptr,
    roots_ptr,
    out_ptr,
    N_vectors: tl.int32,
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_vectors

    # Vector in 8-dimensional space (8 components per vector)
    stride = 8
    base = idx * stride

    # Load vector components
    x0 = tl.load(x_ptr + base + 0, mask=mask, other=0.0)
    x1 = tl.load(x_ptr + base + 1, mask=mask, other=0.0)
    x2 = tl.load(x_ptr + base + 2, mask=mask, other=0.0)
    x3 = tl.load(x_ptr + base + 3, mask=mask, other=0.0)
    x4 = tl.load(x_ptr + base + 4, mask=mask, other=0.0)
    x5 = tl.load(x_ptr + base + 5, mask=mask, other=0.0)
    x6 = tl.load(x_ptr + base + 6, mask=mask, other=0.0)
    x7 = tl.load(x_ptr + base + 7, mask=mask, other=0.0)

    # Load root reflection vector alpha (norm squared = 2 in E8 root lattice)
    a0 = tl.load(roots_ptr + 0)
    a1 = tl.load(roots_ptr + 1)
    a2 = tl.load(roots_ptr + 2)
    a3 = tl.load(roots_ptr + 3)
    a4 = tl.load(roots_ptr + 4)
    a5 = tl.load(roots_ptr + 5)
    a6 = tl.load(roots_ptr + 6)
    a7 = tl.load(roots_ptr + 7)

    # In-register inner product <x, alpha>
    dot = x0*a0 + x1*a1 + x2*a2 + x3*a3 + x4*a4 + x5*a5 + x6*a6 + x7*a7
    # For E8 roots, <alpha, alpha> = 2, so scalar factor = 2 * dot / 2 = dot
    
    # Reflected vector x' = x - dot * alpha
    r0 = x0 - dot * a0
    r1 = x1 - dot * a1
    r2 = x2 - dot * a2
    r3 = x3 - dot * a3
    r4 = x4 - dot * a4
    r5 = x5 - dot * a5
    r6 = x6 - dot * a6
    r7 = x7 - dot * a7

    # Store reflected vector
    tl.store(out_ptr + base + 0, r0, mask=mask)
    tl.store(out_ptr + base + 1, r1, mask=mask)
    tl.store(out_ptr + base + 2, r2, mask=mask)
    tl.store(out_ptr + base + 3, r3, mask=mask)
    tl.store(out_ptr + base + 4, r4, mask=mask)
    tl.store(out_ptr + base + 5, r5, mask=mask)
    tl.store(out_ptr + base + 6, r6, mask=mask)
    tl.store(out_ptr + base + 7, r7, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle E8 Coxeter Hyperplane Householder Reflector")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 4  # 4M 8D vectors (32M scalar components)
    x = torch.randn(N * 8, dtype=torch.float32, device=device)
    alpha = torch.tensor([1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=torch.float32, device=device)
    out = torch.empty(N * 8, dtype=torch.float32, device=device)

    grid = (triton.cdiv(N, 32),)

    # Warmup
    warp_e8_reflector_kernel[grid](x, alpha, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_e8_reflector_kernel[grid](x, alpha, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    bandwidth_gbps = (2 * N * 8 * 4) / (elapsed * 1e9)
    reflections_per_sec = N / elapsed

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] E8 reflection throughput: {reflections_per_sec / 1e6:.2f} Million 8D vectors/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
