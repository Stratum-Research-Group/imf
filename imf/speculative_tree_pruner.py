"""
imf/speculative_tree_pruner.py
Asynchronous Speculative Tree Candidate Pruner with Early Stopping.
Prunes unviable branch paths in speculative decoding trees using dynamic
exponential depth decay confidence thresholds:
    tau_b = alpha_accept * exp(-depth / lambda)
Author: Nicholas Charles Mynhardt (Stratum Research Group)
"""

import math
import torch
from typing import List, Dict, Any, Tuple


class SpeculativeTreePruner:
    def __init__(self, alpha_base: float = 0.72, lambda_decay: float = 4.0, min_prob: float = 0.05):
        self.alpha_base = alpha_base
        self.lambda_decay = lambda_decay
        self.min_prob = min_prob

    def prune_speculative_tree(
        self,
        token_tree: torch.Tensor,       # [B, Num_Nodes] token IDs
        branch_probs: torch.Tensor,     # [B, Num_Nodes] cumulative log-probs or probs
        node_depths: torch.Tensor       # [B, Num_Nodes] depth per node
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Returns mask of surviving nodes and count of pruned tokens per sequence.
        """
        B, N = token_tree.shape
        thresholds = self.alpha_base * torch.exp(-node_depths.float() / self.lambda_decay)
        thresholds = torch.clamp(thresholds, min=self.min_prob)

        # Active mask: nodes that meet or exceed the branch confidence threshold
        surviving_mask = branch_probs >= thresholds
        # Root node (depth 0) is always preserved
        surviving_mask = surviving_mask | (node_depths == 0)

        pruned_counts = (~surviving_mask).sum(dim=-1)
        return surviving_mask, pruned_counts


if __name__ == "__main__":
    pruner = SpeculativeTreePruner()
    tokens = torch.randint(0, 1000, (2, 16))
    depths = torch.tensor([[0, 1, 1, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4],
                           [0, 1, 1, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4]])
    probs = torch.tensor([[1.0, 0.8, 0.6, 0.7, 0.3, 0.1, 0.5, 0.2, 0.05, 0.02, 0.4, 0.1, 0.02, 0.01, 0.0, 0.0],
                          [1.0, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45, 0.4, 0.35, 0.3, 0.25, 0.2]])

    mask, pruned = pruner.prune_speculative_tree(tokens, probs, depths)
    print(f"Surviving nodes: {mask.sum(dim=-1).tolist()} | Pruned tokens: {pruned.tolist()}")
