"""
imf/triton_e8_kernel.py
=======================
Triton Fused E8 Gosset (8D) Polytope Root Dequantization GEMV Kernel.

Fuses 8D E8 root codebook lookup, scale factor multiplication, and dot-product accumulation
directly inside GPU registers and SRAM (Shared Memory), avoiding materialization of
intermediate uncompressed FP16/FP32 weights in global HBM.

Mathematical Formulation:
y_i = sum_j x_j * W_{i, j}
Where W_{i, 8*b : 8*(b+1)} = scale_b * (E8Roots[index_{i, b}] / sqrt(2))

Effective Bits / Weight: 8 / 8 = 1.00 bpw (+ 0.25 bpw scale = 1.25 bpw).
Minimal root norm: ||v|| = sqrt(2) = 1.41421356f.
"""

import math
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_e8_gemv_kernel(
    X_ptr,          # Pointer to input vector x [1, K]
    Indices_ptr,    # Pointer to root indices [M, K // 8] (uint8 or int32)
    Scales_ptr,     # Pointer to scales [M, K // BLOCK_SCALE] (float16)
    Roots_ptr,      # Pointer to E8 240-root codebook [240, 8] (float32)
    Out_ptr,        # Pointer to output vector y [1, M] (float16)
    M, K,           # Dimensions: M = out_features, K = in_features
    stride_xm, stride_xk,
    stride_im, stride_ik,
    stride_sm, stride_sk,
    stride_rm, stride_rk,
    stride_om, stride_on,
    BLOCK_SCALE: tl.constexpr,
):
    """
    Computes 1xK @ KxM -> 1xM with fused E8 Gosset register dequantization.
    Each program block handles 1 row of output m.
    """
    m = tl.program_id(0)
    if m >= M:
        return

    # Accumulator in float32 registers
    acc = 0.0

    num_8_blocks = K // 8
    vec8_indices = tl.arange(0, 8)
    norm_factor = 2.82842712  # sqrt(8): scale unit 8D vector to match block RMS

    # Loop over 8-dimensional chunks
    for b in range(num_8_blocks):
        # Load input 8D slice: x[0, b*8 : (b+1)*8]
        offs_k = b * 8 + vec8_indices
        x_val = tl.load(X_ptr + offs_k * stride_xk) # [8] float16 or float32

        # Scale index for this block
        scale_block_idx = (b * 8) // BLOCK_SCALE
        scale = tl.load(Scales_ptr + m * stride_sm + scale_block_idx * stride_sk).to(tl.float32)

        # Root index for row m, block b (0..239)
        r_id = tl.load(Indices_ptr + m * stride_im + b * stride_ik).to(tl.int32)

        # Load 8D root from E8 codebook
        r_ptrs = Roots_ptr + r_id * stride_rm + vec8_indices * stride_rk
        r_vec = tl.load(r_ptrs).to(tl.float32) * norm_factor # [8]

        dot = tl.sum(x_val * r_vec)
        acc += dot * scale

    # Store result to global HBM
    tl.store(Out_ptr + m * stride_on, acc.to(tl.float16))


def fused_e8_gemv(
    x: torch.Tensor,
    indices: torch.Tensor,
    scales: torch.Tensor,
    roots: torch.Tensor,
    scale_block_size: int = 64
) -> torch.Tensor:
    """
    Python wrapper for the fused Triton E8 Gosset GEMV operator.
    Args:
        x: Input tensor [batch, in_features] or [1, in_features]
        indices: [out_features, in_features // 8] uint8 or int32 (0..239)
        scales: [out_features, in_features // scale_block_size] float16
        roots: [240, 8] float32 E8 Gosset minimal roots
        scale_block_size: Block size for scale sharing (default: 64 weights)
    Returns:
        output: [batch, out_features] float16
    """
    assert x.is_cuda and indices.is_cuda and scales.is_cuda and roots.is_cuda
    orig_shape = x.shape
    x_2d = x.reshape(-1, orig_shape[-1])
    batch_size, K = x_2d.shape
    M = indices.shape[0]

    assert K % 8 == 0, "in_features must be divisible by 8"
    assert roots.shape == (240, 8), f"roots codebook must be [240, 8], got {roots.shape}"

    out = torch.empty((batch_size, M), device=x.device, dtype=torch.float16)
    grid = (M,)

    for i in range(batch_size):
        x_row = x_2d[i : i + 1]
        out_row = out[i : i + 1]

        _fused_e8_gemv_kernel[grid](
            x_row, indices, scales, roots, out_row,
            M, K,
            x_row.stride(0), x_row.stride(1),
            indices.stride(0), indices.stride(1),
            scales.stride(0), scales.stride(1),
            roots.stride(0), roots.stride(1),
            out_row.stride(0), out_row.stride(1),
            BLOCK_SCALE=scale_block_size,
        )

    return out.reshape(orig_shape[:-1] + (M,))
