"""
imf/kernels/triton_fused_soliton_backward.py
Fused Triton Soliton Activation & LayerNorm Backward Kernel.
Computes analytical gradients for the discrete non-linear integrable soliton activation layer
directly fused with LayerNorm backward to eliminate intermediate activations from VRAM.
"""

import torch
import triton
import triton.language as tl
from typing import Tuple


@triton.jit
def _soliton_rmsnorm_fwd_kernel(
    x_ptr,           # [N, D]
    gamma_ptr,       # [D]
    scale_ptr,       # [D]
    out_ptr,         # [N, D]
    inv_rms_ptr,     # [N]
    N: tl.constexpr,
    D: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    row_idx = tl.program_id(0)
    row_offset = row_idx * D

    # 1. Compute RMS of row
    sum_sq = 0.0
    for d_start in range(0, D, BLOCK_D):
        d_offsets = d_start + tl.arange(0, BLOCK_D)
        mask = d_offsets < D
        x_val = tl.load(x_ptr + row_offset + d_offsets, mask=mask, other=0.0)
        sum_sq += tl.sum(x_val * x_val, axis=0)

    rms = tl.sqrt(sum_sq / D + 1e-5)
    inv_rms = 1.0 / rms
    tl.store(inv_rms_ptr + row_idx, inv_rms)

    # 2. RMSNorm + Soliton non-linearity: y = norm_x + tanh(0.1 * norm_x) * scale
    for d_start in range(0, D, BLOCK_D):
        d_offsets = d_start + tl.arange(0, BLOCK_D)
        mask = d_offsets < D
        x_val = tl.load(x_ptr + row_offset + d_offsets, mask=mask, other=0.0)
        gamma = tl.load(gamma_ptr + d_offsets, mask=mask, other=1.0)
        scale = tl.load(scale_ptr + d_offsets, mask=mask, other=0.1)

        norm_x = x_val * inv_rms * gamma
        # Soliton peakon activation: tanh(0.1 * norm_x)
        tanh_act = (tl.exp(0.2 * norm_x) - 1.0) / (tl.exp(0.2 * norm_x) + 1.0)
        out_val = norm_x + tanh_act * scale
        tl.store(out_ptr + row_offset + d_offsets, out_val, mask=mask)


@triton.jit
def _soliton_rmsnorm_bwd_kernel(
    grad_out_ptr,    # [N, D] incoming gradient
    x_ptr,           # [N, D] original input
    gamma_ptr,       # [D] norm weights
    scale_ptr,       # [D] soliton scales
    inv_rms_ptr,     # [N] saved inverse RMS
    grad_x_ptr,      # [N, D] output gradient dL/dx
    N: tl.constexpr,
    D: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    row_idx = tl.program_id(0)
    row_offset = row_idx * D
    inv_rms = tl.load(inv_rms_ptr + row_idx)

    # Compute row dot product: sum(grad_out * d(soliton)/d(norm_x) * norm_x)
    sum_dot = 0.0
    for d_start in range(0, D, BLOCK_D):
        d_offsets = d_start + tl.arange(0, BLOCK_D)
        mask = d_offsets < D
        g_out = tl.load(grad_out_ptr + row_offset + d_offsets, mask=mask, other=0.0)
        x_val = tl.load(x_ptr + row_offset + d_offsets, mask=mask, other=0.0)
        gamma = tl.load(gamma_ptr + d_offsets, mask=mask, other=1.0)
        scale = tl.load(scale_ptr + d_offsets, mask=mask, other=0.1)

        norm_x = x_val * inv_rms * gamma
        tanh_act = (tl.exp(0.2 * norm_x) - 1.0) / (tl.exp(0.2 * norm_x) + 1.0)
        # d/d(norm_x) [norm_x + tanh(0.1*norm_x)*scale] = 1.0 + 0.1*(1 - tanh^2)*scale
        d_act = 1.0 + 0.1 * (1.0 - tanh_act * tanh_act) * scale
        d_norm = g_out * d_act

        sum_dot += tl.sum(d_norm * norm_x, axis=0)

    # Compute grad_x = inv_rms * gamma * (d_norm - norm_x / D * sum_dot)
    for d_start in range(0, D, BLOCK_D):
        d_offsets = d_start + tl.arange(0, BLOCK_D)
        mask = d_offsets < D
        g_out = tl.load(grad_out_ptr + row_offset + d_offsets, mask=mask, other=0.0)
        x_val = tl.load(x_ptr + row_offset + d_offsets, mask=mask, other=0.0)
        gamma = tl.load(gamma_ptr + d_offsets, mask=mask, other=1.0)
        scale = tl.load(scale_ptr + d_offsets, mask=mask, other=0.1)

        norm_x = x_val * inv_rms * gamma
        tanh_act = (tl.exp(0.2 * norm_x) - 1.0) / (tl.exp(0.2 * norm_x) + 1.0)
        d_act = 1.0 + 0.1 * (1.0 - tanh_act * tanh_act) * scale
        d_norm = g_out * d_act

        gx = inv_rms * gamma * (d_norm - (norm_x / D) * sum_dot)
        tl.store(grad_x_ptr + row_offset + d_offsets, gx, mask=mask)


class FusedSolitonRMSNormFunction(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x: torch.Tensor, gamma: torch.Tensor, scale: torch.Tensor) -> torch.Tensor:
        orig_shape = x.shape
        N = x.numel() // x.shape[-1]
        D = x.shape[-1]
        x_flat = x.view(N, D).contiguous()

        out = torch.empty_like(x_flat)
        inv_rms = torch.empty(N, dtype=torch.float32, device=x.device)

        BLOCK_D = min(1024, triton.next_power_of_2(D))
        grid = (N,)

        _soliton_rmsnorm_fwd_kernel[grid](
            x_flat, gamma, scale, out, inv_rms,
            N=N, D=D, BLOCK_D=BLOCK_D
        )

        ctx.save_for_backward(x_flat, gamma, scale, inv_rms)
        ctx.orig_shape = orig_shape
        ctx.D = D
        ctx.N = N
        ctx.BLOCK_D = BLOCK_D
        return out.view(orig_shape)

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor) -> Tuple[torch.Tensor, None, None]:
        x_flat, gamma, scale, inv_rms = ctx.saved_tensors
        D = ctx.D
        N = ctx.N
        BLOCK_D = ctx.BLOCK_D
        
        grad_out_flat = grad_output.contiguous().view(N, D)
        grad_x = torch.empty_like(x_flat)

        grid = (N,)
        _soliton_rmsnorm_bwd_kernel[grid](
            grad_out_flat, x_flat, gamma, scale, inv_rms, grad_x,
            N=N, D=D, BLOCK_D=BLOCK_D
        )

        return grad_x.view(ctx.orig_shape), None, None


def fused_soliton_rmsnorm(x: torch.Tensor, gamma: torch.Tensor, scale: torch.Tensor) -> torch.Tensor:
    return FusedSolitonRMSNormFunction.apply(x, gamma, scale)
