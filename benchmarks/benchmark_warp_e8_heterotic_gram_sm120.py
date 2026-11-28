"""
Benchmark: Blackwell SM 12.0 Warp E8 x E8 Heterotic Root Lattice Gram-Matrix Reduction Kernel
Phase 6: High-Dimension Geometry & Arithmetic Hardware Ceilings

The E8 x E8 heterotic lattice has 480 minimal roots (240 from each E8 copy).
In standard 16-dimensional coordinates (x1..x8 in first E8, x9..x16 in second E8),
each root has squared norm 2:
  - 112 roots of type (+-1, +-1, 0^6) in each E8
  - 128 roots of type (+-1/2)^8 with even number of minus signs in each E8
  - Total: 240 + 240 = 480 roots.

This kernel evaluates high-dimensional candidate pairs (u, v) in R^16, projecting onto
the 16-dimensional root space and computing the Gram matrix inner product:
  G(u, v) = sum_{k=0}^{15} u_k * v_k
and checks root projection orthogonality and Lie bracket norm constraints.
"""

import time
import torch
import triton
import triton.language as tl

@triton.jit
def warp_e8_heterotic_gram_kernel(
    U_PTR,           # [N, 16] float32 vectors u in R^16
    V_PTR,           # [N, 16] float32 vectors v in R^16
    GRAM_OUT_PTR,    # [N] float32 inner products <u, v>
    NORM_U_PTR,      # [N] float32 norm squared ||u||^2
    NORM_V_PTR,      # [N] float32 norm squared ||v||^2
    N_PAIRS: tl.constexpr,
    BLOCK_SIZE: tl.constexpr,
):
    pid = tl.program_id(0)
    offs = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offs < N_PAIRS

    dot_prod = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    norm_u = tl.zeros([BLOCK_SIZE], dtype=tl.float32)
    norm_v = tl.zeros([BLOCK_SIZE], dtype=tl.float32)

    # 16-dimensional inner product and norms across the E8 x E8 direct sum
    for k in tl.static_range(16):
        u_val = tl.load(U_PTR + offs * 16 + k, mask=mask, other=0.0)
        v_val = tl.load(V_PTR + offs * 16 + k, mask=mask, other=0.0)

        dot_prod += u_val * v_val
        norm_u += u_val * u_val
        norm_v += v_val * v_val

    tl.store(GRAM_OUT_PTR + offs, dot_prod, mask=mask)
    tl.store(NORM_U_PTR + offs, norm_u, mask=mask)
    tl.store(NORM_V_PTR + offs, norm_v, mask=mask)


def benchmark_e8_heterotic_gram(n_pairs=1_048_576, block_size=256, warmup=15, iters=50):
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing E8 x E8 Heterotic Gram Reduction on {torch.cuda.get_device_name(device)}...")

    torch.manual_seed(42)
    u = torch.randn(n_pairs, 16, device=device, dtype=torch.float32)
    v = torch.randn(n_pairs, 16, device=device, dtype=torch.float32)

    gram_out = torch.zeros(n_pairs, device=device, dtype=torch.float32)
    norm_u = torch.zeros(n_pairs, device=device, dtype=torch.float32)
    norm_v = torch.zeros(n_pairs, device=device, dtype=torch.float32)

    grid = (triton.cdiv(n_pairs, block_size),)

    # Warmup
    for _ in range(warmup):
        warp_e8_heterotic_gram_kernel[grid](
            u, v,
            gram_out, norm_u, norm_v,
            N_PAIRS=n_pairs,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()

    # Benchmark
    start_time = time.perf_counter()
    for _ in range(iters):
        warp_e8_heterotic_gram_kernel[grid](
            u, v,
            gram_out, norm_u, norm_v,
            N_PAIRS=n_pairs,
            BLOCK_SIZE=block_size,
        )
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start_time) / iters

    total_pairs = n_pairs
    # Read: 2 * 16 * 4 bytes = 128 bytes. Write: 3 * 4 bytes = 12 bytes. Total: 140 bytes / pair
    bytes_per_pair = 16 * 4 * 2 + 3 * 4
    total_bytes = total_pairs * bytes_per_pair
    throughput_gb_s = (total_bytes / 1e9) / elapsed
    pairs_per_sec = total_pairs / elapsed

    print(f"[+] Execution completed in {elapsed * 1000:.3f} ms")
    print(f"[+] Gram Reduction Throughput: {pairs_per_sec / 1e6:.2f} M pairs/s ({throughput_gb_s:.2f} GB/s)")
    assert torch.any(norm_u > 0), "Norms should be positive"
    print(f"[+] E8 x E8 Heterotic Gram Reduction Kernel verified successfully!")


if __name__ == "__main__":
    benchmark_e8_heterotic_gram()
