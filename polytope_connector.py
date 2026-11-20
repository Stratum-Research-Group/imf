"""
polytope_connector.py
Configurable Higher-Dimensional Polytope Connector & Virtual Grid.
Supports:
  1. Simplex (D-simplex -> D + 1 vertices)
  2. Orthoplex / Cross-polytope (D-orthoplex -> 2D vertices with antipodal phase pairs)
  3. Hypercube / Factorized Coset (2^D vertices via Lean-style XOR-coset factorization)

Preset configurations included:
  - 'tetrahedron' (3-simplex, 4 vertices - original baseline)
  - 'enneazetton_simplex' (9D simplex, 10 vertices)
  - 'enneazetton_orthoplex' (9D orthoplex, 18 vertices)
  - 'decayotton_simplex' (10D simplex, 11 vertices)
  - 'decayotton_orthoplex' (10D orthoplex, 20 vertices)
  - 'hendecaxennon_simplex' (11D simplex, 12 vertices)
  - 'hendecaxennon_orthoplex' (11D orthoplex, 22 vertices)
"""

import math
from typing import Literal, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

PolytopeFamily = Literal["simplex", "orthoplex", "hypercube_factorized"]

POLYTOPE_PRESETS = {
    "tetrahedron": {"dimension": 3, "family": "simplex"},           # 4 vertices
    "enneazetton_simplex": {"dimension": 9, "family": "simplex"},     # 10 vertices
    "enneazetton_orthoplex": {"dimension": 9, "family": "orthoplex"}, # 18 vertices
    "decayotton_simplex": {"dimension": 10, "family": "simplex"},    # 11 vertices
    "decayotton_orthoplex": {"dimension": 10, "family": "orthoplex"},# 20 vertices
    "hendecaxennon_simplex": {"dimension": 11, "family": "simplex"}, # 12 vertices
    "hendecaxennon_orthoplex": {"dimension": 11, "family": "orthoplex"}, # 22 vertices
}


