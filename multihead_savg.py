"""
multihead_savg.py
Multi-Head Symmetric-Antisymmetric Virtual Grid Attention (MH-SAVG).
Batches multiple heads over the fused Triton JIT kernel and allows heads to
specialize in symmetric vs. antisymmetric relational routing.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from triton_savg_kernel import SAVGScanFunction, HAS_TRITON
from polytope_connector import ConfigurablePolytopeConnector


class MultiHeadSAVGLayer(nn.Module):
    """
    Multi-Head SAVG Layer:
    Projects input into H heads of dimension D_head, scans all H heads concurrently
    via the fused Triton kernel, and projects back to d_model.
    """
    def __init__(
        self,
        d_model: int,
        num_heads: int = 4,
        preset: str = "decayotton_orthoplex",
        gamma_s: float = 0.999,
        gamma_a: float = 0.990,
    ):
        super().__init__()
        assert d_model % num_heads == 0, "d_model must be divisible by num_heads"
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_head = d_model // num_heads
        self.gamma_s = gamma_s
        self.gamma_a = gamma_a

        self.W_u = nn.Linear(d_model, d_model, bias=False)
        self.W_v = nn.Linear(d_model, d_model, bias=False)
        self.W_q = nn.Linear(d_model, d_model, bias=False)
        self.W_gate = nn.Linear(d_model, d_model, bias=True)
        self.out_proj = nn.Linear(d_model, d_model, bias=False)

        self.connector = ConfigurablePolytopeConnector(d_model, preset=preset)
        nn.init.zeros_(self.W_gate.bias)

    def forward(self, x: torch.Tensor, use_triton: bool = True) -> torch.Tensor:
        B, T, D = x.shape
        H = self.num_heads
        d = self.d_head

        # 1. Linear projections
        U = self.W_u(x).view(B, T, H, d).transpose(1, 2)  # [B, H, T, d]
        V = self.W_v(x).view(B, T, H, d).transpose(1, 2)  # [B, H, T, d]
        Q = self.W_q(x).view(B, T, H, d).transpose(1, 2)  # [B, H, T, d]

        # 2. Reshape for batched Triton execution: (B * H, T, d)
        U_flat = U.reshape(B * H, T, d)
        V_flat = V.reshape(B * H, T, d)
        Q_flat = Q.reshape(B * H, T, d)

        # 3. Polytope modulation (broadcast across heads)
        grid_mod = self.connector.compute_grid_modulation(x).squeeze(-1).squeeze(-1)  # [B, T]
        grid_mod_flat = grid_mod.unsqueeze(1).expand(B, H, T).reshape(B * H, T)

        # 4. Fused SAVG Scan across all heads
        out_scan = SAVGScanFunction.apply(
            U_flat, V_flat, Q_flat, grid_mod_flat, self.gamma_s, self.gamma_a, use_triton
        )  # [B * H, T, d]

        # 5. Restore multi-head structure: [B, T, H * d] = [B, T, D]
        out_scan = out_scan.view(B, H, T, d).transpose(1, 2).reshape(B, T, D)

        # 6. Gated projection
        gate = torch.sigmoid(self.W_gate(x))
        return self.out_proj(gate * out_scan)

    def init_state(self, batch_size: int, device: torch.device, dtype=torch.float32):
        """Initializes constant recurrent state tensors across all heads: [B, H, d, d]."""
        H, d = self.num_heads, self.d_head
        S = torch.zeros(batch_size, H, d, d, device=device, dtype=dtype)
        A = torch.zeros(batch_size, H, d, d, device=device, dtype=dtype)
        return S, A

    def step(
        self,
        x_t: torch.Tensor,
        state: tuple[torch.Tensor, torch.Tensor],
        use_triton: bool = True
    ) -> tuple[torch.Tensor, tuple[torch.Tensor, torch.Tensor]]:
        """O(1) Streaming Multi-Head Autoregressive Step."""
        B, D = x_t.shape
        H, d = self.num_heads, self.d_head
        S_prev, A_prev = state  # [B, H, d, d]

        u_t = self.W_u(x_t).view(B, H, d)
        v_t = self.W_v(x_t).view(B, H, d)
        q_t = self.W_q(x_t).view(B, H, d)
        g_t = self.connector.compute_grid_modulation(x_t.unsqueeze(1)).squeeze(1).squeeze(-1)  # [B, 1]

        # PyTorch multi-head recurrence step
        sym_inc = 0.5 * (torch.matmul(u_t.unsqueeze(-1), v_t.unsqueeze(-2)) + torch.matmul(v_t.unsqueeze(-1), u_t.unsqueeze(-2)))
        anti_inc = 0.5 * (torch.matmul(u_t.unsqueeze(-1), v_t.unsqueeze(-2)) - torch.matmul(v_t.unsqueeze(-1), u_t.unsqueeze(-2)))
        g_broadcast = g_t.unsqueeze(-1).unsqueeze(-1)  # [B, 1, 1, 1]

        S_next = self.gamma_s * S_prev + g_broadcast * sym_inc
        A_next = self.gamma_a * A_prev + g_broadcast * anti_inc
        net_state = S_next + A_next  # [B, H, d, d]

        out_t = torch.matmul(net_state, q_t.unsqueeze(-1)).squeeze(-1)  # [B, H, d]
        out_t = out_t.view(B, D)

        gate_t = torch.sigmoid(self.W_gate(x_t))
        return self.out_proj(gate_t * out_t), (S_next, A_next)
