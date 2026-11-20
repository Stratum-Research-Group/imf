"""
Bidirectional Cut-Reasoning Layer for Interaction Model Foundations (IMF).

Applies the cut-factorization identity from ETH formal mathematics:
Instead of standard unidirectional autoregressive search P -> S_1 -> ... -> C,
the reasoning process is partitioned across a middle Cut Point (k / 2):
1. Forward Generator (Premise -> Intermediate State S_{cut})
2. Backward Goal Conditioned Projector (Conclusion <- Intermediate State S_{cut})
3. Cut Singlet Bilinear Matcher:
   Applies the antisymmetric singlet operator s(x, y) = x0*y1 - x1*y0 to enforce
   chirality and cancel spurious crossing paths at the meet-in-the-middle interface.
"""

from typing import Dict, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F


class BidirectionalCutReasoning(nn.Module):
    """
    Bidirectional Cut-Reasoning Module.
    Factorizes multi-step deduction across an intermediate cut point m = k / 2.
    """
    def __init__(self, d_model: int = 128, num_cuts: int = 4, dropout: float = 0.0):
        super().__init__()
        self.d_model = d_model
        self.num_cuts = num_cuts

        # Forward Premise Projector
        self.forward_proj = nn.Linear(d_model, d_model, bias=False)
        # Backward Goal / Hypothesis Projector
        self.backward_proj = nn.Linear(d_model, d_model, bias=False)

        # Antisymmetric Singlet Coupling Matrices (s_x * s_u - s_y * s_v)
        # Parameterized as skew-symmetric Lie algebra generators
        self.raw_singlet = nn.Parameter(torch.randn(num_cuts, d_model, d_model) * 0.02)
        self.gate = nn.Linear(d_model * 2, d_model)
        self.ln_cut = nn.LayerNorm(d_model)

    def forward(
        self,
        forward_states: torch.Tensor,
        backward_goals: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Args:
            forward_states: [Batch, SeqLen, d_model] (Trajectory from premise)
            backward_goals: [Batch, SeqLen, d_model] (Target hypothesis / goal constraints)
        Returns:
            verified_cut_state: [Batch, SeqLen, d_model]
            cut_metrics: Dict with match_score, singlet_energy, crossing_cancellation
        """
        B, T, D = forward_states.shape

        fwd = self.forward_proj(forward_states) # [B, T, D]
        bwd = self.backward_proj(backward_goals) # [B, T, D]

        # 1. Straight-Through Identity Match (ident1)
        straight_match = (fwd * bwd).sum(dim=-1, keepdim=True) # [B, T, 1]

        # 2. Antisymmetric Singlet Crossing Cancellation:
        # Enforce exact skew-symmetry: S = A - A^T (singlet operator)
        singlet_mats = self.raw_singlet - self.raw_singlet.transpose(-1, -2) # [num_cuts, D, D]

        # Compute bilinear crossing energy: sum_c (fwd @ S_c @ bwd^T)
        crossing_energy = torch.zeros(B, T, 1, device=forward_states.device)
        for c in range(self.num_cuts):
            s_c = singlet_mats[c]
            # (fwd @ S_c) * bwd
            fwd_s = torch.matmul(fwd, s_c) # [B, T, D]
            c_energy = (fwd_s * bwd).sum(dim=-1, keepdim=True) # [B, T, 1]
            crossing_energy = crossing_energy + c_energy

        # 3. Cut-Factorized Match Score: X = I - s(u)*s(v)
        cut_compatibility = torch.sigmoid(straight_match - 0.5 * crossing_energy) # [B, T, 1]

        # 4. Gated Intermediate Representation
        combined = torch.cat([fwd, bwd], dim=-1)
        gated_rep = F.silu(self.gate(combined))
        verified_state = self.ln_cut(forward_states + cut_compatibility * gated_rep)

        metrics = {
            "cut_compatibility": cut_compatibility.squeeze(-1),
            "straight_match": straight_match.squeeze(-1),
            "crossing_energy": crossing_energy.squeeze(-1),
        }

        return verified_state, metrics
