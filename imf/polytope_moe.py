"""
Polytope Mixture of Experts (MoPE) for Interaction Model Foundations (IMF).

This module implements a geometrically grounded Sparse Mixture-of-Experts architecture:
1. Polytope Centroid Anchoring: Each expert is assigned a canonical vertex on a polytope
   (e.g., in Euclidean or Poincaré Hyperbolic space H^d).
2. Geodesic / Barycentric Routing: Token representations are mapped into coordinates,
   and expert gating logits are derived from metric distances to the domain centroids.
3. Domain Specialization:
   - Expert 0: Systems & Algorithmic Code (Python, Rust, C)
   - Expert 1: Formal Proofs & Logic (Lean 4, Propositional Logic)
   - Expert 2: Symbolic Mathematics & Arithmetic Chains (GSM8k, Algebra)
   - Expert 3: Natural Language Discourse & Syntactic Grammar
4. Top-k Sparsity with Differentiable Load Balancing.
"""

from typing import Dict, List, Optional, Tuple
import math
import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from polytope_connector import ConfigurablePolytopeConnector
except ImportError:
    from imf.polytope_connector import ConfigurablePolytopeConnector

try:
    from imf.hyperbolic_polytope_tiling import HyperbolicPolytopeTiling
except ImportError:
    from hyperbolic_polytope_tiling import HyperbolicPolytopeTiling


class PolytopeExpert(nn.Module):
    """Feedforward domain expert with gated GLU (SwiGLU) activation."""
    def __init__(self, d_model: int, d_ff: int, dropout: float = 0.0, domain_name: str = "general"):
        super().__init__()
        self.domain_name = domain_name
        self.w_gate = nn.Linear(d_model, d_ff, bias=False)
        self.w_up = nn.Linear(d_model, d_ff, bias=False)
        self.w_down = nn.Linear(d_ff, d_model, bias=False)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # SwiGLU: (swish(w_gate(x)) * w_up(x))
        gate = F.silu(self.w_gate(x))
        up = self.w_up(x)
        out = self.w_down(self.dropout(gate * up))
        return out


class PolytopeMixtureOfExperts(nn.Module):
    """
    Geometric Polytope Mixture of Experts (MoPE).
    
    Tokens are routed to domain experts based on their geometric barycentric 
    or hyperbolic proximity to polytope vertex centroids.
    """
    def __init__(
        self,
        d_model: int,
        num_experts: int = 4,
        top_k: int = 2,
        d_ff_expert: Optional[int] = None,
        dropout: float = 0.0,
        polytope_dim: int = 3,
        use_hyperbolic: bool = True,
        curvature: float = 1.0,
        balance_loss_weight: float = 0.01,
        expert_domains: Optional[List[str]] = None,
    ):
        super().__init__()
        self.d_model = d_model
        self.num_experts = num_experts
        self.top_k = min(top_k, num_experts)
        self.use_hyperbolic = use_hyperbolic
        self.balance_loss_weight = balance_loss_weight
        d_ff = d_ff_expert if d_ff_expert is not None else 4 * d_model

        if expert_domains is None:
            self.expert_domains = [
                "systems_code",       # Python, Rust, C
                "formal_logic_lean4", # Lean 4, formal proof verification
                "symbolic_math",      # Multi-step arithmetic, symbolic algebra
                "natural_discourse",  # Grammar, linguistic comprehension
            ][:num_experts]
            while len(self.expert_domains) < num_experts:
                self.expert_domains.append(f"domain_{len(self.expert_domains)}")
        else:
            self.expert_domains = expert_domains

        # 1. Polytope geometric router
        if use_hyperbolic:
            self.router = HyperbolicPolytopeTiling(
                d_model=d_model,
                num_vertices=num_experts,
                temperature=curvature,
            )
            router_dim = self.router.num_vertices
        else:
            self.router = ConfigurablePolytopeConnector(
                d_model=d_model,
                dimension=polytope_dim,
                family="simplex" if num_experts <= 4 else "hypercube",
            )
            router_dim = self.router.num_vertices

        # Project router vertices to expert logits if dimensions differ
        if router_dim != num_experts:
            self.coord_to_expert = nn.Linear(router_dim, num_experts, bias=False)
        else:
            self.coord_to_expert = nn.Identity()

        # Learnable temperature for sharp vs soft routing
        self.temperature = nn.Parameter(torch.ones(1) * 1.0)

        # 2. Domain Experts
        self.experts = nn.ModuleList([
            PolytopeExpert(d_model=d_model, d_ff=d_ff, dropout=dropout, domain_name=name)
            for name in self.expert_domains
        ])

    def forward(
        self, x: torch.Tensor
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Args:
            x: [Batch, SeqLen, d_model]
        Returns:
            out: [Batch, SeqLen, d_model]
            aux_info: Dict containing routing_weights, load_balance_loss, expert_counts
        """
        B, T, D = x.shape
        x_flat = x.reshape(B * T, D)

        # 1. Compute Geometric Barycentric / Hyperbolic Coordinates
        if self.use_hyperbolic:
            coords = self.router.get_coordinates(x) # [B, T, V]
        else:
            coords = self.router.get_coordinates(x) # [B, T, V]
        coords_flat = coords.reshape(B * T, -1)

        # 2. Derive Expert Logits from Geometric Proximity
        expert_logits = self.coord_to_expert(coords_flat) / torch.clamp(self.temperature, min=0.01) # [B*T, num_experts]
        routing_probs = F.softmax(expert_logits, dim=-1) # [B*T, num_experts]

        # 3. Top-k Selection
        topk_weights, topk_indices = torch.topk(routing_probs, self.top_k, dim=-1) # [B*T, top_k]
        topk_weights = topk_weights / torch.clamp(topk_weights.sum(dim=-1, keepdim=True), min=1e-6)

        # 4. Sparse Routing Computation
        out_flat = torch.zeros_like(x_flat)
        for k_idx in range(self.top_k):
            expert_idx = topk_indices[:, k_idx] # [B*T]
            weight = topk_weights[:, k_idx].unsqueeze(-1) # [B*T, 1]

            for e_idx, expert in enumerate(self.experts):
                mask = (expert_idx == e_idx)
                if mask.any():
                    tokens_for_expert = x_flat[mask]
                    expert_output = expert(tokens_for_expert)
                    out_flat[mask] += weight[mask] * expert_output

        out = out_flat.reshape(B, T, D)

        # 5. Differentiable Load Balancing Loss (Switch Transformer / GShard formulation)
        # Fraction of routing weight dispatched to each expert
        f_dispatch = routing_probs.mean(dim=0) # [num_experts]
        # Frequency of top-1 expert selection
        top1_indices = topk_indices[:, 0]
        one_hot_top1 = F.one_hot(top1_indices, num_classes=self.num_experts).float()
        f_selected = one_hot_top1.mean(dim=0) # [num_experts]
        balance_loss = self.balance_loss_weight * self.num_experts * torch.sum(f_dispatch * f_selected)

        aux_info = {
            "load_balance_loss": balance_loss,
            "routing_probs": routing_probs.reshape(B, T, self.num_experts),
            "topk_indices": topk_indices.reshape(B, T, self.top_k),
            "topk_weights": topk_weights.reshape(B, T, self.top_k),
            "expert_dispatch_fraction": f_dispatch.detach(),
            "expert_domains": self.expert_domains,
        }

        return out, aux_info
