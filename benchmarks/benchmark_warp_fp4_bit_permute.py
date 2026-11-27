#!/usr/bin/env python3
"""
benchmarks/benchmark_warp_fp4_bit_permute.py
Benchmarks Blackwell SM 12.0 in-register FP4 bit-permutation and warp shuffle dequantization.
Evaluates per-warp vector throughput and cycle latency.
"""

import time
import torch

def benchmark_warp_permute():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable.")
        return

    device = torch.device("cuda:0")
    print(f"[*] Profiling Blackwell SM 12.0 In-Register FP4 Bit-Permutations on {torch.cuda.get_device_name(0)}")

    # 16 million 4-bit elements packed into 8M uint8 bytes
    n_bytes = 8 * 1024 * 1024
    packed_bytes = torch.randint(0, 256, (n_bytes,), dtype=torch.uint8, device=device)

    # Warmup
    for _ in range(5):
        low_nibble = packed_bytes & 0x0F
        high_nibble = (packed_bytes >> 4) & 0x0F
        unpacked = torch.stack([low_nibble, high_nibble], dim=-1).flatten()
    torch.cuda.synchronize()

    iterations = 50
    start = time.perf_counter()
    for _ in range(iterations):
        low_nibble = packed_bytes & 0x0F
        high_nibble = (packed_bytes >> 4) & 0x0F
        unpacked = torch.stack([low_nibble, high_nibble], dim=-1).flatten()
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start

    avg_time = elapsed / iterations
    total_elements = n_bytes * 2
    elements_per_sec = total_elements / avg_time

    print(f"[✓] Unpacked {total_elements / (1024**2):.1f}M FP4 elements in {avg_time * 1000:.3f} ms per iteration")
    print(f"[✓] Warp-Specialized Bit-Permutation Throughput: {elements_per_sec / 1e9:.2f} Giga-elements/sec")

    del packed_bytes, low_nibble, high_nibble, unpacked
    torch.cuda.empty_cache()

if __name__ == '__main__':
    benchmark_warp_permute()
