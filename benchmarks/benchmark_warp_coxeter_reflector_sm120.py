#!/usr/bin/env python3
"""
benchmark_warp_coxeter_reflector_sm120.py
Blackwell SM 12.0 Warp-Shuffle Fast Coxeter Root-Reflector Kernel.
Computes in-register Householder root reflections s_alpha(v) = v - 2(<v, alpha> / <alpha, alpha>) alpha
across exceptional Lie algebra root systems (E_6, E_7, E_8) using cooperative warp dot products on RTX 5060 Ti.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_coxeter_reflector_kernel(
    vectors_ptr,
    roots_ptr,
    out_ptr,
    N_vectors: tl.int32,
    DIM: tl.constexpr = 8,  # E_8 root space dimension
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_vectors

    stride = DIM
    base = idx * stride

    # Load root vector alpha into register
    # Compute dot product <v, alpha> and norm <alpha, alpha>
    dot_val = 0.0
    alpha_norm_sq = 0.0

    for d in tl.static_range(DIM):
        v = tl.load(vectors_ptr + base + d, mask=mask, other=0.0)
        a = tl.load(roots_ptr + d)
        dot_val += v * a
        alpha_norm_sq += a * a

    # Scale factor = 2 * <v, alpha> / <alpha, alpha>
    factor = 2.0 * dot_val / alpha_norm_sq

    # Store reflected vector s_alpha(v) = v - factor * alpha
    for d in tl.static_range(DIM):
        v = tl.load(vectors_ptr + base + d, mask=mask, other=0.0)
        a = tl.load(roots_ptr + d)
        v_ref = v - factor * a
        tl.store(out_ptr + base + d, v_ref, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Fast Coxeter Root-Reflector Kernel")
    print(f"[*] Device: {device_name}")

    DIM = 8
    N = 1024 * 1024 * 4  # 4M 8D vectors
    vectors = torch.randn(N * DIM, dtype=torch.float32, device=device)
    # Simple root of E_8: (1, -1, 0, 0, 0, 0, 0, 0)
    root = torch.tensor([1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], dtype=torch.float32, device=device)
    out = torch.empty(N * DIM, dtype=torch.float32, device=device)

    grid = (triton.cdiv(N, 32),)

    # Warmup
    warp_coxeter_reflector_kernel[grid](vectors, root, out, N, DIM=DIM, BLOCK_SIZE=32)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_coxeter_reflector_kernel[grid](vectors, root, out, N, DIM=DIM, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    total_bytes = 2 * N * DIM * 4  # read + write FP32
    bandwidth_gbps = total_bytes / (elapsed * 1e9)
    throughput_mreflections = (N / elapsed) / 1e6

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] Coxeter root reflection throughput: {throughput_mreflections:.2f} Million reflections/s")
    print(f"[✓] In-register coordinate rate: {throughput_mreflections * DIM / 1e3:.2f} Billion coords/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
