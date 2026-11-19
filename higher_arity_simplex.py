"""
higher_arity_simplex.py
Implements True Higher-Order Simplex Binding (Arity m = 3 and m = 4).
Couples multi-token interactions over simplex hyperfaces:
- Arity-3 (2-faces / triangles): Couples (Subject, Predicate, Object) via 3-way outer product
  with Canonical Polyadic (CP) / Tucker rank factorization to maintain linear O(N) complexity.
- Arity-4 (3-faces / tetrahedra): Couples (Subject, Predicate, Object, Context) over 3-simplex cells.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class HigherAritySimplexBinding(nn.Module):
    """
    Arity-3 and Arity-4 Simplex Hyperface Interaction Module.
    Uses CP rank factorization to avoid O(d^3) or O(d^4) parameter explosion.
    
    T(x, y, z) = sum_{r=1}^R [ w_r · (U_r x) ⊙ (V_r y) ⊙ (W_r z) ]
    """
    def __init__(
        self,
        d_model: int,
        arity: int = 3,
        rank: int = 16,
        num_corners: int = 10, # Decayotton Simplex default
    ):
        super().__init__()
        assert arity in (3, 4), "Supported arities are 3 (triplets) or 4 (quadlets)"
        self.d_model = d_model
        self.arity = arity
        self.rank = rank

        # CP Factor projection matrices for each interacting slot
        self.projections = nn.ModuleList([
            nn.Linear(d_model, rank, bias=False) for _ in range(arity)
        ])

        # Core tensor / hyperface weights: R x d_model
        self.core_weight = nn.Parameter(torch.randn(rank, d_model) / math.sqrt(rank))

        # Simplex landmark projector
        self.corners = nn.Parameter(torch.randn(num_corners, d_model) / math.sqrt(d_model))
        # Hyperface interaction tensor over simplex vertices
        if arity == 3:
            # 2-faces (triangles) over simplex vertices
            self.face_weights = nn.Parameter(torch.randn(num_corners, num_corners, num_corners) * 0.01)
        else:
            # 3-faces (tetrahedra) over simplex vertices (factorized)
            self.face_factor = nn.Parameter(torch.randn(num_corners, rank) * 0.02)

        self.out_proj = nn.Linear(d_model, d_model, bias=False)

    def forward(self, tokens: list[torch.Tensor]) -> torch.Tensor:
        """
        Args:
            tokens: List of tensors [X_1, X_2, ..., X_m], each [Batch, SeqLen, d_model]
        Returns:
            bound_state: [Batch, SeqLen, d_model]
        """
        assert len(tokens) == self.arity, f"Expected {self.arity} token streams, got {len(tokens)}"

        # 1. Project tokens onto CP factor rank spaces: [B, T, R]
        projected = [proj(t) for proj, t in zip(self.projections, tokens)]

        # 2. Hadamard product in rank-R space: ⊙_i (W_i X_i)
        hadamard_rank = projected[0]
        for p in projected[1:]:
            hadamard_rank = hadamard_rank * p  # [B, T, R]

        # 3. Simplex Hyperface Modulation
        if self.arity == 3:
            c1 = F.softmax(torch.matmul(tokens[0], self.corners.T), dim=-1)
            c2 = F.softmax(torch.matmul(tokens[1], self.corners.T), dim=-1)
            c3 = F.softmax(torch.matmul(tokens[2], self.corners.T), dim=-1)
            # Contract hyperface weights: sum_ijk (c1_i * c2_j * c3_k * Face_ijk)
            face_mod = torch.einsum("bti,btj,btk,ijk->bt", c1, c2, c3, self.face_weights)
            hadamard_rank = hadamard_rank * (1.0 + face_mod.unsqueeze(-1))
        else:
            # Factorized 4-way face modulation using primary anchor coordinates
            anchor_coords = F.softmax(torch.matmul(tokens[0], self.corners.T), dim=-1)  # [B, T, K]
            face_mod = torch.matmul(anchor_coords, self.face_factor)  # [B, T, R]
            hadamard_rank = hadamard_rank * (1.0 + face_mod)

        # 4. Reconstruct to embedding dimension via core weights
        # [B, T, R] x [R, d_model] -> [B, T, d_model]
        out = torch.matmul(hadamard_rank, self.core_weight)
        return self.out_proj(out)
