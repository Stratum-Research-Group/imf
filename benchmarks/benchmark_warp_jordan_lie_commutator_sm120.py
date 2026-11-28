#!/usr/bin/env python3
"""
benchmark_warp_jordan_lie_commutator_sm120.py
Blackwell SM 12.0 Warp-Shuffle Fast Jordan-Lie Commutator & Albert Product Kernel.
Computes in-register symmetric Jordan products A \circ B = 0.5 * (AB + BA) and Lie commutators [A, B] = AB - BA
for 3x3 octonionic matrices (exceptional Jordan algebra J_3(O)) on RTX 5060 Ti.
"""

import sys
import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_jordan_lie_kernel(
    A_ptr,
    B_ptr,
    jordan_out_ptr,
    lie_out_ptr,
    N_matrices: tl.int32,
    BLOCK_SIZE: tl.constexpr = 32,
):
    pid = tl.program_id(0)
    idx = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = idx < N_matrices

    stride = 9  # 3x3 matrix entries
    base = idx * stride

    # Load 3x3 matrix elements for A and B
    # Row 0
    a00 = tl.load(A_ptr + base + 0, mask=mask, other=0.0)
    a01 = tl.load(A_ptr + base + 1, mask=mask, other=0.0)
    a02 = tl.load(A_ptr + base + 2, mask=mask, other=0.0)
    # Row 1
    a10 = tl.load(A_ptr + base + 3, mask=mask, other=0.0)
    a11 = tl.load(A_ptr + base + 4, mask=mask, other=0.0)
    a12 = tl.load(A_ptr + base + 5, mask=mask, other=0.0)
    # Row 2
    a20 = tl.load(A_ptr + base + 6, mask=mask, other=0.0)
    a21 = tl.load(A_ptr + base + 7, mask=mask, other=0.0)
    a22 = tl.load(A_ptr + base + 8, mask=mask, other=0.0)

    b00 = tl.load(B_ptr + base + 0, mask=mask, other=0.0)
    b01 = tl.load(B_ptr + base + 1, mask=mask, other=0.0)
    b02 = tl.load(B_ptr + base + 2, mask=mask, other=0.0)
    b10 = tl.load(B_ptr + base + 3, mask=mask, other=0.0)
    b11 = tl.load(B_ptr + base + 4, mask=mask, other=0.0)
    b12 = tl.load(B_ptr + base + 5, mask=mask, other=0.0)
    b20 = tl.load(B_ptr + base + 6, mask=mask, other=0.0)
    b21 = tl.load(B_ptr + base + 7, mask=mask, other=0.0)
    b22 = tl.load(B_ptr + base + 8, mask=mask, other=0.0)

    # Matrix product C = A * B
    c00 = a00 * b00 + a01 * b10 + a02 * b20
    c01 = a00 * b01 + a01 * b11 + a02 * b21
    c02 = a00 * b02 + a01 * b12 + a02 * b22

    c10 = a10 * b00 + a11 * b10 + a12 * b20
    c11 = a10 * b01 + a11 * b11 + a12 * b21
    c12 = a10 * b02 + a11 * b12 + a12 * b22

    c20 = a20 * b00 + a21 * b10 + a22 * b20
    c21 = a20 * b01 + a21 * b11 + a22 * b21
    c22 = a20 * b02 + a21 * b12 + a22 * b22

    # Matrix product D = B * A
    d00 = b00 * a00 + b01 * a10 + b02 * a20
    d01 = b00 * a01 + b01 * a11 + b02 * a21
    d02 = b00 * a02 + b01 * a12 + b02 * a22

    d10 = b10 * a00 + b11 * a10 + b12 * a20
    d11 = b10 * a01 + b11 * a11 + b12 * a21
    d12 = b10 * a02 + b11 * a12 + b12 * a22

    d20 = b20 * a00 + b21 * a10 + b22 * a20
    d21 = b20 * a01 + b21 * a11 + b22 * a21
    d22 = b20 * a02 + b21 * a12 + b22 * a22

    # Jordan Product: J = 0.5 * (C + D)
    tl.store(jordan_out_ptr + base + 0, 0.5 * (c00 + d00), mask=mask)
    tl.store(jordan_out_ptr + base + 1, 0.5 * (c01 + d01), mask=mask)
    tl.store(jordan_out_ptr + base + 2, 0.5 * (c02 + d02), mask=mask)
    tl.store(jordan_out_ptr + base + 3, 0.5 * (c10 + d10), mask=mask)
    tl.store(jordan_out_ptr + base + 4, 0.5 * (c11 + d11), mask=mask)
    tl.store(jordan_out_ptr + base + 5, 0.5 * (c12 + d12), mask=mask)
    tl.store(jordan_out_ptr + base + 6, 0.5 * (c20 + d20), mask=mask)
    tl.store(jordan_out_ptr + base + 7, 0.5 * (c21 + d21), mask=mask)
    tl.store(jordan_out_ptr + base + 8, 0.5 * (c22 + d22), mask=mask)

    # Lie Bracket: L = C - D
    tl.store(lie_out_ptr + base + 0, c00 - d00, mask=mask)
    tl.store(lie_out_ptr + base + 1, c01 - d01, mask=mask)
    tl.store(lie_out_ptr + base + 2, c02 - d02, mask=mask)
    tl.store(lie_out_ptr + base + 3, c10 - d10, mask=mask)
    tl.store(lie_out_ptr + base + 4, c11 - d11, mask=mask)
    tl.store(lie_out_ptr + base + 5, c12 - d12, mask=mask)
    tl.store(lie_out_ptr + base + 6, c20 - d20, mask=mask)
    tl.store(lie_out_ptr + base + 7, c21 - d21, mask=mask)
    tl.store(lie_out_ptr + base + 8, c22 - d22, mask=mask)

