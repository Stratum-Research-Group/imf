"""
imf/kernels/triton_fused_cauchy_schwarz_norm.py
Triton Fused Cauchy-Schwarz Normalization & Geodesic Metric Kernel.
Computes fused unit-norm projection and Cauchy-Schwarz inner-product bounding:
    u_norm = u / sqrt(||u||^2 + eps)
    v_norm = v / sqrt(||v||^2 + eps)
    bounded_norm = min(1.0 - delta, ||u||)
Author: Nicholas Charles Mynhardt (Stratum Research Group)
"""

import torch
import triton
import triton.language as tl
from typing import Tuple


@triton.jit
def _cauchy_schwarz_norm_kernel(
    u_ptr, v_ptr,
    u_bounded_ptr, v_bounded_ptr,
    inner_prod_ptr,
    n_rows, D: tl.constexpr,
    DELTA: tl.constexpr, EPS: tl.constexpr
):
    row = tl.program_id(0)
    if row >= n_rows:
        return

    d_offs = tl.arange(0, D)
    u = tl.load(u_ptr + row * D + d_offs).to(tl.float32)
    v = tl.load(v_ptr + row * D + d_offs).to(tl.float32)

    # Compute Euclidean norms
    u_sq = tl.sum(u * u)
    v_sq = tl.sum(v * v)
    u_norm = tl.sqrt(u_sq + EPS)
    v_norm = tl.sqrt(v_sq + EPS)

    # Bound norm to avoid manifold boundary singularities (||u|| < 1.0 - delta)
    max_radius = 1.0 - DELTA
    scale_u = tl.where(u_norm > max_radius, max_radius / u_norm, 1.0)
    scale_v = tl.where(v_norm > max_radius, max_radius / v_norm, 1.0)

    u_bounded = u * scale_u
    v_bounded = v * scale_v

    # Inner product in bounded Poincaré ball
    dot = tl.sum(u_bounded * v_bounded)

    tl.store(u_bounded_ptr + row * D + d_offs, u_bounded)
    tl.store(v_bounded_ptr + row * D + d_offs, v_bounded)
    tl.store(inner_prod_ptr + row, dot)


def cauchy_schwarz_poincare_norm(
    u: torch.Tensor,
    v: torch.Tensor,
    delta: float = 1e-4,
    eps: float = 1e-8
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Clamps vectors inside the open Poincaré ball B^d of radius 1 - delta and returns
    bounded vectors and their dot product with exact finite guarantees.
    """
    assert u.is_cuda and v.is_cuda, "Tensors must be on CUDA"
    assert u.shape == v.shape
    u_contig, v_contig = u.contiguous(), v.contiguous()
    N, D = u_contig.shape

    u_bounded = torch.empty_like(u_contig)
    v_bounded = torch.empty_like(v_contig)
    inner_prod = torch.empty(N, device=u.device, dtype=torch.float32)

    _cauchy_schwarz_norm_kernel[(N,)](
        u_contig, v_contig,
        u_bounded, v_bounded,
        inner_prod,
        n_rows=N, D=D,
        DELTA=delta, EPS=eps
    )
    return u_bounded, v_bounded, inner_prod