class ConfigurablePolytopeConnector(nn.Module):
    """
    Configurable Landmark Connector Layer mapping continuous embeddings x in R^d
    onto high-dimensional regular polytopes.
    """
    def __init__(
        self,
        d_model: int,
        dimension: int = 10,
        family: PolytopeFamily = "simplex",
        preset: Optional[str] = None,
        temperature: float = 1.0,
        factor_rank: Optional[int] = None,
    ):
        super().__init__()
        if preset is not None:
            if preset not in POLYTOPE_PRESETS:
                raise ValueError(f"Unknown preset '{preset}'. Choose from {list(POLYTOPE_PRESETS.keys())}")
            cfg = POLYTOPE_PRESETS[preset]
            self.dimension = cfg["dimension"]
            self.family = cfg["family"]
        else:
            self.dimension = dimension
            self.family = family

        self.d_model = d_model
        self.temperature = temperature
        self.factor_rank = factor_rank

        # Determine vertex count K based on polytope geometry
        if self.family == "simplex":
            # D-simplex has D + 1 vertices
            self.num_vertices = self.dimension + 1
            self.corners = nn.Parameter(torch.randn(self.num_vertices, d_model) / math.sqrt(d_model))
            if factor_rank is not None and factor_rank < self.num_vertices:
                # Factorized low-rank grid: W = U @ V (O(K * r) instead of O(K^2))
                self.grid_u = nn.Parameter(torch.randn(self.num_vertices, factor_rank) * 0.02)
                self.grid_v = nn.Parameter(torch.randn(factor_rank, self.num_vertices) * 0.02)
                self.grid_weight = None
            else:
                self.grid_weight = nn.Parameter(torch.randn(self.num_vertices, self.num_vertices) * 0.02)
                self.grid_u = None
                self.grid_v = None

        elif self.family == "orthoplex":
            # D-orthoplex (cross-polytope) has 2 * D antipodal vertices (+e_i, -e_i)
            self.num_axes = self.dimension
            self.num_vertices = 2 * self.dimension
            # Only parameterize D independent axes; the other D are exact antipodal negations
            self.axes = nn.Parameter(torch.randn(self.num_axes, d_model) / math.sqrt(d_model))
            if factor_rank is not None and factor_rank < self.num_vertices:
                self.grid_u = nn.Parameter(torch.randn(self.num_vertices, factor_rank) * 0.02)
                self.grid_v = nn.Parameter(torch.randn(factor_rank, self.num_vertices) * 0.02)
                self.grid_weight = None
            else:
                self.grid_weight = nn.Parameter(torch.randn(self.num_vertices, self.num_vertices) * 0.02)
                self.grid_u = None
                self.grid_v = None

        elif self.family == "hypercube_factorized":
            # D-hypercube has 2^D vertices, but factorized into D binary coordinates
            self.num_vertices = 1 << self.dimension
            self.basis_projections = nn.Linear(d_model, self.dimension, bias=False)
            # Factorized diagonal + interaction weights (O(D^2) instead of 2^D x 2^D)
            self.factor_weight = nn.Parameter(torch.randn(self.dimension, self.dimension) * 0.02)
        else:
            raise ValueError(f"Unsupported family: {self.family}")

    def get_coordinates(self, x: torch.Tensor) -> torch.Tensor:
        """
        Computes barycentric/simplex coordinates w(x).
        Args:
            x: [Batch, SeqLen, d_model]
        Returns:
            coords: [Batch, SeqLen, num_vertices]
        """
        if self.family == "simplex":
            logits = torch.matmul(x, self.corners.T) / self.temperature
            return F.softmax(logits, dim=-1)

        elif self.family == "orthoplex":
            # Project onto D axes
            proj = torch.matmul(x, self.axes.T) / self.temperature # [B, T, D]
            # Construct antipodal vertices: [proj, -proj]
            antipodal_logits = torch.cat([proj, -proj], dim=-1) # [B, T, 2D]
            return F.softmax(antipodal_logits, dim=-1)

        elif self.family == "hypercube_factorized":
            # Continuous relaxation of D-bit boolean hypercube coordinates: in (-1, 1)^D
            return torch.tanh(self.basis_projections(x))

    def compute_grid_modulation(self, x: torch.Tensor) -> torch.Tensor:
        """
        Evaluates the virtual grid interaction scalar modulation (1 + w(x)^T G w(x)).
        Args:
            x: [Batch, SeqLen, d_model]
        Returns:
            grid_mod: [Batch, SeqLen, 1, 1]
        """
        coords = self.get_coordinates(x)
        if self.family in ("simplex", "orthoplex"):
            if self.grid_u is not None:
                # Low-rank O(K * r) contraction: (coords @ grid_u) @ (grid_v @ coords^T)
                # coords: [B, T, K]
                # proj_u: [B, T, r], proj_v: [B, T, r]
                proj_u = torch.matmul(coords, self.grid_u)
                proj_v = torch.matmul(coords, self.grid_v.T)
                grid_val = (proj_u * proj_v).sum(dim=-1)  # [B, T]
            else:
                # Standard dense O(K^2) contraction
                grid_val = torch.einsum("bti,ij,btj->bt", coords, self.grid_weight, coords)
            return (1.0 + grid_val).unsqueeze(-1).unsqueeze(-1)
        else:
            # Factorized hypercube form: c(x)^T * W * c(x)
            factor_val = torch.einsum("bti,ij,btj->bt", coords, self.factor_weight, coords)
            return (1.0 + factor_val).unsqueeze(-1).unsqueeze(-1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward projection: maps embeddings x through the barycentric polytope landmark frame.
        For [..., d_model], returns barycentric coordinate projection into embedding space.
        """
        coords = self.get_coordinates(x)
        if self.family == "simplex":
            return torch.matmul(coords, self.corners)
        elif self.family == "orthoplex":
            # coords has 2D dimensions corresponding to [axes, -axes]
            antipodal_vertices = torch.cat([self.axes, -self.axes], dim=0)
            return torch.matmul(coords, antipodal_vertices)
        else:
            return torch.matmul(coords, self.basis_projections.weight)

    def extra_repr(self) -> str:
        return (
            f"dimension={self.dimension}, family='{self.family}', "
            f"num_vertices={self.num_vertices}, grid_size={self.num_vertices}x{self.num_vertices}"
            if self.family != "hypercube_factorized"
            else f"dimension={self.dimension}, family='hypercube_factorized' (implicit {1 << self.dimension} vertices)"
        )
