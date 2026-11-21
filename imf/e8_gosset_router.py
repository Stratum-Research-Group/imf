"""
imf/e8_gosset_router.py
Gosset 4_21 / E8 Polytope Router for Dense Optimal Hyperspace Routing.

Constructs the exact 240 root vectors of the E8 root system (Gosset 4_21 uniform polytope),
achieving the mathematically proven optimal kissing number in 8-dimensional space.
Embeds the 240 E8 roots into d_model via orthogonal frame projection for optimal
angular coverage and minimum mutual coherence.
"""

from typing import Dict, List, Optional, Tuple
import itertools
import math
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def generate_e8_roots() -> torch.Tensor:
    """
    Constructs the 240 root vectors of the E8 Lie algebra (4_21 Gosset polytope).
    
    Consists of:
    1. 112 vectors: All permutations of (±1, ±1, 0, 0, 0, 0, 0, 0) -> (8 choose 2) * 4 = 112
    2. 128 vectors: (±1/2, ±1/2, ..., ±1/2) with an even number of minus signs -> 2^7 = 128
    Total = 240 vectors, each having norm sqrt(2).
    """
    roots = []
    
    # 1. 112 vectors: Permutations of (±1, ±1, 0, 0, 0, 0, 0, 0)
    for idx in itertools.combinations(range(8), 2):
        for s0, s1 in [(1.0, 1.0), (1.0, -1.0), (-1.0, 1.0), (-1.0, -1.0)]:
            vec = [0.0] * 8
            vec[idx[0]] = s0
            vec[idx[1]] = s1
            roots.append(vec)
            
    # 2. 128 vectors: (±1/2, ..., ±1/2) with even count of minus signs
    for signs in itertools.product([0.5, -0.5], repeat=8):
        minus_count = sum(1 for s in signs if s < 0)
        if minus_count % 2 == 0:
            roots.append(list(signs))
            
    roots_tensor = torch.tensor(roots, dtype=torch.float32)  # [240, 8]
    # Normalize to unit vectors
    return F.normalize(roots_tensor, p=2, dim=-1)


class E8GossetRouter(nn.Module):
    """
    E8 Gosset 4_21 Polytope Router (8-Dimensional Optimal Kissing Manifold).
    
    Maps tokens through an 8-dimensional Lie-algebraic subspace using the 240
    maximally dense equidistant kissing vertices of the E8 root lattice.
    """

    def __init__(
        self,
        d_model: int,
        num_experts: int = 16,
        top_k: int = 2,
    ):
        super().__init__()
        self.d_model = d_model
        self.num_experts = min(num_experts, 240)
        self.top_k = top_k
        
        # 8-dimensional projection frame: [d_model, 8]
        self.proj_to_8d = nn.Linear(d_model, 8, bias=False)
        
        # Fixed canonical 240 E8 roots on the 7-sphere S^7
        e8_roots = generate_e8_roots()  # [240, 8]
        self.register_buffer("e8_roots", e8_roots)
        
        # Mapping from 240 E8 roots to active expert clusters (or 1:1 if num_experts == 240)
        if self.num_experts < 240:
            # Cluster roots into num_experts evenly
            root_to_expert = torch.arange(240) % self.num_experts
            self.register_buffer("root_to_expert", root_to_expert)
        else:
            self.register_buffer("root_to_expert", torch.arange(240))
            
        self.scale = 1.0 / math.sqrt(8)
        self.reset_parameters()

    def reset_parameters(self):
        # Orthonormal initialization of projection frame
        q, _ = torch.linalg.qr(torch.randn(self.d_model, 8))
        with torch.no_grad():
            self.proj_to_8d.weight.copy_(q.t())

    def forward(
        self, x: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Routes tokens to the nearest E8 Gosset root vertices.
        
        Args:
            x: Input tensor [batch, seq_len, d_model] or [tokens, d_model]
            
        Returns:
            routing_weights: Top-k expert softmax weights [..., top_k]
            expert_indices: Top-k expert IDs [..., top_k]
            e8_logits: Full 240-vertex dot product logits [..., 240]
        """
        orig_shape = x.shape
        if x.dim() == 3:
            B, S, D = x.shape
            x_flat = x.reshape(B * S, D)
        else:
            x_flat = x
            
        # 1. Project input to 8D Lie subspace and normalize
        h8 = self.proj_to_8d(x_flat)  # [N, 8]
        h8_norm = F.normalize(h8, p=2, dim=-1)
        
        # 2. Compute inner products with 240 E8 roots: [N, 240]
        # Canonical roots are already unit normalized
        e8_logits = torch.matmul(h8_norm, self.e8_roots.t()) * self.scale
        
        # 3. Aggregate into expert cluster logits if num_experts < 240
        if self.num_experts < 240:
            # Max-pool root logits belonging to the same expert cluster
            expert_logits = torch.full(
                (x_flat.size(0), self.num_experts),
                float("-inf"),
                device=x.device,
                dtype=x.dtype,
            )
            for exp_id in range(self.num_experts):
                mask = (self.root_to_expert == exp_id)
                expert_logits[:, exp_id] = e8_logits[:, mask].max(dim=-1).values
        else:
            expert_logits = e8_logits
            
        # 4. Top-k selection
        topk_logits, topk_indices = torch.topk(expert_logits, k=self.top_k, dim=-1)
        topk_weights = F.softmax(topk_logits, dim=-1)
        
        if x.dim() == 3:
            topk_weights = topk_weights.view(B, S, self.top_k)
            topk_indices = topk_indices.view(B, S, self.top_k)
            e8_logits = e8_logits.view(B, S, 240)
            
        return topk_weights, topk_indices, e8_logits
