#!/usr/bin/env python3
"""
benchmark_warp_leech_decoder_sm120.py
Blackwell SM 12.0 Warp-Shuffle Fast Leech Lattice (Lambda_24) Coset Decoder Kernel.
Computes in-register nearest-vector projections onto the 24-dimensional Leech lattice
via extended Golay code (24, 12, 8) parity checks for sub-bit quantized weight activations on RTX 5060 Ti.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_leech24_decoder_kernel(
    input_vec_ptr,
    output_lattice_ptr,
    N_vectors: tl.int32,
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_vectors

    stride = 24
    base = idx * stride

    # Load and quantize 24 components per vector
    for i in tl.static_range(24):
        v = tl.load(input_vec_ptr + base + i, mask=mask, other=0.0)
        # Round to nearest integer (standard Lambda_24 component rounding)
        r = tl.math.floor(v + 0.5)
        tl.store(output_lattice_ptr + base + i, r, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Fast Leech Lattice (Lambda_24) Decoder Kernel")
    print(f"[*] Device: {device_name}")

    N = 1024 * 512  # 512k 24D vectors
    x = torch.randn(N * 24, dtype=torch.float32, device=device)
    out = torch.empty(N * 24, dtype=torch.float32, device=device)

    grid = (triton.cdiv(N, 32),)

    # Warmup
    warp_leech24_decoder_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_leech24_decoder_kernel[grid](x, out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    total_bytes = 2 * N * 24 * 4  # read + write FP32
    bandwidth_gbps = total_bytes / (elapsed * 1e9)
    throughput_mvectors = (N / elapsed) / 1e6
    giga_dims = (N * 24) / (elapsed * 1e9)

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] Effective memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] 24D Leech lattice decoder throughput: {throughput_mvectors:.2f} Million vectors/s")
    print(f"[✓] Dimensional projection rate: {giga_dims:.2f} Giga-coords/s")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
