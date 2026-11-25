"""
imf/diagnostics/speculative_tree_telemetry.py
Multi-Branch Speculative Decoding Acceptance Rate Visualizer & Diagnostics.
Hooks into tree draft decoders and benchmarks per-depth acceptance rates,
branching efficiency, and latency profiles across token streams.
"""

import time
import math
import json
import torch
from typing import Dict, Any, List
from imf.triton_fused_tree_speculative_draft import fused_tree_speculative_draft


class SpeculativeTreeTelemetry:
    def __init__(self, num_nodes: int = 7, vocab_size: int = 32000, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        self.num_nodes = num_nodes
        self.vocab_size = vocab_size
        self.device = device
        # Topology: 1 root, 2 branch-1, 4 branch-2
        self.tree_parents = torch.tensor([-1, 0, 0, 1, 1, 2, 2], dtype=torch.int32, device=self.device)

    def evaluate_entropy_slice(self, logits: torch.Tensor) -> Dict[str, Any]:
        """
        Runs fused tree speculative draft and computes information-theoretic metrics:
        - Mean branching entropy
        - Candidate confidence distribution
        - Path acceptance probability estimate
        """
        t0 = time.perf_counter()
        candidate_tokens, path_scores, tree_mask = fused_tree_speculative_draft(logits, self.tree_parents)
        dt = time.perf_counter() - t0

        probs = torch.softmax(logits, dim=-1)
        entropy = -torch.sum(probs * torch.log(probs.clamp(min=1e-9)), dim=-1).mean().item()

        # Depth-stratified acceptance estimation
        # Root (depth 0), Nodes 1,2 (depth 1), Nodes 3..6 (depth 2)
        depth_0_conf = torch.sigmoid(path_scores[:, 0]).mean().item()
        depth_1_conf = torch.sigmoid(path_scores[:, 1:3]).mean().item()
        depth_2_conf = torch.sigmoid(path_scores[:, 3:]).mean().item()

        return {
            "num_nodes": self.num_nodes,
            "vocab_size": self.vocab_size,
            "dispatch_time_ms": round(dt * 1000.0, 3),
            "mean_entropy": round(entropy, 4),
            "depth_confidence": {
                "depth_0_root": round(depth_0_conf, 4),
                "depth_1_branches": round(depth_1_conf, 4),
                "depth_2_leaves": round(depth_2_conf, 4)
            },
            "branching_factor": 2,
            "tree_efficiency_ratio": round((1.0 + 2.0 * depth_1_conf + 4.0 * depth_2_conf) / 7.0, 3)
        }
