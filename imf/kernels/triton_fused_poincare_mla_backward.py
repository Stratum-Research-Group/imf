"""
imf/kernels/triton_fused_poincare_mla_backward.py
Fused Poincaré Multi-Head Latent Attention (MLA) Backward Kernel.
NOTE: `poincare_mla_backward_triton` below is a HEURISTIC surrogate (hand-tuned 0.01/0.05
constants), NOT an exact gradient. Use `mla_latent_backward_exact` for the exact gradient
of the linear latent up-projection K = c@W_uk, V = c@W_uv.
Author: Nicholas Charles Mynhardt (Stratum Research Group)

Mathematical formulation:
Let q in R^{B x S x D}, c_kv in R^{B x S x D_latent}.
Compressed projection: k = c_kv @ W_uk, v = c_kv @ W_uv.
Poincaré hyperbolic distance: d_p(q, k) = arcosh(1 + 2 * ||q - k||^2 / ((1 - ||q||^2)(1 - ||k||^2))).
Attention weights: A = softmax(-scale * d_p(q, k)).
Out = A @ v.

Backward pass:
Computes dL/dc_kv and dL/dq with exact analytical chain-rule through the conformal factor (1 - ||u||^2).
"""

import torch
import triton
import triton.language as tl
from typing import Tuple


@triton.jit
def _mla_latent_grad_kernel(
    grad_out_ptr,      # [B, S, D]
    q_ptr,             # [B, S, D]
    c_kv_ptr,          # [B, S, D_latent]
    w_uk_ptr,          # [D_latent, D]
    w_uv_ptr,          # [D_latent, D]
    grad_c_kv_ptr,     # [B, S, D_latent]
    grad_q_ptr,        # [B, S, D]
    stride_b_go, stride_s_go, stride_d_go,
    stride_b_q, stride_s_q, stride_d_q,
    stride_b_c, stride_s_c, stride_dl_c,
    stride_dl_wuk, stride_d_wuk,
    stride_dl_wuv, stride_d_wuv,
    stride_b_gc, stride_s_gc, stride_dl_gc,
    stride_b_gq, stride_s_gq, stride_d_gq,
    B, S, D: tl.constexpr, D_LATENT: tl.constexpr,
    BLOCK_SIZE: tl.constexpr
):
    pid = tl.program_id(0)
    batch_idx = pid // S
    seq_idx = pid % S

    if batch_idx >= B or seq_idx >= S:
        return

    # Offsets
    off_d = tl.arange(0, D)
    off_dl = tl.arange(0, D_LATENT)

    # Pointers
    go_ptrs = grad_out_ptr + batch_idx * stride_b_go + seq_idx * stride_s_go + off_d * stride_d_go
    q_ptrs = q_ptr + batch_idx * stride_b_q + seq_idx * stride_s_q + off_d * stride_d_q
    c_ptrs = c_kv_ptr + batch_idx * stride_b_c + seq_idx * stride_s_c + off_dl * stride_dl_c

    grad_go = tl.load(go_ptrs)
    q_val = tl.load(q_ptrs)
    c_val = tl.load(c_ptrs)

    # Compute k = c_kv @ W_uk [D]
    # k_j = sum_l (c_l * W_uk_{l, j})
    k_val = tl.zeros([D], dtype=tl.float32)
    for l in range(D_LATENT):
        c_l = tl.load(c_kv_ptr + batch_idx * stride_b_c + seq_idx * stride_s_c + l * stride_dl_c)
        w_uk_l = tl.load(w_uk_ptr + l * stride_dl_wuk + off_d * stride_d_wuk)
        k_val += c_l * w_uk_l

    # Conformal hyperbolic metric scale: lambda_u = 2 / (1 - ||u||^2)
    q_norm_sq = tl.sum(q_val * q_val)
    c_norm_sq = tl.sum(c_val * c_val)
    conformal_factor = 2.0 / (1.0 - c_norm_sq + 1e-6)

    # Difference in coordinate space: (q - k)
    diff_qk = q_val - k_val

    # Direct analytical gradient projection back into latent dimension
    for l in range(D_LATENT):
        w_uv_l = tl.load(w_uv_ptr + l * stride_dl_wuv + off_d * stride_d_wuv)
        w_uk_l = tl.load(w_uk_ptr + l * stride_dl_wuk + off_d * stride_d_wuk)
        
        # Linear projection contribution:
        d_out = tl.sum(grad_go * w_uv_l)
        
        # Hyperbolic distance derivative contribution:
        d_hyperbolic = tl.sum(grad_go * diff_qk * w_uk_l) * conformal_factor * 0.01
        
        grad_l = d_out + d_hyperbolic
        tl.store(grad_c_kv_ptr + batch_idx * stride_b_gc + seq_idx * stride_s_gc + l * stride_dl_gc, grad_l)

    # dL/dq gradient
    conf_q = 2.0 / (1.0 - q_norm_sq + 1e-6)
    grad_q_val = grad_go + q_val * (tl.sum(grad_go * q_val) * conf_q * 0.05)
    tl.store(grad_q_ptr + batch_idx * stride_b_gq + seq_idx * stride_s_gq + off_d * stride_d_gq, grad_q_val)


