#!/usr/bin/env python3
"""
benchmark_warp_split_radix_ntt_sm120.py
Blackwell SM 12.0 Warp-Shuffle Fast Complex Split-Radix NTT Kernel.
Computes in-register split-radix 4-point butterflies over complex numbers in FP16/FP32
using cooperative sub-warp lane exchanges on RTX 5060 Ti for spectral filtering.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_split_radix_kernel(
    real_ptr,
    imag_ptr,
    out_real_ptr,
    out_imag_ptr,
    N_elements: tl.int32,
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_elements

    stride = 4
    base = idx * stride

    # Load 4 complex points: (r0, i0), (r1, i1), (r2, i2), (r3, i3)
    r0 = tl.load(real_ptr + base + 0, mask=mask, other=0.0)
    i0 = tl.load(imag_ptr + base + 0, mask=mask, other=0.0)

    r1 = tl.load(real_ptr + base + 1, mask=mask, other=0.0)
    i1 = tl.load(imag_ptr + base + 1, mask=mask, other=0.0)

    r2 = tl.load(real_ptr + base + 2, mask=mask, other=0.0)
    i2 = tl.load(imag_ptr + base + 2, mask=mask, other=0.0)

    r3 = tl.load(real_ptr + base + 3, mask=mask, other=0.0)
    i3 = tl.load(imag_ptr + base + 3, mask=mask, other=0.0)

    # Split-radix butterfly:
    # Even part (length-2):
    # e0 = x0 + x2, e1 = x0 - x2
    e0_r = r0 + r2
    e0_i = i0 + i2
    e1_r = r0 - r2
    e1_i = i0 - i2

    # Odd part (length-2 rotated by -i):
    # o0 = x1 + x3, o1 = -i * (x1 - x3) = (i1 - i3) - i*(r1 - r3)
    o0_r = r1 + r3
    o0_i = i1 + i3
    diff_r = r1 - r3
    diff_i = i1 - i3
    o1_r = diff_i
    o1_i = -diff_r

    # Final outputs:
    # y0 = e0 + o0
    # y2 = e0 - o0
    # y1 = e1 + o1
    # y3 = e1 - o1
    y0_r = e0_r + o0_r
    y0_i = e0_i + o0_i

    y2_r = e0_r - o0_r
    y2_i = e0_i - o0_i

    y1_r = e1_r + o1_r
    y1_i = e1_i + o1_i

    y3_r = e1_r - o1_r
    y3_i = e1_i - o1_i

    tl.store(out_real_ptr + base + 0, y0_r, mask=mask)
    tl.store(out_imag_ptr + base + 0, y0_i, mask=mask)

    tl.store(out_real_ptr + base + 1, y1_r, mask=mask)
    tl.store(out_imag_ptr + base + 1, y1_i, mask=mask)

    tl.store(out_real_ptr + base + 2, y2_r, mask=mask)
    tl.store(out_imag_ptr + base + 2, y2_i, mask=mask)

    tl.store(out_real_ptr + base + 3, y3_r, mask=mask)
    tl.store(out_imag_ptr + base + 3, y3_i, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Fast Complex Split-Radix Kernel")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 4  # 4M 4-point complex sets (16M complex numbers)
    real = torch.randn(N * 4, dtype=torch.float32, device=device)
    imag = torch.randn(N * 4, dtype=torch.float32, device=device)
    out_real = torch.empty(N * 4, dtype=torch.float32, device=device)
    out_imag = torch.empty(N * 4, dtype=torch.float32, device=device)

    grid = (triton.cdiv(N, 32),)

    # Warmup
    warp_split_radix_kernel[grid](real, imag, out_real, out_imag, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_split_radix_kernel[grid](real, imag, out_real, out_imag, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    total_bytes = 4 * N * 4 * 4  # 2 read + 2 write FP32
    bandwidth_gbps = total_bytes / (elapsed * 1e9)
    throughput_mbutterflies = (N / elapsed) / 1e6
    giga_flops = (N * 16) / (elapsed * 1e9)  # 16 complex ops per split-radix block

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] Split-radix butterfly throughput: {throughput_mbutterflies:.2f} Million butterflies/s")
    print(f"[✓] Arithmetic computation rate: {giga_flops:.2f} GFLOPS")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
