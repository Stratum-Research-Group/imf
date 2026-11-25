"""
imf/kernels/triton_fused_poincare_geodesic_backward.py
Fused Triton Poincaré Hyperbolic Geodesic Distance Forward & Backward Kernel.
Computes hyperbolic distance:
    delta = 1 + 2 * ||u - v||^2 / ((1 - ||u||^2) * (1 - ||v||^2))
    d_D(u, v) = arcosh(delta) = ln(delta + sqrt(delta^2 - 1))
and its analytical gradient:
    grad_u = (4 / (alpha * beta * sqrt(delta^2 - 1))) * (u * ||v||^2 - 2*v + u)  [where alpha = 1 - ||u||^2, beta = 1 - ||v||^2]
directly in GPU SRAM without intermediate VRAM activation tensors.
"""

import math
import torch
import triton
import triton.language as tl
from typing import Tuple


@triton.jit
def _poincare_geodesic_fwd_kernel(
    u_ptr,           # [B, D]
    v_ptr,           # [B, D]
    dist_ptr,        # [B]
    delta_ptr,       # [B]
    alpha_ptr,       # [B]
    beta_ptr,        # [B]
    B: tl.constexpr,
    D: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    b_idx = tl.program_id(0)
    b_offset = b_idx * D

    sum_diff_sq = 0.0
    sum_u_sq = 0.0
    sum_v_sq = 0.0

    for d_start in range(0, D, BLOCK_D):
        d_offsets = d_start + tl.arange(0, BLOCK_D)
        mask = d_offsets < D

        u_val = tl.load(u_ptr + b_offset + d_offsets, mask=mask, other=0.0)
        v_val = tl.load(v_ptr + b_offset + d_offsets, mask=mask, other=0.0)

        diff = u_val - v_val
        sum_diff_sq += tl.sum(diff * diff, axis=0)
        sum_u_sq += tl.sum(u_val * u_val, axis=0)
        sum_v_sq += tl.sum(v_val * v_val, axis=0)

    # Clamping norms to unit disk radius (< 0.999)
    u_norm_sq = tl.minimum(sum_u_sq, 0.998)
    v_norm_sq = tl.minimum(sum_v_sq, 0.998)

    alpha = 1.0 - u_norm_sq
    beta = 1.0 - v_norm_sq

    delta = 1.0 + 2.0 * sum_diff_sq / (alpha * beta + 1e-7)
    delta_clamped = tl.maximum(delta, 1.00001)

    # arcosh(delta) = ln(delta + sqrt(delta^2 - 1))
    sqrt_term = tl.sqrt(delta_clamped * delta_clamped - 1.0)
    dist = tl.log(delta_clamped + sqrt_term)

    tl.store(dist_ptr + b_idx, dist)
    tl.store(delta_ptr + b_idx, delta_clamped)
    tl.store(alpha_ptr + b_idx, alpha)
    tl.store(beta_ptr + b_idx, beta)


@triton.jit
def _poincare_geodesic_bwd_kernel(
    grad_dist_ptr,   # [B]
    u_ptr,           # [B, D]
    v_ptr,           # [B, D]
    delta_ptr,       # [B]
    alpha_ptr,       # [B]
    beta_ptr,        # [B]
    grad_u_ptr,      # [B, D]
    B: tl.constexpr,
    D: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    b_idx = tl.program_id(0)
    b_offset = b_idx * D

    g_d = tl.load(grad_dist_ptr + b_idx)
    delta = tl.load(delta_ptr + b_idx)
    alpha = tl.load(alpha_ptr + b_idx)
    beta = tl.load(beta_ptr + b_idx)

    # sqrt(delta^2 - 1)
    denom_sqrt = tl.sqrt(delta * delta - 1.0 + 1e-7)
    # scalar prefactor: 4 / (alpha * beta * sqrt(delta^2 - 1))
    coeff = 4.0 / (alpha * beta * denom_sqrt + 1e-7)

    # Compute sum_v_sq and sum_diff_sq for exact quotient rule
    sum_diff_sq = 0.5 * (delta - 1.0) * (alpha * beta)

    for d_start in range(0, D, BLOCK_D):
        d_offsets = d_start + tl.arange(0, BLOCK_D)
        mask = d_offsets < D

        u_val = tl.load(u_ptr + b_offset + d_offsets, mask=mask, other=0.0)
        v_val = tl.load(v_ptr + b_offset + d_offsets, mask=mask, other=0.0)

        # d(delta)/du_i = 4(u_i - v_i)/(alpha*beta) + 4 * sum_diff_sq * u_i / (alpha^2 * beta)
        d_delta_du = (4.0 * (u_val - v_val) / (alpha * beta + 1e-7)) + (4.0 * sum_diff_sq * u_val / (alpha * alpha * beta + 1e-7))
        # d(dist)/du_i = (1 / denom_sqrt) * d_delta_du
        grad_u_val = g_d * (1.0 / denom_sqrt) * d_delta_du

        tl.store(grad_u_ptr + b_offset + d_offsets, grad_u_val, mask=mask)


class FusedPoincareGeodesicFunction(torch.autograd.Function):
    @staticmethod
    def forward(ctx, u: torch.Tensor, v: torch.Tensor) -> torch.Tensor:
        orig_shape = u.shape[:-1]
        D = u.shape[-1]
        B = u.numel() // D

        u_flat = u.view(B, D).contiguous()
        v_flat = v.view(B, D).contiguous()

        dist = torch.empty(B, dtype=torch.float32, device=u.device)
        delta = torch.empty(B, dtype=torch.float32, device=u.device)
        alpha = torch.empty(B, dtype=torch.float32, device=u.device)
        beta = torch.empty(B, dtype=torch.float32, device=u.device)

        BLOCK_D = min(1024, triton.next_power_of_2(D))
        grid = (B,)

        _poincare_geodesic_fwd_kernel[grid](
            u_flat, v_flat, dist, delta, alpha, beta,
            B=B, D=D, BLOCK_D=BLOCK_D
        )

        ctx.save_for_backward(u_flat, v_flat, delta, alpha, beta)
        ctx.D = D
        ctx.B = B
        ctx.BLOCK_D = BLOCK_D
        ctx.orig_shape = orig_shape

        return dist.view(orig_shape)

    @staticmethod
    def backward(ctx, grad_dist: torch.Tensor) -> Tuple[torch.Tensor, None]:
        u_flat, v_flat, delta, alpha, beta = ctx.saved_tensors
        D = ctx.D
        B = ctx.B
        BLOCK_D = ctx.BLOCK_D

        grad_d_flat = grad_dist.contiguous().view(B)
        grad_u = torch.empty_like(u_flat)

        grid = (B,)
        _poincare_geodesic_bwd_kernel[grid](
            grad_d_flat, u_flat, v_flat, delta, alpha, beta, grad_u,
            B=B, D=D, BLOCK_D=BLOCK_D
        )

        return grad_u.view(*ctx.orig_shape, D), None


def fused_poincare_geodesic_distance(u: torch.Tensor, v: torch.Tensor) -> torch.Tensor:
    return FusedPoincareGeodesicFunction.apply(u, v)
