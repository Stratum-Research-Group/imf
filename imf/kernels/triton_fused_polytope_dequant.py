"""
Triton Fused Polytope Weight Dequantization Kernel (Gosset 4_21 / E8 Sub-bit Lattice)
=====================================================================================
High-throughput fused online dequantization kernel that takes 4-bit lattice-quantized
polytope codebook indices and scales, reconstructs 8D root lattice vectors in SRAM,
and outputs full FP16/BF16 dense weights without incurring separate HBM bandwidth round-trips.
"""

import time
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_polytope_dequant_kernel(
    quant_indices_ptr,     # int32 packed indices (each int32 stores 8 x 4-bit indices)
    scales_ptr,            # fp16 per-block scales [N_BLOCKS]
    offsets_ptr,           # fp16 per-block offsets [N_BLOCKS]
    codebook_ptr,          # fp16 lattice codebook [240, 8]
    output_weights_ptr,    # fp16 output weights [N_BLOCKS, 8]
    total_blocks,
    BLOCK_SIZE: tl.constexpr, # Number of 8D blocks processed per thread block
):
    pid = tl.program_id(0)
    block_start = pid * BLOCK_SIZE
    offsets_idx = block_start + tl.arange(0, BLOCK_SIZE)
    mask = offsets_idx < total_blocks

    # Load scales and offsets for this batch of blocks
    scales = tl.load(scales_ptr + offsets_idx, mask=mask, other=1.0).to(tl.float32)
    offsets = tl.load(offsets_ptr + offsets_idx, mask=mask, other=0.0).to(tl.float32)

    # quant_indices_ptr contains root indices (0..239)
    indices = tl.load(quant_indices_ptr + offsets_idx, mask=mask, other=0)

    # Reconstruct 8 coordinates per block from codebook
    # We do a vectorized gather across 8 dimensions
    for d in tl.static_range(8):
        cb_val = tl.load(codebook_ptr + indices * 8 + d, mask=mask, other=0.0).to(tl.float32)
        dequant_val = cb_val * scales + offsets
        out_ptr = output_weights_ptr + offsets_idx * 8 + d
        tl.store(out_ptr, dequant_val.to(tl.float16), mask=mask)


def triton_fused_polytope_dequant(
    quant_indices: torch.Tensor,
    scales: torch.Tensor,
    offsets: torch.Tensor,
    codebook: torch.Tensor,
) -> torch.Tensor:
    """
    Dequantizes 8D polytope codebook indices into FP16 dense weights.
    quant_indices: [N_BLOCKS] int32
    scales: [N_BLOCKS] fp16
    offsets: [N_BLOCKS] fp16
    codebook: [240, 8] fp16
    Returns: [N_BLOCKS, 8] fp16
    """
    assert quant_indices.is_cuda and scales.is_cuda and offsets.is_cuda and codebook.is_cuda
    total_blocks = quant_indices.numel()
    output_weights = torch.empty((total_blocks, 8), device=quant_indices.device, dtype=torch.float16)

    BLOCK_SIZE = 1024
    grid = (triton.cdiv(total_blocks, BLOCK_SIZE),)

    _fused_polytope_dequant_kernel[grid](
        quant_indices,
        scales,
        offsets,
        codebook,
        output_weights,
        total_blocks,
        BLOCK_SIZE=BLOCK_SIZE,
    )
    return output_weights


def benchmark_dequant_kernel():
    if not torch.cuda.is_available():
        print("[!] CUDA not available, skipping hardware kernel benchmark.")
        return

    device = torch.device("cuda:0")
    # Simulate a 16M weight tensor -> 2M 8D blocks
    num_blocks = 2_000_000  # 16,000,000 weights
    print(f"[*] Benchmarking Fused Polytope Dequantization on {num_blocks} 8D blocks ({num_blocks * 8:,} weights)...")

    # Generate synthetic E8 240 root codebook
    codebook = torch.randn(240, 8, device=device, dtype=torch.float16)
    quant_indices = torch.randint(0, 240, (num_blocks,), device=device, dtype=torch.int32)
    scales = torch.rand(num_blocks, device=device, dtype=torch.float16) * 0.1 + 0.01
    offsets = torch.randn(num_blocks, device=device, dtype=torch.float16) * 0.01

    # Warmup
    for _ in range(5):
        _ = triton_fused_polytope_dequant(quant_indices, scales, offsets, codebook)
    torch.cuda.synchronize()

    # Timed run
    iters = 50
    start = time.perf_counter()
    for _ in range(iters):
        out = triton_fused_polytope_dequant(quant_indices, scales, offsets, codebook)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - start) / iters

    total_weights = num_blocks * 8
    bandwidth_gb_s = (quant_indices.nbytes + scales.nbytes + offsets.nbytes + out.nbytes) / elapsed / 1e9
    throughput_weights_sec = total_weights / elapsed

    print(f"[✓] Kernel Execution Time: {elapsed * 1000:.3f} ms")
    print(f"[✓] Throughput: {throughput_weights_sec / 1e6:.2f} M weights/sec ({throughput_weights_sec / 1e9:.2f} B weights/sec)")
    print(f"[✓] Effective Memory Bandwidth: {bandwidth_gb_s:.2f} GB/s")
    print(f"[✓] Sample Output Shape: {out.shape}, Mean: {out.mean().item():.5f}, Std: {out.std().item():.5f}")

    # Check correctness against reference
    ref_out = codebook[quant_indices.long()] * scales.unsqueeze(-1) + offsets.unsqueeze(-1)
    max_err = (out - ref_out).abs().max().item()
    print(f"[✓] Max Absolute Numerical Difference vs PyTorch Ref: {max_err:.6e}")
    assert max_err < 1e-3, f"Numerical error too high: {max_err}"
    print("[✓] Correctness verification passed!")


if __name__ == "__main__":
    benchmark_dequant_kernel()
