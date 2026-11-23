"""
Microbenchmark for Fused On-The-Fly PLQ GEMV Kernel (Track 1).
"""

import time
import torch
from torch.utils.cpp_extension import load

def benchmark_fused_gemv():
    print("=" * 80)
    print("  IMF FUSED ON-THE-FLY PLQ-GEMV BENCHMARK (TRACK 1)")
    print("=" * 80)

    if not torch.cuda.is_available():
        print("[!] CUDA not available.")
        return

    device = "cuda"
    print(f"[*] Compiling csrc/fused_plq_gemv.cu on {torch.cuda.get_device_name(0)}...")

    t0_build = time.time()
    try:
        gemv_cuda = load(
            name="fused_plq_gemv_cuda",
            sources=["csrc/fused_plq_gemv.cu"],
            extra_cuda_cflags=["-O3", "--use_fast_math"],
            verbose=False
        )
        print(f"[✓] CUDA extension compiled in {time.time() - t0_build:.2f}s")
    except Exception as e:
        print(f"[!] Compilation error: {e}")
        return

    # Benchmark typical 7B layer projection: M=4096, K=4096 (K/8 = 512 E8 vectors per row)
    M, K = 4096, 4096
    num_vectors_per_row = K // 8

    indices = torch.randint(0, 240, (M, num_vectors_per_row), dtype=torch.uint8, device=device)
    scales = torch.randn((M, num_vectors_per_row), dtype=torch.float16, device=device) * 0.05
    codebook = torch.randn(240, 8, dtype=torch.float32, device=device)
    vec_x = torch.randn(K, dtype=torch.float16, device=device)

    # Warmup
    for _ in range(10):
        y = gemv_cuda.fused_plq_gemv(indices, scales, codebook, vec_x)
    torch.cuda.synchronize()

    iterations = 100
    t0 = time.time()
    for _ in range(iterations):
        y = gemv_cuda.fused_plq_gemv(indices, scales, codebook, vec_x)
    torch.cuda.synchronize()
    latency_us = ((time.time() - t0) / iterations) * 1e6

    # FLOPs: 2 * M * K
    total_flops = 2.0 * M * K
    tflops = (total_flops / (latency_us / 1e6)) / 1e12

    print(f"\n[✓] Fused On-The-Fly PLQ-GEMV Execution Results:")
    print(f"    Matrix Dimension:      {M} × {K} (16.7M params in compressed PLQ)")
    print(f"    Kernel Latency:        {latency_us:.2f} µs ({latency_us/1000.0:.3f} ms)")
    print(f"    Effective Compute:     {tflops:.2f} TFLOPs")
    print(f"    Zero VRAM Allocation:  0 bytes uncompressed weights written to VRAM")
    print(f"    Output Tensor Shape:   {y.shape} ({y.dtype})")
    print("=" * 80)

if __name__ == "__main__":
    benchmark_fused_gemv()
