"""
imf/matryoshka_cross_polytope_router.py
Russian-Doll (Matryoshka) Nested Cross-Polytope & Hyperspace Router.

Allows continual recursive expansion of virtual expert subspaces into hyperspace cells
analogous to nesting Russian dolls (Matryoshka cells).
At each hierarchy level k, input tokens are projected into a D-dimensional cross-polytope
(orthoplex with 2D vertices) or dual hypercube cell (2^D facets), localizing activations
into recursive orthant chambers with exact parameter-complete linear footprint.
"""

from typing import Dict, List, Optional, Tuple
import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class MatryoshkaCrossPolytopeRouter(nn.Module):
    """
    Arbitrary-D Recursive Nested Cross-Polytope Router.
    
    In dimension D, a Cross-Polytope (Orthoplex) has 2*D vertices at ±e_i along coordinate axes.
    Its regular dual is the D-hypercube with 2^D vertices / orthants.
    
    By nesting cross-polytope cells to depth K (Russian-Doll factorization):
    - Virtual routing capacity: (2^D)^K chambers or (2*D)^K path combinations.
    - Physical parameter footprint: Only K * (2 * D * d_model) parameters, strictly linear!
    """

    def __init__(
        self,
        d_model: int,
        dim_polytope: int = 4,
        nesting_depth: int = 3,
        scale_decay: float = 0.5,
    ):
        super().__init__()
        self.d_model = d_model
        self.dim_polytope = dim_polytope
        self.nesting_depth = nesting_depth
        self.scale_decay = scale_decay
        
        # 2 * dim_polytope polar vertices per level
        self.num_vertices_per_level = 2 * dim_polytope
        
        # Linear projection bases for each nested Russian-doll level
        # Level 0 is the outermost macro-hyperspace shell; Level K-1 is the finest micro-cell
        self.level_projections = nn.ParameterList([
            nn.Parameter(torch.empty(self.num_vertices_per_level, d_model))
            for _ in range(nesting_depth)
        ])
        
        # Learnable scale factors for each shell
        self.shell_scales = nn.Parameter(
            torch.tensor([scale_decay ** k for k in range(nesting_depth)], dtype=torch.float32)
        )
        
        self.reset_parameters()

    def reset_parameters(self):
        """Initialize projection vectors along orthogonal axes (Cross-Polytope polar vertices)."""
        for k, proj in enumerate(self.level_projections):
            # Generate orthogonal axes: e_0, -e_0, e_1, -e_1, ...
            # Project random orthogonal basis of dimension D into d_model
            q, _ = torch.linalg.qr(torch.randn(self.d_model, self.dim_polytope))
            # q shape: [d_model, dim_polytope] -> basis vectors along rows
            basis = q.t()  # [dim_polytope, d_model]
            
            # Form cross-polytope vertices: [+e_i, -e_i]
            vertices = torch.empty(self.num_vertices_per_level, self.d_model)
            for i in range(self.dim_polytope):
                vertices[2 * i] = basis[i]
                vertices[2 * i + 1] = -basis[i]
            
            with torch.no_grad():
                proj.copy_(vertices * (self.scale_decay ** k))

    @property
    def virtual_chamber_capacity(self) -> int:
        """Total virtual chamber capacity: (2^D)^K cells."""
        return (2 ** self.dim_polytope) ** self.nesting_depth

    @property
    def total_polar_vertices(self) -> int:
        """Total polar vertices across all nested shells."""
        return self.nesting_depth * self.num_vertices_per_level

    def forward(
        self, x: torch.Tensor, top_k: int = 1
    ) -> Tuple[torch.Tensor, torch.Tensor, List[torch.Tensor]]:
        """
        Forward hierarchical recursive routing through Russian-Doll cross-polytope cells.
        
        Args:
            x: Input tensor [batch_size, seq_len, d_model] or [tokens, d_model]
            top_k: Number of highest-affinity virtual path selections
            
        Returns:
            routing_weights: Combined path affinity weights
            virtual_cell_ids: Integer indices of the selected virtual hypercells
            level_affinities: List of affinity logits at each nesting level
        """
        orig_shape = x.shape
        if x.dim() == 3:
            B, S, D = x.shape
            x_flat = x.reshape(B * S, D)
        else:
            x_flat = x
            
        N = x_flat.size(0)
        
        # Residual input as we zoom in through nesting layers
        residual = x_flat
        level_affinities = []
        accumulated_indices = torch.zeros(N, dtype=torch.long, device=x.device)
        
        # Track path affinity
        path_log_probs = torch.zeros(N, device=x.device)
        
        for k in range(self.nesting_depth):
            proj = self.level_projections[k]  # [2 * dim_polytope, d_model]
            scale = self.shell_scales[k]
            
            # Normalize projection to unit sphere for pure directional cross-polytope alignment
            norm_proj = F.normalize(proj, p=2, dim=-1)
            norm_res = F.normalize(residual, p=2, dim=-1)
            
            # Compute alignment with polar vertices: [N, 2 * dim_polytope]
            logits = torch.matmul(norm_res, norm_proj.t()) / math.sqrt(self.dim_polytope)
            level_affinities.append(logits)
            
            # Select nearest cross-polytope polar vertex
            best_vertex = torch.argmax(logits, dim=-1)  # [N]
            
            # Accumulate hierarchical virtual cell ID:
            # cell_id = sum_{k=0}^{K-1} vertex_k * (2*D)^{K - 1 - k}
            multiplier = self.num_vertices_per_level ** (self.nesting_depth - 1 - k)
            accumulated_indices += best_vertex * multiplier
            
            # Update path log-probabilities
            probs = F.softmax(logits, dim=-1)
            selected_probs = probs.gather(-1, best_vertex.unsqueeze(-1)).squeeze(-1)
            path_log_probs = path_log_probs + torch.log(selected_probs + 1e-9)
            
            # Deflate residual along the selected polar vertex direction (zoom into sub-cell)
            chosen_vector = norm_proj[best_vertex]  # [N, d_model]
            projection_length = (residual * chosen_vector).sum(dim=-1, keepdim=True)
            residual = residual - scale * projection_length * chosen_vector

        routing_weights = torch.exp(path_log_probs)
        
        if x.dim() == 3:
            routing_weights = routing_weights.view(B, S)
            accumulated_indices = accumulated_indices.view(B, S)
            
        return routing_weights, accumulated_indices, level_affinities
