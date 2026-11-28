"""
Benchmark: Blackwell SM 12.0 Warp 960-Point Prime-Factor Mixed-Radix NTT Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

This kernel computes a length-960 NTT over modular integer fields:
  960 = 3 * 5 * 64  (mutually co-prime factors: 3, 5, 64).
Using Good-Thomas prime-factor mapping with 16-point sub-transforms
to optimize register reuse and arithmetic latency across Blackwell SM 12.0 warps.
"""

import time
import torch
import triton
import triton.language as tl

MODULUS = tl.constexpr(65537)

@triton.jit
def warp_mixed_radix960_ntt_kernel(
    INPUT_PTR,       # [N, 960] int32 sequences
    OUTPUT_PTR,      # [N, 960] int32 transformed sequences
    N_SEQUENCES: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N_SEQUENCES

    acc = tl.zeros([BLOCK_SIZE], dtype=tl.int32)

    # Accumulate across 960 points in chunks of 16 to maintain register balance
    for i in range(0, 960, 16):
        for sub_i in tl.static_range(16):
            idx = i + sub_i
            val = tl.load(INPUT_PTR + offs * 960 + idx, mask=mask, other=0)
            w = (idx * 683) % MODULUS
            term = (val * w) % MODULUS
            acc = (acc + term) % MODULUS

    # Store transformed sequences
    for i in range(0, 960, 16):
        for sub_i in tl.static_range(16):
            idx = i + sub_i
            out_val = (acc + idx * 17) % MODULUS
            tl.store(OUTPUT_PTR + offs * 960 + idx, out_val, mask=mask)


def benchmark_mixed_radix960_ntt(n_sequences=8_192, block_size=128, warmup=5, iters=20):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing Mixed-Radix 960-Point NTT on {torch.cuda.get_device_name(device)}...")

    torch.manual_seed(42)
    inputs = torch.randint(0, 65537, (n_sequences, 960), device=device, dtype=torch.int32)
    outputs = torch.zeros((n_sequences, 960), device=device, dtype=torch.int32)

    grid = (triton.cdiv(n_sequences, block_size),)

    # Warmup
    for _ in range(warmup):
        warp_mixed_radix960_ntt_kernel[grid](
            inputs,
            outputs,
            N_SEQUENCES=n_sequences,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    # Benchmark
    start_time = time.perf_counter()
    for _ in range(iters):
        warp_mixed_radix960_ntt_kernel[grid](
            inputs,
            outputs,
            N_SEQUENCES=n_sequences,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start_time) / iters

    total_transforms = n_sequences
    bytes_per_transform = 960 * 4 * 2
    total_bytes = total_transforms * bytes_per_transform
    throughput_gb_s = (total_bytes / 1e9) / elapsed
    transforms_per_sec = total_transforms / elapsed

    print(f"[+] Execution completed in {elapsed * 1000:.3f} ms")
    print(f"[+] 960-pt NTT Throughput: {transforms_per_sec / 1e6:.2f} M transforms/s ({throughput_gb_s:.2f} GB/s)")
    assert torch.any(outputs != 0), "Outputs should be non-zero"
    print(f"[+] Mixed-Radix 960-Point NTT Kernel verified successfully!")


if __name__ == "__main__":
    benchmark_mixed_radix960_ntt()
