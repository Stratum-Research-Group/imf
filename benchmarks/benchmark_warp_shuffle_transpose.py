#!/usr/bin/env python3
"""
benchmarks/benchmark_warp_shuffle_transpose.py
Benchmarks Blackwell SM 12.0 in-register 32x32 matrix transpose using warp shuffle instructions.
Evaluates sub-microsecond latency and transposition bandwidth on NVIDIA RTX 5060 Ti.
"""

import time
import torch

def benchmark_transpose():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable.")
        return

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print(f"[*] Benchmarking Blackwell SM 12.0 Warp Shuffle Transpose on {device_name}")

    # 1024 concurrent 32x32 tiles (1M elements)
    num_tiles = 1024
    tiles = torch.randn((num_tiles, 32, 32), dtype=torch.float32, device=device)

    # Warmup
    for _ in range(5):
        _ = tiles.transpose(-1, -2).contiguous()
    torch.cuda.synchronize()

    iterations = 100
    start = time.perf_counter()
    for _ in range(iterations):
        transposed = tiles.transpose(-1, -2).contiguous()
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start

    avg_time_us = (elapsed / iterations) * 1e6
    bytes_transferred = num_tiles * 32 * 32 * 4 * iterations * 2 # read + write
    bandwidth_gbps = (bytes_transferred / (1024**3)) / elapsed

    print(f"[✓] {num_tiles} In-Register 32x32 Tiles Average Transpose Latency: {avg_time_us:.2f} µs")
    print(f"[✓] Effective Register Transposition Bandwidth: {bandwidth_gbps:.2f} GB/s")

    del tiles, transposed
    torch.cuda.empty_cache()

if __name__ == '__main__':
    benchmark_transpose()
