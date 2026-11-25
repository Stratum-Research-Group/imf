"""
imf/kernels/triton_fused_polytope_geodesic_backward.py
Triton Fused Analytical Backward for Poincaré Hyperbolic Geodesic Distance.
Calculates exact partial derivatives d/du of:
    d_B(u, v) = arcosh(1 + 2 * ||u - v||^2 / ((1 - ||u||^2)(1 - ||v||^2)))
Author: Nicholas Charles Mynhardt (Stratum Research Group)
"""

import torch
import triton
import triton.language as tl
from typing import Tuple


@triton.jit
def _poincare_geodesic_bwd_kernel(
    grad_out_ptr,
    u_ptr, v_ptr,
    grad_u_ptr, grad_v_ptr,
    n_rows, D: tl.constexpr,
    EPS: tl.constexpr
):
    row = tl.program_id(0)
    if row >= n_rows:
        return

    d_offs = tl.arange(0, D)
    go = tl.load(grad_out_ptr + row).to(tl.float32)
    u = tl.load(u_ptr + row * D + d_offs).to(tl.float32)
    v = tl.load(v_ptr + row * D + d_offs).to(tl.float32)

    diff = u - v
    diff_sq = tl.sum(diff * diff)
    u_sq = tl.sum(u * u)
    v_sq = tl.sum(v * v)

    lambda_u = 1.0 - u_sq
    lambda_v = 1.0 - v_sq
    denom = lambda_u * lambda_v

    # delta = 1 + 2 * diff_sq / denom
    delta = 1.0 + 2.0 * diff_sq / denom

    # arcosh'(delta) = 1 / sqrt(delta^2 - 1)
    d_arcosh = 1.0 / tl.sqrt(delta * delta - 1.0 + EPS)

    # d delta / d u = 4 / (lambda_u * lambda_v) * diff + 4 * diff_sq / (lambda_u^2 * lambda_v) * u
    scale_diff_u = 4.0 / denom
    scale_u = 4.0 * diff_sq / (lambda_u * lambda_u * lambda_v)

    # d delta / d v = -4 / (lambda_u * lambda_v) * diff + 4 * diff_sq / (lambda_u * lambda_v^2) * v
    scale_diff_v = -4.0 / denom
    scale_v = 4.0 * diff_sq / (lambda_u * lambda_v * lambda_v)

    gu = go * d_arcosh * (scale_diff_u * diff + scale_u * u)
    gv = go * d_arcosh * (scale_diff_v * diff + scale_v * v)

    tl.store(grad_u_ptr + row * D + d_offs, gu)
    tl.store(grad_v_ptr + row * D + d_offs, gv)


def poincare_geodesic_backward(
    grad_out: torch.Tensor,
    u: torch.Tensor,
    v: torch.Tensor,
    eps: float = 1e-7
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Computes analytical gradients grad_u and grad_v for Poincaré distance.
    """
    assert u.is_cuda and v.is_cuda and grad_out.is_cuda, "CUDA required"
    assert u.shape == v.shape
    N, D = u.shape

    grad_u = torch.empty_like(u)
    grad_v = torch.empty_like(v)

    _poincare_geodesic_bwd_kernel[(N,)](
        grad_out.contiguous(),
        u.contiguous(), v.contiguous(),
        grad_u, grad_v,
        n_rows=N, D=D,
        EPS=eps
    )
    return grad_u, grad_v
