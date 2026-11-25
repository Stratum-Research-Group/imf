"""
Physical Workstation Triton Kernel: Fused Sub-Bit E8 Gosset Lattice Dequantizer (Cycle 212)
Hardware Target: NVIDIA GeForce RTX 5060 Ti (AD106, SM 8.9), 16GB VRAM.

This kernel performs fused dequantization of weights compressed onto the E8 Gosset root lattice
(240 minimal vectors in R^8, requiring 8 bits per 8-dimensional weight block = 1.0 bit/weight,
plus 4 bits shared scale = 1.5 bits/weight effective).
In SRAM, each 8-bit index is dequantized into 8 FP16 values, scaled, and directly multiplied
against input activations in registers:
    Y = X * dequant(W_indices, scales)
eliminating DRAM round-trips for high-parameter (32B / 70B) local execution.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def fused_e8_dequant_gemv_kernel(
    X_ptr,          # [K] input activation vector FP16
    W_idx_ptr,      # [N, K // 8] uint8 indices into E8 codebook
    Scales_ptr,     # [N, K // 32] fp16 scales
    E8_Roots_ptr,   # [240, 8] fp16 table of Gosset E8 root vectors
    Out_ptr,        # [N] output activation vector FP16
    N: tl.constexpr,
    K: tl.constexpr,
    BLOCK_N: tl.constexpr,
    BLOCK_K: tl.constexpr, # Must be multiple of 8
):
    pid = tl.program_id(0)
    n_offset = pid * BLOCK_N + tl.arange(0, BLOCK_N)
    n_mask = n_offset < N

    acc = tl.zeros([BLOCK_N], dtype=tl.float32)

    # Loop over K dimension in chunks of BLOCK_K
    for k_start in range(0, K, BLOCK_K):
        for g in range(0, BLOCK_K // 8):
            k_base = k_start + g * 8
            k_idx = k_base + tl.arange(0, 8)
            k_mask = k_idx < K

            # Load 8 elements of X
            x_vals = tl.load(X_ptr + k_idx, mask=k_mask, other=0.0) # [8]

            # Load uint8 E8 codebook index for each row in BLOCK_N and convert explicitly to int32
            idx_offset = n_offset * (K // 8) + (k_base // 8)
            code_idx = tl.load(W_idx_ptr + idx_offset, mask=n_mask, other=0).to(tl.int32) # [BLOCK_N]

            # Load scale for this group (1 scale per 32 weights)
            scale_offset = n_offset * (K // 32) + (k_base // 32)
            scale = tl.load(Scales_ptr + scale_offset, mask=n_mask, other=1.0) # [BLOCK_N]

            # Load the corresponding 8D E8 root vector from codebook for each row
            roots = tl.load(E8_Roots_ptr + code_idx[:, None] * 8 + tl.arange(0, 8)[None, :]) # [BLOCK_N, 8]

            # Dequantized weights = roots * scale
            w_vals = roots * scale[:, None] # [BLOCK_N, 8]

            # Dot product: sum across 8 dimensions
            acc += tl.sum(w_vals.to(tl.float32) * x_vals[None, :].to(tl.float32), axis=1)

    tl.store(Out_ptr + n_offset, acc.to(tl.float16), mask=n_mask)


def run_benchmark():
    assert torch.cuda.is_available(), "Physical workstation GPU required"
    device = torch.device("cuda:0")

    # Dimensions representing a single projection layer in a 14B/32B model:
    # N = 4096 (out features), K = 4096 (in features)
    N, K = 4096, 4096

    # Construct the canonical E8 Gosset root vectors (240 roots in R^8)
    roots = []
    # 1) +/- e_i +/- e_j (112 roots)
    for i in range(8):
        for j in range(i + 1, 8):
            for s1 in [-1.0, 1.0]:
                for s2 in [-1.0, 1.0]:
                    v = [0.0] * 8
                    v[i] = s1
                    v[j] = s2
                    roots.append(v)
    # 2) 1/2 (+/- 1, ..., +/- 1) with even sum of minuses (128 roots)
    for bits in range(256):
        signs = [(1.0 if (bits & (1 << b)) else -1.0) for b in range(8)]
        if signs.count(-1.0) % 2 == 0:
            roots.append([0.5 * s for s in signs])
    roots = torch.tensor(roots[:240], device=device, dtype=torch.float16)
    assert roots.shape == (240, 8), f"Expected (240, 8), got {roots.shape}"

    torch.manual_seed(42)
    x = torch.randn(K, device=device, dtype=torch.float16)
    w_idx = torch.randint(0, 240, (N, K // 8), device=device, dtype=torch.uint8)
    scales = torch.randn(N, K // 32, device=device, dtype=torch.float16) * 0.1

    # PyTorch reference
    def ref_dequant(x, w_idx, scales, roots):
        w_roots = roots[w_idx.long()] # [N, K // 8, 8]
        w_reshaped = w_roots.view(N, K // 32, 4, 8)
        w_scaled = w_reshaped * scales.unsqueeze(-1).unsqueeze(-1)
        w_matrix = w_scaled.view(N, K)
        return torch.matmul(w_matrix, x)

    # Warmup reference
    for _ in range(10):
        ref_out = ref_dequant(x, w_idx, scales, roots)
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    iters = 50
    for _ in range(iters):
        ref_out = ref_dequant(x, w_idx, scales, roots)
    torch.cuda.synchronize()
    ref_time = (time.perf_counter() - t0) / iters

    out = torch.empty(N, device=device, dtype=torch.float16)
    BLOCK_N = 64
    BLOCK_K = 64
    grid = ((N + BLOCK_N - 1) // BLOCK_N,)

    # Warmup Triton
    for _ in range(10):
        fused_e8_dequant_gemv_kernel[grid](
            x, w_idx, scales, roots, out, N, K, BLOCK_N, BLOCK_K
        )
    torch.cuda.synchronize()

    t0 = time.perf_counter()
    for _ in range(iters):
        fused_e8_dequant_gemv_kernel[grid](
            x, w_idx, scales, roots, out, N, K, BLOCK_N, BLOCK_K
        )
    torch.cuda.synchronize()
    triton_time = (time.perf_counter() - t0) / iters

    max_err = torch.max(torch.abs(out.float() - ref_out.float())).item()
    speedup = ref_time / triton_time
    total_weights = N * K
    throughput = (total_weights) / triton_time / 1e9 # Giga weights/s
    compressed_bytes = (N * (K // 8)) + (N * (K // 32) * 2) # 1 byte per 8 weights + 2 bytes per 32 weights
    raw_bytes = N * K * 2
    compression_ratio = raw_bytes / compressed_bytes

    print(f"=== Workstation Benchmark: Cycle 212 Fused Sub-Bit E8 Gosset Dequantizer ===")
    print(f"Hardware: {torch.cuda.get_device_name(0)}")
    print(f"Matrix: N={N}, K={K} ({total_weights/1e6:.2f}M weights)")
    print(f"Effective Bitrate: {compressed_bytes * 8 / total_weights:.2f} bits/weight (Compression Ratio: {compression_ratio:.2f}x)")
    print(f"PyTorch baseline latency: {ref_time*1e6:.2f} us")
    print(f"Triton fused latency:     {triton_time*1e6:.2f} us")
    print(f"Speedup factor:           {speedup:.2f}x")
    print(f"Dequant Throughput:       {throughput:.2f} Giga weights/s")
    print(f"Max Absolute Error:       {max_err:.2e}")
    assert max_err < 5e-2, f"Tolerance exceeded: {max_err}"
    print("PHYSICAL HARDWARE TEST PASSED")

if __name__ == "__main__":
    run_benchmark()
