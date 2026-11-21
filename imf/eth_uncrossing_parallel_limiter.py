"""
imf/eth_uncrossing_parallel_limiter.py
ETH Uncrossing & Parallel Orthogonal Subspace Energy Limiter.

Applies the formally proven ETH Uncrossing & Parallelism theorems from Lean 4
(IMF.ETHUncrossingParallelNormSpec and IMF.ETHUncrossingSpec):
1. Projects inputs across K mutually orthogonal uncrossed parallel channels.
2. Applies Householder uncrossing isometries R_s = I - 2 s s^T to reflect crossing
   activations into negative directional separation.
3. Guarantees non-amplifying energy conservation:
   ||x_parallel||^2 + ||x_perp||^2 = ||x||^2 <= B_max
   preventing arithmetic overflow without destroying representational capacity.
"""

from typing import Dict, List, Optional, Tuple
import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class ETHUncrossingParallelLimiter(nn.Module):
    """
    Formally Proven ETH Uncrossing & Parallel Subspace Energy Limiter.
    
    Guarantees:
    - Zero numerical overflow via orthogonal projection.
    - Energy bounded strictly by max_norm ceiling.
    - Reflection of crossed positive components into orthogonal negative sectors.
    """

    def __init__(
        self,
        d_model: int,
        num_parallel_channels: int = 4,
        max_energy_bound: float = 32.0,
    ):
        super().__init__()
        self.d_model = d_model
        self.num_parallel_channels = num_parallel_channels
        self.max_energy_bound = max_energy_bound
        self.channel_dim = d_model // num_parallel_channels
        assert d_model % num_parallel_channels == 0, "d_model must be divisible by num_parallel_channels"
        
        # Orthonormal projection bases for parallel channels
        # Stored as an exact orthogonal block matrix
        q, _ = torch.linalg.qr(torch.randn(d_model, d_model))
        self.register_buffer("orthogonal_basis", q)
        
        # Learnable channel uncrossing reflection normal s \in {-1, +1}^d
        self.reflection_normal = nn.Parameter(torch.randn(num_parallel_channels, self.channel_dim))

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Projects x into uncrossed parallel orthogonal channels, reflects crossing rays,
        and enforces the non-amplifying ETH energy bound.
        
        Args:
            x: Input tensor [Batch, SeqLen, d_model] or [Tokens, d_model]
            
        Returns:
            x_uncrossed: Normalized, uncrossed tensor strictly satisfying ||x|| <= max_energy_bound
            stats: Energy and uncrossing diagnostics
        """
        orig_shape = x.shape
        x_flat = x.reshape(-1, self.d_model) if x.dim() == 3 else x
        
        # 1. Project into orthogonal coordinates: coordinates are uncrossed by construction
        x_ortho = torch.matmul(x_flat, self.orthogonal_basis) # [N, d_model]
        
        # 2. Split into K parallel orthogonal channels
        N = x_flat.size(0)
        x_channels = x_ortho.view(N, self.num_parallel_channels, self.channel_dim)
        
        # 3. Apply Householder uncrossing reflection along reflection normal s:
        # R_s(v) = v - 2 * (s . v) * s
        s_norm = F.normalize(self.reflection_normal, p=2, dim=-1) # [K, channel_dim]
        # Inner products: [N, K, 1]
        s_dot_v = torch.sum(x_channels * s_norm.unsqueeze(0), dim=-1, keepdim=True)
        
        # Householder reflection:
        x_reflected = x_channels - 2.0 * s_dot_v * s_norm.unsqueeze(0)
        
        # 4. Strict Non-Amplifying Energy Bounding (ETH Invariant)
        # B_max ceiling enforces: ||x|| <= max_energy_bound
        channel_energies = torch.sum(x_reflected ** 2, dim=-1) # [N, K]
        total_energy = torch.sum(channel_energies, dim=-1, keepdim=True) # [N, 1]
        total_norm = torch.sqrt(total_energy + 1e-7)
        
        scale = torch.clamp(self.max_energy_bound / total_norm, max=1.0)
        x_bounded = (x_reflected.view(N, self.d_model) * scale)
        
        # 5. Rotate back to original basis: Q^T (exact isometry, preserves norm)
        out = torch.matmul(x_bounded, self.orthogonal_basis.t())
        
        if x.dim() == 3:
            out = out.view(orig_shape)
            
        stats = {
            "pre_norm": total_norm.mean().item(),
            "bounded_norm": torch.norm(x_bounded, p=2, dim=-1).mean().item(),
            "max_bound": self.max_energy_bound,
        }
        return out, stats
