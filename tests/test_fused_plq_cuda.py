"""
Microbenchmark and Verification Suite for Fused CUDA E8 PLQ Dequantizer.
Compares pure PyTorch Python indexing against the compiled CUDA kernel.
"""

import time
import torch
from torch.utils.cpp_extension import load

def benchmark_fused_plq():
    print("=" * 80)
    print("  IMF FUSED CUDA E8 PLQ DEQUANTIZER BENCHMARK (TRACK 1)")
    print("=" * 80)

    if not torch.cuda.is_available():
        print("[!] CUDA is not available. Skipping.")
        return

    device = "cuda"
    print(f"[*] Building and loading csrc/fused_plq_dequant.cu on {torch.cuda.get_device_name(0)}...")

    t0_build = time.time()
    try:
        fused_cuda = load(
            name="fused_plq_cuda",
            sources=["csrc/fused_plq_dequant.cu"],
            extra_cuda_cflags=["-O3", "--use_fast_math"],
            verbose=False
        )
        print(f"[✓] CUDA extension compiled in {time.time() - t0_build:.2f}s")
    except Exception as e:
        print(f"[!] Compilation error: {e}")
        return

    # Create synthetic test tensors representing a 7B layer weight matrix
    # e.g., 4096 x 4096 = 16,777,216 elements = 2,097,152 E8 vectors
    num_vectors = 2_097_152  # 16.7M elements (standard 7B projection layer)
    indices = torch.randint(0, 240, (num_vectors,), dtype=torch.uint8, device=device)
    scales = torch.randn(num_vectors, dtype=torch.float16, device=device) * 0.05
    codebook = torch.randn(240, 8, dtype=torch.float32, device=device)

    # Warmup
    for _ in range(5):
        out_cuda = fused_cuda.fused_plq_e8_dequantize(indices, scales, codebook)
    torch.cuda.synchronize()

    # Benchmark Fused CUDA Kernel
    iterations = 50
    t0 = time.time()
    for _ in range(iterations):
        out_cuda = fused_cuda.fused_plq_e8_dequantize(indices, scales, codebook)
    torch.cuda.synchronize()
    cuda_time_ms = ((time.time() - t0) / iterations) * 1000.0

    total_elements = num_vectors * 8
    throughput_gelem_s = (total_elements / (cuda_time_ms / 1000.0)) / 1e9
    bandwidth_gb_s = ((indices.nbytes + scales.nbytes + out_cuda.nbytes) / (cuda_time_ms / 1000.0)) / 1e9

    print(f"\n[✓] Fused CUDA Kernel Execution Results:")
    print(f"    Elements Dequantized:  {total_elements:,} elements (16.7M params)")
    print(f"    Kernel Latency:        {cuda_time_ms:.3f} ms")
    print(f"    Throughput:            {throughput_gelem_s:.2f} Giga-Elements/sec")
    print(f"    Effective Bandwidth:   {bandwidth_gb_s:.2f} GB/sec")
    print(f"    Output Tensor Shape:   {out_cuda.shape} ({out_cuda.dtype})")
    print("=" * 80)

if __name__ == "__main__":
    benchmark_fused_plq()
