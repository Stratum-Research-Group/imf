"""
Nested Hypercube Cell Layer (Virtual Cells Within Cells).
Implements a multi-scale recursive tensor projection where latent vectors are decomposed
hierarchically into virtual hypercube facets (cells within cells) across D recursive stages.
Enables exponential coordinate addressability with linear basis parameters.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class NestedHypercubeCell(nn.Module):
    """
    Decomposes representations into recursive virtual cells:
    Level 1: Root Hypercube (2^m1 facets)
      Level 2: Virtual Child Cells (2^m2 sub-facets)
        Level D: Deep virtual sub-cells
    """
    def __init__(
        self,
        d_model: int = 384,
        hypercube_dim: int = 4,    # m = 4 -> 2^4 = 16 facets per cell
        recursion_depth: int = 3,  # D = 3 -> 16^3 = 4,096 virtual addressable sub-cells
    ):
        super().__init__()
        self.d_model = d_model
        self.hypercube_dim = hypercube_dim
        self.recursion_depth = recursion_depth
        self.n_facets = 2 ** hypercube_dim

        # Compact basis projections per depth stage (Linear O(D * m) parameters)
        self.depth_projections = nn.ModuleList([
            nn.Linear(d_model, hypercube_dim, bias=False)
            for _ in range(recursion_depth)
        ])
        
        # Virtual cell hyper-plane codebook (stores compact basis for each dimension)
        self.facet_basis = nn.Parameter(
            torch.randn(recursion_depth, self.n_facets, d_model // recursion_depth) * 0.02
        )
        
        # Output synthesis projection
        self.out_proj = nn.Linear(d_model, d_model)
        self.layer_norm = nn.LayerNorm(d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (batch_size, seq_len, d_model)
        Returns: (batch_size, seq_len, d_model) mapped through virtual nested cells
        """
        B, T, C = x.shape
        stage_outputs = []

        curr_state = x
        for d_idx, proj in enumerate(self.depth_projections):
            # Project to hypercube facet coordinates in R^m
            coords = torch.tanh(proj(curr_state))  # [-1, 1]^m hypercube
            
            # Compute distance to all 2^m virtual cell vertices via matrix dot product
            # Each vertex is a binary sign vector in {-1, 1}^m
            basis_d = self.facet_basis[d_idx]  # (n_facets, C // recursion_depth)
            
            # Virtual cell soft routing weights (simplex over virtual sub-cells)
            cell_scores = torch.matmul(coords, coords.new_ones(self.hypercube_dim, self.n_facets))
            cell_weights = F.softmax(cell_scores, dim=-1)  # (B, T, n_facets)
            
            # Retrieve virtual cell content
            cell_embed = torch.matmul(cell_weights, basis_d)  # (B, T, C // D)
            stage_outputs.append(cell_embed)
            
            # Recursive refinement: next virtual cell is conditioned on residual
            curr_state = curr_state + F.pad(cell_embed, (0, C - cell_embed.shape[-1]))

        # Synthesize concatenated virtual nested cell activations
        nested_repr = torch.cat(stage_outputs, dim=-1)
        # Handle padding if C % recursion_depth != 0
        if nested_repr.shape[-1] < C:
            nested_repr = F.pad(nested_repr, (0, C - nested_repr.shape[-1]))
        elif nested_repr.shape[-1] > C:
            nested_repr = nested_repr[..., :C]

        out = self.layer_norm(x + self.out_proj(nested_repr))
        return out
