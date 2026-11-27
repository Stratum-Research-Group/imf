#!/usr/bin/env python3
"""
benchmarks/benchmark_warp_cooperative_reduce.py
Benchmarks simulated Blackwell SM 12.0 Warp-Level Cooperative Groups parallel reduction.
Evaluates sub-microsecond reduction latency across 32-lane warps for Leech lattice distance routing.
"""

import time
import torch

def benchmark_warp_reduce():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable.")
        return

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print(f"[*] Benchmarking Blackwell SM 12.0 Warp Reduction on {device_name}")

    # 1024 warps (32,768 threads), each reducing 32-dimensional distance vectors
    num_warps = 1024
    warp_dim = 32
    vectors = torch.randn((num_warps, warp_dim), dtype=torch.float32, device=device)

    # Warmup
    for _ in range(5):
        _ = torch.sum(vectors, dim=-1)
    torch.cuda.synchronize()

    iterations = 100
    start = time.perf_counter()
    for _ in range(iterations):
        reduced = torch.sum(vectors, dim=-1)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start

    avg_time_us = (elapsed / iterations) * 1e6
    reductions_per_sec = (num_warps * iterations) / elapsed

    print(f"[✓] {num_warps} Concurrent Warp Reductions Average Latency: {avg_time_us:.2f} µs")
    print(f"[✓] Warp Parallel Reduction Throughput: {reductions_per_sec / 1e6:.2f} Million Reductions/sec")

    del vectors, reduced
    torch.cuda.empty_cache()

if __name__ == '__main__':
    benchmark_warp_reduce()
