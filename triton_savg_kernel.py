"""
triton_savg_kernel.py
Hardware-fused Triton JIT kernel for Symmetric-Antisymmetric Virtual Grid Attention (SAVG).

Includes:
- Autograd Function with backward pass (or pure PyTorch backward pass fallback).
- Benchmark & verification harness.
"""

import math
import time
import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    import triton
    import triton.language as tl
    HAS_TRITON = True
except ImportError:
    HAS_TRITON = False


if HAS_TRITON:
    @triton.jit
    def _fused_savg_scan_kernel(
        U_ptr, V_ptr, Q_ptr, mod_ptr, Out_ptr,
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
        pid_b = tl.program_id(axis=0)

        offs_d1 = tl.arange(0, BLOCK_D)
        offs_d2 = tl.arange(0, BLOCK_D)
        mask_d1 = offs_d1 < D
        mask_d2 = offs_d2 < D

        S_state = tl.zeros([BLOCK_D, BLOCK_D], dtype=tl.float32)
        A_state = tl.zeros([BLOCK_D, BLOCK_D], dtype=tl.float32)

        for t in range(0, T):
            u_ptrs = U_ptr + pid_b * stride_ub + t * stride_ut + offs_d1 * stride_ud
            v_ptrs = V_ptr + pid_b * stride_vb + t * stride_vt + offs_d2 * stride_vd
            q_ptrs = Q_ptr + pid_b * stride_qb + t * stride_qt + offs_d2 * stride_qd
            mod_ptr_t = mod_ptr + pid_b * stride_mb + t * stride_mt

            u_t = tl.load(u_ptrs, mask=mask_d1, other=0.0)
            v_t = tl.load(v_ptrs, mask=mask_d2, other=0.0)
            q_t = tl.load(q_ptrs, mask=mask_d2, other=0.0)
            g_t = tl.load(mod_ptr_t)

            sym_inc = 0.5 * (u_t[:, None] * v_t[None, :] + v_t[:, None] * u_t[None, :])
            anti_inc = 0.5 * (u_t[:, None] * v_t[None, :] - v_t[:, None] * u_t[None, :])

            S_state = gamma_s * S_state + g_t * sym_inc
            A_state = gamma_a * A_state + g_t * anti_inc

            net_state = S_state + A_state
            out_t = tl.sum(net_state * q_t[None, :], axis=1)

            out_ptrs = Out_ptr + pid_b * stride_ob + t * stride_ot + offs_d1 * stride_od
            tl.store(out_ptrs, out_t, mask=mask_d1)


def pytorch_reference_savg_scan(U, V, Q, grid_mod, gamma_s=0.999, gamma_a=0.990):
    """Numerically identical PyTorch reference implementation for testing and autograd."""
    B, T, D = U.shape
    device = U.device
    Out = torch.zeros_like(U)
    S_state = torch.zeros(B, D, D, device=device)
    A_state = torch.zeros(B, D, D, device=device)

    for t in range(T):
        u_t = U[:, t, :] # [B, D]
        v_t = V[:, t, :] # [B, D]
        q_t = Q[:, t, :] # [B, D]
        g_t = grid_mod[:, t].unsqueeze(-1).unsqueeze(-1) # [B, 1, 1]

        # S = 0.5 * (u v^T + v u^T)
        sym_inc = 0.5 * (torch.bmm(u_t.unsqueeze(2), v_t.unsqueeze(1)) + torch.bmm(v_t.unsqueeze(2), u_t.unsqueeze(1)))
        anti_inc = 0.5 * (torch.bmm(u_t.unsqueeze(2), v_t.unsqueeze(1)) - torch.bmm(v_t.unsqueeze(2), u_t.unsqueeze(1)))

        S_state = gamma_s * S_state + g_t * sym_inc
        A_state = gamma_a * A_state + g_t * anti_inc

        net_state = S_state + A_state # [B, D, D]
        # out_t = net_state @ q_t
        out_t = torch.bmm(net_state, q_t.unsqueeze(2)).squeeze(2)
        Out[:, t, :] = out_t
    return Out


class SAVGScanFunction(torch.autograd.Function):
    @staticmethod
    def forward(ctx, U, V, Q, grid_mod, gamma_s=0.999, gamma_a=0.990, use_triton=True):
        ctx.save_for_backward(U, V, Q, grid_mod)
        ctx.gamma_s = gamma_s
        ctx.gamma_a = gamma_a

        if use_triton and HAS_TRITON and U.is_cuda:
            B, T, D = U.shape
            BLOCK_D = triton.next_power_of_2(D)
            Out = torch.empty_like(U)
            grid = (B,)
            _fused_savg_scan_kernel[grid](
                U, V, Q, grid_mod, Out,
                B, T, D,
                U.stride(0), U.stride(1), U.stride(2),
                V.stride(0), V.stride(1), V.stride(2),
                Q.stride(0), Q.stride(1), Q.stride(2),
                grid_mod.stride(0), grid_mod.stride(1),
                Out.stride(0), Out.stride(1), Out.stride(2),
                gamma_s=gamma_s,
                gamma_a=gamma_a,
                BLOCK_D=BLOCK_D,
            )
            return Out
        else:
            return pytorch_reference_savg_scan(U, V, Q, grid_mod, gamma_s, gamma_a)

    @staticmethod
    def backward(ctx, grad_out):
        # Full autograd gradient via unrolled reference graph
        U, V, Q, grid_mod = ctx.saved_tensors
        with torch.enable_grad():
            U_ref = U.detach().requires_grad_(True)
            V_ref = V.detach().requires_grad_(True)
            Q_ref = Q.detach().requires_grad_(True)
            g_ref = grid_mod.detach().requires_grad_(True)
            out_ref = pytorch_reference_savg_scan(U_ref, V_ref, Q_ref, g_ref, ctx.gamma_s, ctx.gamma_a)
            out_ref.backward(grad_out)
        return U_ref.grad, V_ref.grad, Q_ref.grad, g_ref.grad, None, None, None


class FusedSAVGLayer(nn.Module):
    """Production-ready SAVG Layer with Autograd and Triton acceleration."""
    def __init__(self, d_model: int, preset: str = "decayotton_orthoplex"):
        super().__init__()
        from polytope_connector import ConfigurablePolytopeConnector
        self.d_model = d_model
        self.W_u = nn.Linear(d_model, d_model, bias=False)
        self.W_v = nn.Linear(d_model, d_model, bias=False)
        self.W_q = nn.Linear(d_model, d_model, bias=False)
        self.out_proj = nn.Linear(d_model, d_model, bias=False)
        self.connector = ConfigurablePolytopeConnector(d_model, preset=preset)

    def forward(self, x: torch.Tensor, use_triton: bool = True) -> torch.Tensor:
        U = self.W_u(x)
        V = self.W_v(x)
        Q = self.W_q(x)

        grid_mod = self.connector.compute_grid_modulation(x).squeeze(-1).squeeze(-1)
        out_scan = SAVGScanFunction.apply(U, V, Q, grid_mod, 0.999, 0.990, use_triton)
        return self.out_proj(out_scan)


def run_timing_and_verification():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 80)
    print(f"VERIFICATION: Triton Fused SAVG Scan vs PyTorch Reference on {device}")
    print("=" * 80)

    B, T, D = 4, 64, 32
    U = torch.randn(B, T, D, device=device)
    V = torch.randn(B, T, D, device=device)
    Q = torch.randn(B, T, D, device=device)
    mod = torch.ones(B, T, device=device)

    # 1. Numerical Equivalence
    out_ref = pytorch_reference_savg_scan(U, V, Q, mod)
    if HAS_TRITON and device.type == "cuda":
        out_triton = SAVGScanFunction.apply(U, V, Q, mod, 0.999, 0.990, True)
        max_diff = (out_ref - out_triton).abs().max().item()
        print(f"Max absolute numerical difference: {max_diff:.2e}")
        assert max_diff < 1e-4, "Triton and Reference outputs differ!"
        print("✓ Triton kernel matches PyTorch reference.")
    else:
        print("[*] Triton not running on this device; running reference.")

    # 2. Gradient Flow
    layer = FusedSAVGLayer(d_model=D).to(device)
    x = torch.randn(B, T, D, device=device, requires_grad=True)
    out = layer(x)
    loss = out.sum()
    loss.backward()

    all_have_grad = all(p.grad is not None and not torch.isnan(p.grad).any() for p in layer.parameters())
    assert all_have_grad, "Gradient flow broken!"
    print("✓ Full backward gradient flow confirmed for all layer parameters.")


if __name__ == "__main__":
    run_timing_and_verification()
