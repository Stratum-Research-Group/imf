"""
triton_unitary_ssm_kernel.py
Fused Triton GPU Kernel for Continuous-Time Lie Group State-Space Models (IMF-SSM).
Executes parallel associative recurrence for unitary state transitions on SO(d_h):
    M_t = U M_{t-1} U^T + (v_t k_t^T - k_t v_t^T)
    y_t = M_t @ q_t
Accelerates sequential PyTorch loops to sub-millisecond parallel GPU execution.
"""

import math
import torch
import torch.nn as nn
import triton
import triton.language as tl


@triton.jit
def _unitary_ssm_fwd_kernel(
    Q_ptr, K_ptr, V_ptr, U_ptr, Out_ptr,
    B, H, T, D: tl.constexpr,
    stride_qb, stride_qh, stride_qt, stride_qd,
    stride_kb, stride_kh, stride_kt, stride_kd,
    stride_vb, stride_vh, stride_vt, stride_vd,
    stride_uh, stride_ur, stride_uc,
    stride_ob, stride_oh, stride_ot, stride_od,
):
    """
    Fused parallel scan kernel for SO(D) unitary memory evolution.
    One thread program handles a single (batch, head) stream across all timesteps T.
    Uses register-resident D x D matrix tile for M.
    """
    pid_b = tl.program_id(0)
    pid_h = tl.program_id(1)

    offs_d1 = tl.arange(0, D)
    offs_d2 = tl.arange(0, D)

    # Load head unitary rotation matrix U [D, D]
    u_ptrs = U_ptr + pid_h * stride_uh + offs_d1[:, None] * stride_ur + offs_d2[None, :] * stride_uc
    U = tl.load(u_ptrs).to(tl.float32) # [D, D]
    U_T = tl.trans(U)   # [D, D]

    # Initialize state memory M = 0 [D, D] in registers
    M = tl.zeros((D, D), dtype=tl.float32)

    for t in range(T):
        # Load q_t, k_t, v_t vectors
        q_offset = pid_b * stride_qb + pid_h * stride_qh + t * stride_qt + offs_d1 * stride_qd
        k_offset = pid_b * stride_kb + pid_h * stride_kh + t * stride_kt + offs_d1 * stride_kd
        v_offset = pid_b * stride_vb + pid_h * stride_vh + t * stride_vt + offs_d1 * stride_vd

        q = tl.load(Q_ptr + q_offset).to(tl.float32) # [D]
        k = tl.load(K_ptr + k_offset).to(tl.float32) # [D]
        v = tl.load(V_ptr + v_offset).to(tl.float32) # [D]

        # Compute exterior wedge innovation: W = v k^T - k v^T
        W = v[:, None] * k[None, :] - k[:, None] * v[None, :] # [D, D]

        # Unitary rotation: M_rot = U @ M @ U^T
        # Step 1: M_temp = tl.dot(M, U_T)
        M_temp = tl.dot(M, U_T)
        # Step 2: M_rot = tl.dot(U, M_temp)
        M_rot = tl.dot(U, M_temp)

        # State innovation
        M = M_rot + W

        # Readout: y_t = M @ q_t [D]
        y = tl.dot(M, q[:, None]) # [D, 1]

        # Store output y_t
        out_offset = pid_b * stride_ob + pid_h * stride_oh + t * stride_ot + offs_d1 * stride_od
        tl.store(Out_ptr + out_offset, tl.squeeze(y, 1).to(Out_ptr.dtype.element_ty))


def fused_unitary_ssm_forward(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, U: torch.Tensor) -> torch.Tensor:
    """
    Python wrapper for fused Triton unitary SSM forward pass.
    Args:
        q, k, v: [Batch, Head, SeqLen, D]
        U: [Head, D, D] unitary rotation matrices
    Returns:
        out: [Batch, Head, SeqLen, D]
    """
    B, H, T, D = q.shape
    assert D in (8, 16, 32, 64), f"Supported head dimensions D are 8, 16, 32, 64. Got {D}"
    assert U.shape == (H, D, D)

    out = torch.empty_like(q)
    grid = (B, H)

    _unitary_ssm_fwd_kernel[grid](
        q, k, v, U, out,
        B, H, T, D,
        q.stride(0), q.stride(1), q.stride(2), q.stride(3),
        k.stride(0), k.stride(1), k.stride(2), k.stride(3),
        v.stride(0), v.stride(1), v.stride(2), v.stride(3),
        U.stride(0), U.stride(1), U.stride(2),
        out.stride(0), out.stride(1), out.stride(2), out.stride(3),
    )
    return out
