"""
imf/omnilm_mope.py
==================
Flagship Unified Architecture: IMF-OmniLM-MoPE.

Integrates the 4 IMF core architectural pillars:
1. Unitary continuous-time SO(d_h) SSM with fused register-resident Triton kernel.
2. Continuous multilinear simplex convolutions (m >= 3).
3. Poincaré hyperbolic polytope routing to Domain Experts.
4. Bidirectional Cut-Reasoning + Anti-Collapse Joint Reconstruction (L = L_pred + alpha * L_recon).
"""

from typing import Dict, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf.omni_block import IMFOmniBlock
from imf.polytope_moe import PolytopeMixtureOfExperts
from imf.eth_cut_reasoning import BidirectionalCutReasoning


class IMFOmniLMMoPE(nn.Module):
    """
    Unified Flagship Model:
    Combines Continuous Lie Group SSM, Simplex Convolutions, Hyperbolic Polytope MoE,
    and Bidirectional Cut-Reasoning with Joint State Reconstruction.
    """
    def __init__(
        self,
        vocab_size: int,
        d_model: int = 128,
        num_layers: int = 2,
        num_heads: int = 4,
        polytope_dim: int = 3,
        num_experts: int = 32,
        top_k: int = 2,
        max_seq_len: int = 256,
        alpha_recon: float = 0.3,
    ):
        super().__init__()
        self.d_model = d_model
        self.vocab_size = vocab_size
        self.alpha_recon = alpha_recon

        self.tok_embed = nn.Embedding(vocab_size, d_model)
        self.pos_embed = nn.Parameter(torch.randn(1, max_seq_len, d_model) * 0.02)

        # OmniBlocks: Unitary SO(d_h) SSM + Continuous Simplex Convolutions
        self.layers = nn.ModuleList([
            IMFOmniBlock(
                d_model=d_model,
                num_heads=num_heads,
                polytope_dim=polytope_dim,
            )
            for _ in range(num_layers)
        ])

        # Polytope Mixture-of-Experts with Hyperbolic Routing
        self.moe_layers = nn.ModuleList([
            PolytopeMixtureOfExperts(
                d_model=d_model,
                num_experts=num_experts,
                top_k=top_k,
                use_hyperbolic=True,
            )
            for _ in range(num_layers)
        ])

        # Bidirectional Cut-Reasoning Layer at the output bottleneck
        self.cut_reasoner = BidirectionalCutReasoning(d_model=d_model, num_cuts=4)

        self.ln_f = nn.LayerNorm(d_model)

        # 1. Forward Prediction Head (tied weights)
        self.pred_head = nn.Linear(d_model, vocab_size, bias=False)
        self.pred_head.weight = self.tok_embed.weight

        # 2. Joint Reconstruction Head (Anti-Collapse)
        self.recon_mlp = nn.Sequential(
            nn.Linear(d_model, d_model * 2),
            nn.GELU(),
            nn.Linear(d_model * 2, d_model),
            nn.LayerNorm(d_model),
        )
        self.recon_head = nn.Linear(d_model, vocab_size, bias=False)

    def forward(
        self,
        input_ids: torch.Tensor,
        targets: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, torch.Tensor]]:
        B, T = input_ids.shape
        x = self.tok_embed(input_ids) + self.pos_embed[:, :T, :]

        total_balance_loss = torch.tensor(0.0, device=x.device)
        for omni, moe in zip(self.layers, self.moe_layers):
            x = omni(x)
            moe_out, aux = moe(x)
            x = x + moe_out
            total_balance_loss = total_balance_loss + aux["load_balance_loss"]

        # Strictly Causal Autoregressive Representation:
        # Autoregressive next-token prediction heads must maintain prefix invariance.
        # Forward states 'x' are directly passed through the causal output normalizer.
        latents = self.ln_f(x)

        # Optional Cut-Reasoning verification metric (without backwards sequence leakage into causal heads)
        x_rev = torch.flip(x, dims=[1])
        _, cut_metrics = self.cut_reasoner(x, x_rev)

        pred_logits = self.pred_head(latents)
        recon_features = self.recon_mlp(latents)
        recon_logits = self.recon_head(recon_features)

        metrics = {}
        if targets is not None:
            loss_pred = F.cross_entropy(
                pred_logits.reshape(-1, self.vocab_size),
                targets.reshape(-1),
            )
            loss_recon = F.cross_entropy(
                recon_logits.reshape(-1, self.vocab_size),
                input_ids.reshape(-1),
            )
            total_loss = loss_pred + self.alpha_recon * loss_recon + total_balance_loss
            metrics = {
                "total_loss": total_loss,
                "loss_pred": loss_pred,
                "loss_recon": loss_recon,
                "balance_loss": total_balance_loss,
                "cut_compatibility": cut_metrics["cut_compatibility"].mean(),
            }

        return pred_logits, recon_logits, metrics
