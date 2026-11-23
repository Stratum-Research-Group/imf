"""
Benchmark for 24-Dimensional Leech Lattice CUDA Dequantizer (Track 2).
"""

import time
import torch
from torch.utils.cpp_extension import load

def benchmark_leech24():
    print("=" * 80)
    print("  IMF FUSED CUDA LEECH 24D PLQ DEQUANTIZER BENCHMARK (TRACK 2)")
    print("=" * 80)

    if not torch.cuda.is_available():
        print("[!] CUDA not available.")
        return

    device = "cuda"
    print(f"[*] Compiling csrc/fused_leech24_dequant.cu on {torch.cuda.get_device_name(0)}...")

    t0_build = time.time()
    try:
        leech_cuda = load(
            name="fused_leech24_cuda",
            sources=["csrc/fused_leech24_dequant.cu"],
            extra_cuda_cflags=["-O3", "--use_fast_math"],
            verbose=False
        )
        print(f"[✓] CUDA extension compiled in {time.time() - t0_build:.2f}s")
    except Exception as e:
        print(f"[!] Compilation error: {e}")
        return

    # Simulate 100B expert layer: 699,050 vectors of dimension 24 = ~16.7M params
    num_vectors = 699_050
    indices = torch.randint(0, 684, (num_vectors,), dtype=torch.int16, device=device)
    scales = torch.randn(num_vectors, dtype=torch.float16, device=device) * 0.05
    codebook = torch.randn(684, 24, dtype=torch.float32, device=device)

    # Warmup
    for _ in range(5):
        out = leech_cuda.fused_leech24_dequantize(indices, scales, codebook)
    torch.cuda.synchronize()

    iterations = 50
    t0 = time.time()
    for _ in range(iterations):
        out = leech_cuda.fused_leech24_dequantize(indices, scales, codebook)
    torch.cuda.synchronize()
    latency_ms = ((time.time() - t0) / iterations) * 1000.0

    total_elements = num_vectors * 24
    gelem_s = (total_elements / (latency_ms / 1000.0)) / 1e9
    bw_gb_s = ((indices.nbytes + scales.nbytes + out.nbytes) / (latency_ms / 1000.0)) / 1e9

    print(f"\n[✓] Fused Leech-24 CUDA Kernel Results:")
    print(f"    Elements Dequantized:  {total_elements:,} elements (16.7M params)")
    print(f"    Kernel Latency:        {latency_ms:.3f} ms")
    print(f"    Throughput:            {gelem_s:.2f} Giga-Elements/sec")
    print(f"    Effective Bandwidth:   {bw_gb_s:.2f} GB/sec")
    print(f"    Output Tensor Shape:   {out.shape}")
    print("=" * 80)

if __name__ == "__main__":
    benchmark_leech24()
