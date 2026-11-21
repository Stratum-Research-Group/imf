"""
imf/triton_leech_kernel.py
==========================
Triton Fused Leech Lattice (24D) / Polytope Root Dequantization GEMV Kernel.

Fuses root codebook lookup, scale factor multiplication, and dot-product accumulation
directly inside GPU registers and SRAM, avoiding materialization of intermediate uncompressed
FP16/FP32 weights in global HBM.
"""

import math
import torch
import triton
import triton.language as tl


@triton.jit
def _fused_leech24_gemv_kernel(
    X_ptr,          # Pointer to input vector x [1, K]
    Indices_ptr,    # Pointer to root indices [M, K // 24] (int32)
    Scales_ptr,     # Pointer to scales [M, K // BLOCK_SCALE] (float16)
    Roots_ptr,      # Pointer to Leech 24D codebook [num_roots, 24] (float32)
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
    Computes 1xK @ KxM -> 1xM with fused Leech 24D register dequantization.
    Each program block handles 1 row of output m.
    """
    m = tl.program_id(0)
    if m >= M:
        return

    # Accumulator in float32 registers
    acc = 0.0

    num_24_blocks = K // 24
    vec32_indices = tl.arange(0, 32)
    mask_24 = vec32_indices < 24
    norm_factor = 0.35355339

    # Loop over 24-dimensional chunks
    for b in range(num_24_blocks):
        # Load input 24D slice: x[0, b*24 : (b+1)*24]
        offs_k = b * 24 + vec32_indices
        x_val = tl.load(X_ptr + offs_k * stride_xk, mask=mask_24, other=0.0) # [32]

        # Scale index for this block
        scale_block_idx = (b * 24) // BLOCK_SCALE
        scale = tl.load(Scales_ptr + m * stride_sm + scale_block_idx * stride_sk).to(tl.float32)

        # Root index for row m, block b
        r_id = tl.load(Indices_ptr + m * stride_im + b * stride_ik)

        # Load 24D root from codebook
        r_ptrs = Roots_ptr + r_id * stride_rm + vec32_indices * stride_rk
        r_vec = tl.load(r_ptrs, mask=mask_24, other=0.0).to(tl.float32) * norm_factor # [32]

        dot = tl.sum(x_val * r_vec)
        acc += dot * scale

    # Store result to global HBM
    tl.store(Out_ptr + m * stride_on, acc.to(tl.float16))


def fused_leech24_gemv(
    x: torch.Tensor,
    indices: torch.Tensor,
    scales: torch.Tensor,
    roots: torch.Tensor,
    scale_block_size: int = 48
) -> torch.Tensor:
    """
    Python wrapper for the fused Triton Leech 24D GEMV operator.
    """
    assert x.is_cuda and indices.is_cuda and scales.is_cuda and roots.is_cuda
    orig_shape = x.shape
    x_2d = x.reshape(-1, orig_shape[-1])
    batch_size, K = x_2d.shape
    M = indices.shape[0]

    assert K % 24 == 0, "in_features must be divisible by 24"
    assert roots.shape[1] == 24, "roots codebook must be 24-dimensional"

    out = torch.empty((batch_size, M), device=x.device, dtype=torch.float16)
    grid = (M,)

    for i in range(batch_size):
        x_row = x_2d[i : i + 1]
        out_row = out[i : i + 1]

        _fused_leech24_gemv_kernel[grid](
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
