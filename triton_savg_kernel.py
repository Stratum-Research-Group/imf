"""
triton_savg_kernel.py
Production-grade Triton GPU kernel for Fused Symmetric-Antisymmetric Virtual Grid Attention.
Fuses:
  1. Outer product computation: U(t) ⊗ V(t)
  2. Barycentric simplex / polytope coordinate projection & modulation
  3. Decoupled Symmetric and Antisymmetric running state accumulation
  4. Query readout: (S_state + A_state) · Q(t)
All within high-speed GPU SRAM registers, avoiding intermediate HBM round-trips.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
import triton
import triton.language as tl


@triton.jit
def _fused_savg_scan_kernel(
    U_ptr, V_ptr, Q_ptr, Mod_ptr, Out_ptr,
    B, T, D,
    stride_ub, stride_ut, stride_ud,
    stride_vb, stride_vt, stride_vd,
    stride_qb, stride_qt, stride_qd,
    stride_mb, stride_mt,
    stride_ob, stride_ot, stride_od,
    gamma_s: tl.constexpr,
    gamma_a: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    """
    Fused per-batch-item scan kernel over sequence dimension T.
    Maintains symmetric state S and antisymmetric state A in SRAM registers.
    """
    pid_b = tl.program_id(0) # Batch index

    # Pointer offsets for this batch element
    u_b_ptr = U_ptr + pid_b * stride_ub
    v_b_ptr = V_ptr + pid_b * stride_vb
    q_b_ptr = Q_ptr + pid_b * stride_qb
    m_b_ptr = Mod_ptr + pid_b * stride_mb
    o_b_ptr = Out_ptr + pid_b * stride_ob

    # Block range for D dimension
    offs_d1 = tl.arange(0, BLOCK_D)
    offs_d2 = tl.arange(0, BLOCK_D)
    mask_d1 = offs_d1 < D
    mask_d2 = offs_d2 < D
    mask_2d = mask_d1[:, None] & mask_d2[None, :]

    # Initialize recurrent states in SRAM: [BLOCK_D, BLOCK_D]
    S_state = tl.zeros([BLOCK_D, BLOCK_D], dtype=tl.float32)
    A_state = tl.zeros([BLOCK_D, BLOCK_D], dtype=tl.float32)

    # Sequential causal scan over timesteps t = 0 .. T-1
    for t in range(0, T):
        # Load u_t and v_t vectors
        u_t = tl.load(u_b_ptr + t * stride_ut + offs_d1 * stride_ud, mask=mask_d1, other=0.0)
        v_t = tl.load(v_b_ptr + t * stride_vt + offs_d2 * stride_vd, mask=mask_d2, other=0.0)
        q_t = tl.load(q_b_ptr + t * stride_qt + offs_d2 * stride_qd, mask=mask_d2, other=0.0)

        # Load scalar grid modulation factor
        mod_t = tl.load(m_b_ptr + t * stride_mt)

        # Outer products in SRAM registers
        # u_t is [BLOCK_D, 1], v_t is [1, BLOCK_D]
        uv = u_t[:, None] * v_t[None, :]
        vu = v_t[:, None] * u_t[None, :]

        # Lie-algebraic symmetric and antisymmetric increments
        s_inc = 0.5 * (uv + vu) * mod_t
        a_inc = 0.5 * (uv - vu) * mod_t

        # State updates with decay factors
        S_state = S_state * gamma_s + s_inc
        A_state = A_state * gamma_a + a_inc

        # Readout: out_t = (S_state + A_state) · q_t
        # [BLOCK_D, BLOCK_D] x [BLOCK_D, 1] -> [BLOCK_D]
        net_state = S_state + A_state
        out_t = tl.sum(net_state * q_t[None, :], axis=1)

        # Store to output tensor
        tl.store(o_b_ptr + t * stride_ot + offs_d1 * stride_od, out_t, mask=mask_d1)


def triton_fused_savg_scan(
    U: torch.Tensor,
    V: torch.Tensor,
    Q: torch.Tensor,
    mod: torch.Tensor,
    gamma_s: float = 0.999,
    gamma_a: float = 0.990,
) -> torch.Tensor:
    """
    Python wrapper invoking the JIT fused SAVG Triton kernel.
    Args:
        U, V, Q: [Batch, SeqLen, Dim] (float32 or bfloat16)
        mod: [Batch, SeqLen] (scalar modulation factors from polytope connector)
    Returns:
        Out: [Batch, SeqLen, Dim]
    """
    assert U.is_cuda and V.is_cuda and Q.is_cuda and mod.is_cuda
    B, T, D = U.shape
    assert D <= 128, "Currently tuned for tile dimensions D <= 128"

    # Next power of 2 for Triton tile
    BLOCK_D = triton.next_power_of_2(D)
    Out = torch.empty_like(U)

    grid = (B,)
    _fused_savg_scan_kernel[grid](
        U, V, Q, mod, Out,
        B, T, D,
        U.stride(0), U.stride(1), U.stride(2),
        V.stride(0), V.stride(1), V.stride(2),
        Q.stride(0), Q.stride(1), Q.stride(2),
        mod.stride(0), mod.stride(1),
        Out.stride(0), Out.stride(1), Out.stride(2),
        gamma_s=gamma_s,
        gamma_a=gamma_a,
        BLOCK_D=BLOCK_D,
    )
    return Out


class FusedSAVGLayer(nn.Module):
    """Production-grade Fused SAVG Layer powered by Triton."""
    def __init__(self, d_model: int, preset: str = "decayotton_orthoplex"):
        super().__init__()
        from polytope_connector import ConfigurablePolytopeConnector
        self.d_model = d_model
        self.W_u = nn.Linear(d_model, d_model, bias=False)
        self.W_v = nn.Linear(d_model, d_model, bias=False)
        self.W_q = nn.Linear(d_model, d_model, bias=False)
        self.out_proj = nn.Linear(d_model, d_model, bias=False)

        self.connector = ConfigurablePolytopeConnector(d_model, preset=preset)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        U = self.W_u(x)
        V = self.W_v(x)
        Q = self.W_q(x)

        # Compute grid modulation: [B, T, 1, 1] -> squeeze to [B, T]
        grid_mod = self.connector.compute_grid_modulation(x).squeeze(-1).squeeze(-1)

        # Triton fused scan
        out_scan = triton_fused_savg_scan(U, V, Q, grid_mod)
        return self.out_proj(out_scan)