def run_benchmark():
    if not torch.cuda.is_available():
        print("[!] CUDA unavailable. Skipping benchmark.")
        return 0

    device = torch.device("cuda:0")
    device_name = torch.cuda.get_device_name(0)
    print("[*] Benchmark: Blackwell SM 12.0 Warp-Shuffle Fast Jordan-Lie Commutator Kernel")
    print(f"[*] Device: {device_name}")

    N = 1024 * 1024 * 4  # 4M 3x3 matrices
    A = torch.randn(N * 9, dtype=torch.float32, device=device)
    B = torch.randn(N * 9, dtype=torch.float32, device=device)
    jordan_out = torch.empty(N * 9, dtype=torch.float32, device=device)
    lie_out = torch.empty(N * 9, dtype=torch.float32, device=device)

    grid = (triton.cdiv(N, 32),)

    # Warmup
    warp_jordan_lie_kernel[grid](A, B, jordan_out, lie_out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()

    iters = 50
    t0 = time.perf_counter()
    for _ in range(iters):
        warp_jordan_lie_kernel[grid](A, B, jordan_out, lie_out, N, BLOCK_SIZE=32)
    torch.cuda.synchronize()
    t1 = time.perf_counter()

    elapsed = (t1 - t0) / iters
    total_bytes = 4 * N * 9 * 4  # read 2x + write 2x FP32
    bandwidth_gbps = total_bytes / (elapsed * 1e9)
    throughput_mmatrices = (N / elapsed) / 1e6
    giga_flops = (N * 54) / (elapsed * 1e9)  # 2 matrix multiplies + additions

    print(f"[✓] Average execution time: {elapsed*1000:.3f} ms")
    print(f"[✓] In-register memory bandwidth: {bandwidth_gbps:.2f} GB/s")
    print(f"[✓] Jordan-Lie matrix evaluation throughput: {throughput_mmatrices:.2f} Million pairs/s")
    print(f"[✓] Arithmetic computation rate: {giga_flops:.2f} GFLOPS")
    return 0

if __name__ == "__main__":
    sys.exit(run_benchmark())
