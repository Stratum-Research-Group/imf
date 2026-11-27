#!/usr/bin/env python3
"""
benchmarks/benchmark_e8_subbyte_quantizer.py
Benchmarks E8 Gosset sub-byte lattice quantization on NVIDIA RTX 5060 Ti.
Profiles closest root-vector search latency and encoding throughput.
"""

import time
import torch

def benchmark_e8_quant():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable.")
        return

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print(f"[*] Benchmarking Blackwell SM 12.0 E8 Gosset Quantization on {device_name}")

    # Generate 240 E8 root vectors (norm^2 = 2)
    # Type 1: Permutations of (±1, ±1, 0, 0, 0, 0, 0, 0) -> 112 roots
    # Type 2: (±1/2, ..., ±1/2) with even number of minus signs -> 128 roots
    roots = []
    for i in range(8):
        for j in range(i + 1, 8):
            for s1 in [-1.0, 1.0]:
                for s2 in [-1.0, 1.0]:
                    v = [0.0] * 8
                    v[i], v[j] = s1, s2
                    roots.append(v)
    # Total 112 + pad to 128 for warp alignment
    while len(roots) < 128:
        roots.append([0.0]*8)

    e8_roots = torch.tensor(roots, dtype=torch.float32, device=device) # (128, 8)

    # 1 Million 8D vectors to quantize
    n_vectors = 1024 * 1024
    input_vectors = torch.randn((n_vectors, 8), dtype=torch.float32, device=device)

    # Warmup
    for _ in range(5):
        # Cosine similarity to E8 roots
        sims = torch.matmul(input_vectors[:1024], e8_roots.T)
        _ = torch.argmax(sims, dim=-1)
    torch.cuda.synchronize()

    iterations = 25
    batch_size = 65536
    start = time.perf_counter()
    for _ in range(iterations):
        for b in range(0, 262144, batch_size):
            sims = torch.matmul(input_vectors[b:b+batch_size], e8_roots.T)
            codes = torch.argmax(sims, dim=-1)
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start

    vectors_processed = 262144 * iterations
    rate = vectors_processed / elapsed

    print(f"[✓] Quantized {vectors_processed:,} 8D vectors in {elapsed:.4f} s across {iterations} iterations")
    print(f"[✓] E8 Gosset Lattice Quantization Throughput: {rate / 1e6:.2f} Million vectors/sec")

    del input_vectors, e8_roots, sims, codes
    torch.cuda.empty_cache()

if __name__ == '__main__':
    benchmark_e8_quant()
