"""
Unified Flagship Pretraining Script: IMF-OmniLM-MoPE.

Integrates all 4 IMF core architectural pillars:
1. Unitary continuous-time SO(d_h) SSM with fused register-resident Triton kernel.
2. Continuous multilinear simplex convolutions (m >= 3).
3. Poincaré hyperbolic polytope routing to 4 Domain Experts.
4. Bidirectional Cut-Reasoning + Anti-Collapse Joint Reconstruction (L = L_pred + alpha * L_recon).
"""

import math
import os
import time
from typing import Dict, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf.omni_block import IMFOmniBlock
from imf.polytope_moe import PolytopeMixtureOfExperts
from imf.eth_cut_reasoning import BidirectionalCutReasoning
from imf.bpe_tokenizer import BPETokenizer
from imf.synthetic_reasoning_corpus import MultiDomainCorpusSynthesizer
from imf.execution_verifier import MultiLanguageExecutionVerifier


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
        num_experts: int = 4,
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

        # Apply Bidirectional Cut-Reasoning:
        # Reconcile forward state rollout with backward adjoint representation
        x_rev = torch.flip(x, dims=[1])
        x_cut, cut_metrics = self.cut_reasoner(x, x_rev)
        latents = self.ln_f(x_cut)

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


def train_flagship_omnilm_mope():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Launching Flagship IMF-OmniLM-MoPE Pretraining on {device}...")

    # 1. Dataset & Tokenizer
    synthesizer = MultiDomainCorpusSynthesizer(seed=42)
    train_samples = synthesizer.generate_corpus(num_samples=1500)
    val_samples = synthesizer.generate_corpus(num_samples=250)

    tok_path = "checkpoints/bpe_tokenizer_reasoning.pt"
    tokenizer = BPETokenizer.load(tok_path)
    vocab_size = len(tokenizer.vocab)

    def encode_corpus(samples, seq_len=128):
        full_tokens = []
        for text, _ in samples:
            full_tokens.extend(tokenizer.encode(text))
        num_batches = len(full_tokens) // seq_len
        full_tokens = full_tokens[:num_batches * seq_len]
        return torch.tensor(full_tokens, dtype=torch.long).reshape(-1, seq_len)

    train_data = encode_corpus(train_samples, seq_len=128).to(device)
    val_data = encode_corpus(val_samples, seq_len=128).to(device)

    # 2. Model Setup
    model = IMFOmniLMMoPE(
        vocab_size=vocab_size,
        d_model=128,
        num_layers=2,
        num_heads=4,
        polytope_dim=3,
        num_experts=4,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.3,
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters())
    print(f"[*] Total Flagship Parameters: {total_params:,}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)

    # 3. Pretraining Loop (500 steps)
    batch_size = 16
    steps = 500
    model.train()
    start_time = time.time()

    for step in range(1, steps + 1):
        idx = torch.randint(0, len(train_data), (batch_size,))
        batch = train_data[idx]
        x, y = batch[:, :-1], batch[:, 1:]

        _, _, metrics = model(x, targets=y)
        loss = metrics["total_loss"]

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        if step % 100 == 0 or step == steps:
            model.eval()
            with torch.no_grad():
                v_idx = torch.randint(0, len(val_data), (min(batch_size, len(val_data)),))
                v_batch = val_data[v_idx]
                vx, vy = v_batch[:, :-1], v_batch[:, 1:]
                _, _, v_m = model(vx, targets=vy)
                v_loss = v_m["loss_pred"].item()
                v_ppl = math.exp(min(v_loss, 20.0))
            model.train()
            elapsed = time.time() - start_time
            print(f"Step {step:3d}/{steps} | Train Pred: {metrics['loss_pred'].item():.4f} | Recon: {metrics['loss_recon'].item():.4f} | Val Loss: {v_loss:.4f} (PPL: {v_ppl:.2f}) | {elapsed:.1f}s")

    # 4. Save Flagship Checkpoint
    os.makedirs("checkpoints", exist_ok=True)
    out_ckpt = "checkpoints/imf_omnilm_mope_flagship.pt"
    torch.save(model.state_dict(), out_ckpt)
    print(f"[+] Saved Flagship checkpoint to {out_ckpt}")


if __name__ == "__main__":
    train_flagship_omnilm_mope()