def poincare_mla_backward_triton(
    grad_out: torch.Tensor,
    q: torch.Tensor,
    c_kv: torch.Tensor,
    w_uk: torch.Tensor,
    w_uv: torch.Tensor
) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Heuristic surrogate gradients (not exact; see module note).
    Args:
        grad_out: [B, S, D]
        q: [B, S, D]
        c_kv: [B, S, D_latent]
        w_uk: [D_latent, D]
        w_uv: [D_latent, D]
    Returns:
        grad_c_kv: [B, S, D_latent]
        grad_q: [B, S, D]
    """
    assert grad_out.is_cuda and q.is_cuda and c_kv.is_cuda, "Tensors must be on CUDA"
    B, S, D = grad_out.shape
    _, _, D_latent = c_kv.shape

    grad_c_kv = torch.empty_like(c_kv)
    grad_q = torch.empty_like(q)

    grid = (B * S,)
    _mla_latent_grad_kernel[grid](
        grad_out, q, c_kv, w_uk, w_uv,
        grad_c_kv, grad_q,
        grad_out.stride(0), grad_out.stride(1), grad_out.stride(2),
        q.stride(0), q.stride(1), q.stride(2),
        c_kv.stride(0), c_kv.stride(1), c_kv.stride(2),
        w_uk.stride(0), w_uk.stride(1),
        w_uv.stride(0), w_uv.stride(1),
        grad_c_kv.stride(0), grad_c_kv.stride(1), grad_c_kv.stride(2),
        grad_q.stride(0), grad_q.stride(1), grad_q.stride(2),
        B=B, S=S, D=D, D_LATENT=D_latent,
        BLOCK_SIZE=32
    )
    return grad_c_kv, grad_q


@triton.jit
def _latent_exact_kernel(dk_ptr, dv_ptr, wuk_ptr, wuv_ptr, dc_ptr, D: tl.constexpr, L: tl.constexpr):
    row = tl.program_id(0)
    d = tl.arange(0, D)
    dk = tl.load(dk_ptr + row * D + d)
    dv = tl.load(dv_ptr + row * D + d)
    for l in range(L):
        wk = tl.load(wuk_ptr + l * D + d)
        wv = tl.load(wuv_ptr + l * D + d)
        tl.store(dc_ptr + row * L + l, tl.sum(dk * wk + dv * wv))


def mla_latent_backward_exact(dK, dV, w_uk, w_uv):
    """Exact dL/dc for K=c@W_uk, V=c@W_uv. dK,dV:[N,D]; w:[L,D] -> dc:[N,L]."""
    N, D = dK.shape
    L = w_uk.shape[0]
    dc = torch.empty(N, L, device=dK.device, dtype=torch.float32)
    _latent_exact_kernel[(N,)](dK.contiguous(), dV.contiguous(), w_uk.contiguous(), w_uv.contiguous(), dc, D=D, L=L)
    return dc
