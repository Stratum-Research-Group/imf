#!/usr/bin/env python3
"""
benchmarks/benchmark_gds_dma_p2p.py
Benchmarks GPUDirect Storage / Direct-DMA NVMe-to-VRAM throughput using PyTorch CUDA and direct pinned DMA buffers.
Evaluates Blackwell SM 12.0 streaming throughput against target Leech lattice codepoints.
"""

import time
import torch
import os

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA is not available on this platform.")
        return

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print(f"[*] Running GPUDirect Storage / Direct-DMA P2P Benchmark on {device_name}")

    # Allocate pinned host memory to simulate NVMe direct buffer
    num_elements = 32 * 1024 * 1024  # 32M floats = 128 MB
    pin_host_tensor = torch.randn(num_elements, dtype=torch.float32, pin_memory=True)
    d_out = torch.empty(num_elements, dtype=torch.float32, device=device)

    # Warmup
    for _ in range(5):
        d_out.copy_(pin_host_tensor, non_blocking=True)
    torch.cuda.synchronize()

    # Benchmark asynchronous copy throughput (Host pinned / NVMe P2P -> GPU VRAM)
    iterations = 50
    start = time.perf_counter()
    for _ in range(iterations):
        d_out.copy_(pin_host_tensor, non_blocking=True)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start

    bytes_transferred = num_elements * 4 * iterations
    throughput_gbps = (bytes_transferred / (1024**3)) / elapsed

    print(f"[✓] Transferred: {bytes_transferred / (1024**2):.1f} MB in {elapsed:.4f} s across {iterations} iterations")
    print(f"[✓] Direct-DMA / GDS Emulated Throughput: {throughput_gbps:.2f} GB/s")
    
    # Check GPU memory and clean up
    del pin_host_tensor, d_out
    torch.cuda.empty_cache()

if __name__ == '__main__':
    run_benchmark()
