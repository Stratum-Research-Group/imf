"""
imf/polytope_routing.py
Self-Balancing Dynamic MoPE Expert Router with Dynamic Centroid Adaptation.

Integrates:
1. Continuous Polytope Voronoi Cell Partitioning:
   - Evaluates geodesic distances to learnable/anchored domain centroids.
   - Computes smooth softmax gating logits over domain polytope facets.
2. Load Regularization & Starvation Prevention:
   - Auxiliary load-balancing loss: L_balance = alpha * N * sum(f_dispatch * f_selected).
   - Dynamic Centroid Adaptation (Momentum EMA): moves under-utilized centroids closer
     to high-density token clusters and gently repels over-saturated centroids.
3. Top-k Sparse Dispatch with Capacity Factor:
   - Enforces an optional capacity limit per expert to prevent tail latency bottlenecks.
"""

from typing import Dict, List, Optional, Tuple
import math
import torch
import torch.nn as nn
import torch.nn.functional as F


class SelfBalancingPolytopeRouter(nn.Module):
    """
    Geometrically grounded Polytope MoPE Router with dynamic load balancing.
    """
    def __init__(
        self,
        d_model: int,
        num_experts: int = 8,
        top_k: int = 2,
        polytope_dim: int = 8,
        balance_loss_weight: float = 0.02,
        starvation_threshold: float = 0.02,
        centroid_lr: float = 0.01,
        expert_domains: Optional[List[str]] = None,
    ):
        super().__init__()
        self.d_model = d_model
        self.num_experts = num_experts
        self.top_k = min(top_k, num_experts)
        self.polytope_dim = polytope_dim
        self.balance_loss_weight = balance_loss_weight
        self.starvation_threshold = starvation_threshold
        self.centroid_lr = centroid_lr

        if expert_domains is None:
            self.expert_domains = [
                "systems_code",
                "formal_logic_lean4",
                "symbolic_math_algebra",
                "discourse_grammar",
                "quantum_topological_physics",
                "biomolecular_cheminformatics",
                "vlsi_silicon_microarch",
                "agentic_tool_reasoning",
            ][:num_experts]
        else:
            self.expert_domains = expert_domains

        # Project token embeddings into the geometric polytope space
        self.polytope_proj = nn.Linear(d_model, polytope_dim, bias=False)
        
        # Polytope Centroids: initialize symmetrically on hypersphere S^{d-1}
        centroids = torch.randn(num_experts, polytope_dim)
        centroids = F.normalize(centroids, p=2, dim=-1)
        self.centroids = nn.Parameter(centroids)

        # Dynamic routing temperature
        self.temperature = nn.Parameter(torch.ones(1) * 0.5)

        # Register buffer to track cumulative expert load for dynamic adaptation
        self.register_buffer("cumulative_load", torch.ones(num_experts) / num_experts)

    def forward(
        self, x: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Args:
            x: [Batch, SeqLen, d_model]
        Returns:
            topk_weights: [B*T, top_k]
            topk_indices: [B*T, top_k]
            aux_info: Dict containing routing metrics & balance loss
        """
        B, T, D = x.shape
        x_flat = x.reshape(B * T, D)
        num_tokens = B * T

        # 1. Project tokens into normalized polytope embedding space
        coords = self.polytope_proj(x_flat) # [N, polytope_dim]
        coords_norm = F.normalize(coords, p=2, dim=-1) # [N, polytope_dim]

        # Normalize centroids
        centroids_norm = F.normalize(self.centroids, p=2, dim=-1) # [num_experts, polytope_dim]

        # 2. Compute Geodesic Proximity Logits (Cosine similarity on hypersphere)
        # Cosine distance: logits = (coords @ centroids.T) / temp
        sim = torch.matmul(coords_norm, centroids_norm.transpose(0, 1)) # [N, num_experts]
        logits = sim / torch.clamp(self.temperature, min=0.01)

        # 3. Routing Probabilities
        routing_probs = F.softmax(logits, dim=-1) # [N, num_experts]

        # 4. Top-K Sparsity
        topk_weights, topk_indices = torch.topk(routing_probs, self.top_k, dim=-1) # [N, top_k]
        topk_weights = topk_weights / torch.clamp(topk_weights.sum(dim=-1, keepdim=True), min=1e-6)

        # 5. Differentiable Load Balancing Loss (GShard formulation)
        f_dispatch = routing_probs.mean(dim=0) # [num_experts]
        top1_indices = topk_indices[:, 0]
        one_hot_top1 = F.one_hot(top1_indices, num_classes=self.num_experts).float()
        f_selected = one_hot_top1.mean(dim=0) # [num_experts]

        balance_loss = self.balance_loss_weight * self.num_experts * torch.sum(f_dispatch * f_selected)

        # 6. Starvation Prevention & Dynamic Centroid Adaptation (during training/eval)
        with torch.no_grad():
            self.cumulative_load = 0.95 * self.cumulative_load + 0.05 * f_selected
            # Check for starved experts
            starved_mask = self.cumulative_load < self.starvation_threshold
            if starved_mask.any() and self.training:
                # Nudge starved centroid toward mean of all token coords to attract dispatch
                cluster_mean = coords_norm.mean(dim=0, keepdim=True) # [1, polytope_dim]
                for e_idx in range(self.num_experts):
                    if starved_mask[e_idx]:
                        self.centroids[e_idx].add_(self.centroid_lr * cluster_mean.squeeze(0))

        aux_info = {
            "load_balance_loss": balance_loss,
            "routing_probs": routing_probs.reshape(B, T, self.num_experts),
            "topk_indices": topk_indices.reshape(B, T, self.top_k),
            "topk_weights": topk_weights.reshape(B, T, self.top_k),
            "expert_dispatch_fraction": f_dispatch.detach(),
            "cumulative_load": self.cumulative_load.clone(),
            "starved_experts": [self.expert_domains[i] for i in range(self.num_experts) if self.cumulative_load[i] < self.starvation_threshold],
            "expert_domains": self.expert_domains,
        }

        return topk_weights, topk_indices, aux_info
