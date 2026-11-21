"""
Joint Reconstruction + Prediction Architecture for IMF (Interaction Model Foundations).

Implements Section 4 & 6 of the joint recon-prediction design:
- Core recurrence: s_k = IMF_OmniBlock(s_{k-1}, x_k)
- Prediction Head: Predicts next token / block B_{k+1}
- Joint Reconstruction Decoder Head: Forces state s_k to reconstruct current / past token block B_k
- Joint Loss: L = L_pred + alpha * L_recon
Provides active anti-collapse pressure on the internal continuous Lie-group SSM states,
preventing long-horizon forgetting of exact syntax, variable identities, and AST structure.
"""

from typing import Dict, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf.omni_block import IMFOmniBlock
from imf.polytope_moe import PolytopeMixtureOfExperts


class IMFJointReconPredictorLM(nn.Module):
    """
    IMF Language Model with Joint Prediction and State Reconstruction Heads.
    """
    def __init__(
        self,
        vocab_size: int,
        d_model: int = 128,
        num_layers: int = 2,
        num_heads: int = 4,
        polytope_dim: int = 3,
        num_experts: int = 4,
        top_k: int = 2,
        max_seq_len: int = 256,
        alpha_recon: float = 0.5,
    ):
        super().__init__()
        self.d_model = d_model
        self.vocab_size = vocab_size
        self.alpha_recon = alpha_recon

        self.tok_embed = nn.Embedding(vocab_size, d_model)
        self.pos_embed = nn.Parameter(torch.randn(1, max_seq_len, d_model) * 0.02)

        self.layers = nn.ModuleList([
            IMFOmniBlock(
                d_model=d_model,
                num_heads=num_heads,
                polytope_dim=polytope_dim,
            )
            for _ in range(num_layers)
        ])

        self.moe_layers = nn.ModuleList([
            PolytopeMixtureOfExperts(
                d_model=d_model,
                num_experts=num_experts,
                top_k=top_k,
                use_hyperbolic=True,
            )
            for _ in range(num_layers)
        ])

        self.ln_f = nn.LayerNorm(d_model)

        # 1. Prediction Head (Target: Next Token x_{t+1})
        self.pred_head = nn.Linear(d_model, vocab_size, bias=False)
        self.pred_head.weight = self.tok_embed.weight # Weight tying

        # 2. Joint Reconstruction Head (Target: Current / Retrospective Token x_t)
        # Reconstructs raw syntax directly from the continuous geometric state
        self.recon_mlp = nn.Sequential(
            nn.Linear(d_model, d_model * 2),
            nn.GELU(),
            nn.Linear(d_model * 2, d_model),
            nn.LayerNorm(d_model),
        )
        self.recon_head = nn.Linear(d_model, vocab_size, bias=False)

        # Apply robust weight initialization across embeddings and heads
        self._init_weights()

    def _init_weights(self):
        nn.init.normal_(self.tok_embed.weight, mean=0.0, std=0.02)
        nn.init.normal_(self.recon_head.weight, mean=0.0, std=0.02)
        for m in self.recon_mlp.modules():
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, mean=0.0, std=0.02)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(
        self,
        input_ids: torch.Tensor,
        targets: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Args:
            input_ids: [Batch, SeqLen]
            targets: Optional [Batch, SeqLen] for next-token prediction
        Returns:
            pred_logits: [Batch, SeqLen, vocab_size]
            recon_logits: [Batch, SeqLen, vocab_size]
            metrics: Dict with total_loss, pred_loss, recon_loss, latent_rank, latent_variance
        """
        B, T = input_ids.shape
        x = self.tok_embed(input_ids) + self.pos_embed[:, :T, :]

        total_balance_loss = torch.tensor(0.0, device=x.device)
        for omni, moe in zip(self.layers, self.moe_layers):
            x = omni(x)
            moe_out, aux = moe(x)
            x = x + moe_out
            total_balance_loss = total_balance_loss + aux["load_balance_loss"]

        # Latent representations before output heads
        latents = self.ln_f(x) # [B, T, D]

        # 1. Forward Prediction Logits
        pred_logits = self.pred_head(latents)

        # 2. Backward Reconstruction Logits (reconstruct input_ids from latents)
        recon_features = self.recon_mlp(latents)
        recon_logits = self.recon_head(recon_features)

        metrics = {}
        if targets is not None:
            # Prediction loss: teacher-forced next-token prediction
            loss_pred = F.cross_entropy(
                pred_logits.reshape(-1, self.vocab_size),
                targets.reshape(-1),
            )

            # Reconstruction loss: reconstruct input_ids themselves
            loss_recon = F.cross_entropy(
                recon_logits.reshape(-1, self.vocab_size),
                input_ids.reshape(-1),
            )

            # Combined Joint Loss
            total_loss = loss_pred + self.alpha_recon * loss_recon + total_balance_loss

            # Measure representation collapse metrics (rank and variance)
            with torch.no_grad():
                latents_flat = latents.reshape(-1, self.d_model)
                latent_var = latents_flat.var(dim=0).mean().item()
                # Sample SVD for effective dimensionality / rank (run safely on CPU)
                eff_rank = self.d_model
                sample_u = latents_flat[:min(128, latents_flat.shape[0])].detach().cpu().float()
                if sample_u.shape[0] >= 16 and torch.isfinite(sample_u).all():
                    try:
                        s = torch.linalg.svdvals(sample_u - sample_u.mean(dim=0))
                        s_norm = s / (s.sum() + 1e-7)
                        cum_energy = torch.cumsum(s_norm, dim=0)
                        eff_rank = (cum_energy < 0.95).sum().item() + 1
                    except Exception:
                        eff_rank = self.d_model

            metrics = {
                "total_loss": total_loss,
                "loss_pred": loss_pred,
                "loss_recon": loss_recon,
                "balance_loss": total_balance_loss,
                "latent_variance": latent_var,
                "effective_rank": eff_rank,
            }

        return pred_logits, recon_logits, metrics
