"""
omni_block.py
IMF-OmniBlock: Unified Next-Generation Hybrid Architecture for Interaction Model Foundations.

Synthesizes three core mathematical principles into a unified, high-throughput causal layer:
1. Continuous-Time Lie Group SSM on SO(d_h):
   - Fused Triton parallel associative scan in GPU registers.
   - Preserves Frobenius energy norm (||U M U^T||_F = ||M||_F) over unbounded sequence horizons.
2. Continuous Multilinear Simplex Convolution:
   - Rank-R CP tensor factorized continuous sliding window integration in log-prefix space.
   - Captures high-order ($m$-way) interaction structures in strictly O(T) compute without parameter explosion.
3. Non-Abelian SU(2) Simplicial Gauge Complex:
   - Geometric Landmark Polytope (e.g. 10D Deca-yotton V=11) barycentric coordinate routing.
   - Computes Wilson loop curvature holonomy W_ijk = U_ij U_jk U_ki along 2-simplices,
     providing topological invariance under local gauge transformations and syntactic re-orderings.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint

from imf.continuous_lie_ssm import ContinuousLieGroupSSM
from imf.triton_unitary_ssm_kernel import fused_unitary_ssm_forward
from higher_arity_simplex import ContinuousSimplexConvolutionalBinding
from imf.gauge_polytope_complex import SU2GaugeSimplicialComplex
from polytope_connector import ConfigurablePolytopeConnector
from imf.nested_hypercube_cell import NestedHypercubeCell


class IMFOmniBlock(nn.Module):
    """
    Unified IMF OmniBlock.
    Integrates:
    - Long-term unitary associative memory (Lie Group SO(d_h) SSM with Triton JIT fallback)
    - Medium/Short-term high-order multilinear interactions (Continuous Simplex Convolution)
    - Structural topological curvature modulation (SU(2) Simplicial Gauge Complex over Polytopes)
    """
    def __init__(
        self,
        d_model: int = 256,
        num_heads: int = 8,
        polytope_dim: int = 10,
        polytope_family: str = "simplex",
        conv_rank: int = 64,
        conv_window: int = 8,
        use_triton_ssm: bool = True,
        use_nested_hypercube: bool = False,
        use_checkpointing: bool = False,
        dropout: float = 0.0,
    ):
        super().__init__()
        assert d_model % num_heads == 0, f"d_model ({d_model}) must be divisible by num_heads ({num_heads})"
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.polytope_dim = polytope_dim
        self.use_triton_ssm = use_triton_ssm
        self.use_nested_hypercube = use_nested_hypercube
        self.use_checkpointing = use_checkpointing

        # 1. Polytope Connector for Barycentric Simplicial Coordinates
        self.polytope_connector = ConfigurablePolytopeConnector(
            d_model=d_model,
            dimension=polytope_dim,
            family=polytope_family,
            learnable_remeshing=False,
        )
        self.num_vertices = self.polytope_connector.num_vertices

        # 2. Continuous-Time Lie Group SSM on SO(d_h)
        self.ssm = ContinuousLieGroupSSM(d_model=d_model, num_heads=num_heads)

        # 3. Continuous Simplex Multilinear Convolution
        self.simplex_conv = ContinuousSimplexConvolutionalBinding(
            d_model=d_model,
            rank=conv_rank,
            default_window=conv_window,
        )

        # 4. Non-Abelian SU(2) Gauge Complex with Wilson Loop Holonomy
        self.gauge_complex = SU2GaugeSimplicialComplex(
            num_vertices=self.num_vertices,
            d_model=d_model,
        )

        # 5. Optional Recursive Nested Hypercube Cell Decompositions
        if self.use_nested_hypercube:
            self.nested_hypercube = NestedHypercubeCell(
                d_model=d_model,
                hypercube_dim=4,
                recursion_depth=3,
            )
            n_branches = 4
        else:
            self.nested_hypercube = None
            n_branches = 3

        # Gated Multi-Modal Integration & Feedforward Fusion
        self.norm1 = nn.RMSNorm(d_model)
        self.norm2 = nn.RMSNorm(d_model)
        
        self.gate_proj = nn.Linear(d_model, n_branches * d_model, bias=True)
        self.branch_fusion = nn.Linear(n_branches * d_model, d_model, bias=False)

        # Feedforward sub-layer (SwiGLU)
        ffn_dim = int(d_model * 8 / 3)
        self.ffn_w1 = nn.Linear(d_model, ffn_dim, bias=False)
        self.ffn_w2 = nn.Linear(d_model, ffn_dim, bias=False)
        self.ffn_w3 = nn.Linear(ffn_dim, d_model, bias=False)
        self.dropout = nn.Dropout(dropout)

    def forward_ssm(self, x_norm: torch.Tensor) -> torch.Tensor:
        """
        Executes Lie Group SO(d_h) SSM forward pass.
        Uses Fused Triton associative kernel if input is on CUDA and D is supported,
        otherwise falls back to sequential autograd-compatible PyTorch scan.
        """
        B, T, D = x_norm.shape
        H = self.num_heads
        d_h = self.head_dim

        # Project Q, K, V
        q = self.ssm.q_proj(x_norm).view(B, T, H, d_h).transpose(1, 2).contiguous() # [B, H, T, d_h]
        k = self.ssm.k_proj(x_norm).view(B, T, H, d_h).transpose(1, 2).contiguous()
        v = self.ssm.v_proj(x_norm).view(B, T, H, d_h).transpose(1, 2).contiguous()

        U = self.ssm.get_orthogonal_rotator() # [H, d_h, d_h]

        if self.use_triton_ssm and x_norm.is_cuda and (d_h in (8, 16, 32, 64)) and not torch.is_grad_enabled():
            # Fast inference path via register-tiled Triton kernel
            out_ssm = fused_unitary_ssm_forward(q, k, v, U) # [B, H, T, d_h]
            out_ssm = out_ssm.transpose(1, 2).contiguous().view(B, T, D)
            return self.ssm.out_proj(out_ssm)
        else:
            # Training / autograd / CPU path via PyTorch scan
            U_exp = U.unsqueeze(0)             # [1, H, d_h, d_h]
            U_T_exp = U.transpose(-1, -2).unsqueeze(0)

            M = torch.zeros(B, H, d_h, d_h, device=x_norm.device, dtype=x_norm.dtype)
            outputs = []

            for t in range(T):
                q_t = q[:, :, t, :].unsqueeze(-1)  # [B, H, d_h, 1]
                k_t = k[:, :, t, :].unsqueeze(-1)
                v_t = v[:, :, t, :].unsqueeze(-1)

                W_t = torch.matmul(v_t, k_t.transpose(-1, -2)) - torch.matmul(k_t, v_t.transpose(-1, -2))
                M = torch.matmul(torch.matmul(U_exp, M), U_T_exp) + W_t

                y_t = torch.matmul(M, q_t).squeeze(-1) # [B, H, d_h]
                outputs.append(y_t)

            out_seq = torch.stack(outputs, dim=2)  # [B, H, T, d_h]
            out_seq = out_seq.transpose(1, 2).contiguous().view(B, T, D)
            return self.ssm.out_proj(out_seq)

    def _inner_forward(self, x: torch.Tensor, window: int = None) -> torch.Tensor:
        B, T, D = x.shape
        x_norm = self.norm1(x)

        # 1. Polytope barycentric projection: [B, T, V]
        coords = self.polytope_connector.get_coordinates(x_norm)

        # 2. Parallel Unified Branches:
        # Branch A: Unitary Lie SSM (lossless infinite context memory)
        y_ssm = self.forward_ssm(x_norm)

        # Branch B: Continuous multilinear simplex convolution (higher-arity tokens)
        y_conv = self.simplex_conv(x_norm, window=window)

        # Branch C: Non-Abelian SU(2) Wilson loop curvature holonomy
        y_gauge = self.gauge_complex.compute_triangle_curvature(coords)

        # 3. Dynamic Branch Gating & Multi-Modal Interaction
        if self.use_nested_hypercube and self.nested_hypercube is not None:
            y_nested = self.nested_hypercube(x_norm)
            gates = torch.sigmoid(self.gate_proj(x_norm)) # [B, T, 4 * D]
            g_ssm, g_conv, g_gauge, g_nested = torch.chunk(gates, 4, dim=-1)
            fused_branches = torch.cat([
                g_ssm * y_ssm,
                g_conv * y_conv,
                g_gauge * y_gauge,
                g_nested * y_nested,
            ], dim=-1)
        else:
            gates = torch.sigmoid(self.gate_proj(x_norm)) # [B, T, 3 * D]
            g_ssm, g_conv, g_gauge = torch.chunk(gates, 3, dim=-1)
            fused_branches = torch.cat([
                g_ssm * y_ssm,
                g_conv * y_conv,
                g_gauge * y_gauge,
            ], dim=-1)

        attn_out = self.branch_fusion(fused_branches)
        x = x + self.dropout(attn_out)

        # 4. Feedforward SwiGLU Block
        x_ffn_norm = self.norm2(x)
        w1 = self.ffn_w1(x_ffn_norm)
        w2 = self.ffn_w2(x_ffn_norm)
        ffn_out = self.ffn_w3(F.silu(w1) * w2)
        x = x + self.dropout(ffn_out)

        return x

    def forward(self, x: torch.Tensor, window: int = None) -> torch.Tensor:
        """
        Forward pass through IMF OmniBlock with optional activation checkpointing.
        Args:
            x: [Batch, SeqLen, d_model]
            window: Optional window size override for continuous simplex convolution
        Returns:
            out: [Batch, SeqLen, d_model]
        """
        if self.use_checkpointing and self.training:
            # Gradient activation checkpointing avoids caching intermediate activations
            return checkpoint(self._inner_forward, x, window, use_reentrant=False)
        return self._inner_forward(x, window)
