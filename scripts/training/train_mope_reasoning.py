"""
Training script for IMF-MoPE: Geometric Mixture of Polytope Experts.

Trains IMF with:
1. Continuous SO(d_h) unitary Lie group SSM.
2. Continuous multilinear simplex convolutions.
3. Polytope Mixture-of-Experts with Hyperbolic Poincaré routing.
4. Multi-Domain synthetic corpus: Python, Rust, Lean 4 tactics, and GSM8k CoT reasoning.
"""

import math
import os
import time
from typing import Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf.omni_block import IMFOmniBlock
from imf.polytope_moe import PolytopeMixtureOfExperts
from imf.bpe_tokenizer import BPETokenizer
from imf.synthetic_reasoning_corpus import MultiDomainCorpusSynthesizer


class IMFMiniMoPELM(nn.Module):
    """Compact IMF Language Model with Polytope MoE for domain reasoning."""
    def __init__(
        self,
        vocab_size: int,
        d_model: int = 128,
        num_layers: int = 2,
        num_experts: int = 4,
        top_k: int = 2,
        max_seq_len: int = 256,
    ):
        super().__init__()
        self.d_model = d_model
        self.vocab_size = vocab_size
        self.tok_embed = nn.Embedding(vocab_size, d_model)
        self.pos_embed = nn.Parameter(torch.randn(1, max_seq_len, d_model) * 0.02)

        self.layers = nn.ModuleList([
            IMFOmniBlock(
                d_model=d_model,
                num_heads=4,
                polytope_dim=3,
            )
            for _ in range(num_layers)
        ])

        self.moe_layers = nn.ModuleList([
            PolytopeMixtureOfExperts(
                d_model=d_model,
                num_experts=num_experts,
                top_k=top_k,
                use_hyperbolic=True,
                curvature=1.0,
            )
            for _ in range(num_layers)
        ])

        self.ln_f = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size, bias=False)
        self.head.weight = self.tok_embed.weight # Weight tying

    def forward(self, input_ids: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        B, T = input_ids.shape
        x = self.tok_embed(input_ids) + self.pos_embed[:, :T, :]

        total_balance_loss = torch.tensor(0.0, device=x.device)
        for omni, moe in zip(self.layers, self.moe_layers):
            x = omni(x)
            moe_out, aux = moe(x)
            x = x + moe_out
            total_balance_loss = total_balance_loss + aux["load_balance_loss"]

        x = self.ln_f(x)
        logits = self.head(x)
        return logits, total_balance_loss


def train_mope_reasoning():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing IMF-MoPE Multi-Domain Reasoning Training on {device}...")

    # 1. Synthesize multi-domain corpus
    synthesizer = MultiDomainCorpusSynthesizer(seed=1337)
    train_samples = synthesizer.generate_corpus(num_samples=1200)
    val_samples = synthesizer.generate_corpus(num_samples=200)

    # 2. Tokenizer
    tok_path = "checkpoints/bpe_tokenizer_reasoning.pt"
    if os.path.exists(tok_path):
        tokenizer = BPETokenizer.load(tok_path)
    else:
        tokenizer = BPETokenizer()
        raw_text = "\n".join([s[0] for s in train_samples])
        tokenizer.train(raw_text, target_vocab_size=1024, min_freq=2)
        os.makedirs("checkpoints", exist_ok=True)
        tokenizer.save(tok_path)

    vocab_size = len(tokenizer.vocab)
    print(f"[*] Tokenizer vocabulary size: {vocab_size}")

    # Encode streams
    def encode_corpus(samples, seq_len=128):
        full_tokens = []
        for text, _ in samples:
            full_tokens.extend(tokenizer.encode(text))
        num_batches = len(full_tokens) // seq_len
        full_tokens = full_tokens[:num_batches * seq_len]
        return torch.tensor(full_tokens, dtype=torch.long).reshape(-1, seq_len)

    train_data = encode_corpus(train_samples, seq_len=128).to(device)
    val_data = encode_corpus(val_samples, seq_len=128).to(device)
    print(f"[*] Train batches: {len(train_data)} | Val batches: {len(val_data)}")

    # 3. Model setup
    model = IMFMiniMoPELM(
        vocab_size=vocab_size,
        d_model=128,
        num_layers=2,
        num_experts=4,
        top_k=2,
        max_seq_len=128,
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters())
    print(f"[*] Total IMF-MoPE Parameters: {total_params:,}")

    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)

    # 4. Training loop (300 fast steps for demonstration & convergence check)
    batch_size = 16
    steps = 300
    model.train()
    start_time = time.time()

    for step in range(1, steps + 1):
        idx = torch.randint(0, len(train_data), (batch_size,))
        batch = train_data[idx] # [B, T]
        inputs = batch[:, :-1]
        targets = batch[:, 1:]

        logits, bal_loss = model(inputs) # [B, T-1, V]
        loss_ce = F.cross_entropy(logits.reshape(-1, vocab_size), targets.reshape(-1))
        loss = loss_ce + bal_loss

        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        if step % 50 == 0 or step == steps:
            model.eval()
            with torch.no_grad():
                val_idx = torch.randint(0, len(val_data), (min(batch_size, len(val_data)),))
                v_batch = val_data[val_idx]
                v_in, v_tgt = v_batch[:, :-1], v_batch[:, 1:]
                v_logits, _ = model(v_in)
                val_loss = F.cross_entropy(v_logits.reshape(-1, vocab_size), v_tgt.reshape(-1)).item()
                val_ppl = math.exp(min(val_loss, 20.0))
            model.train()
            elapsed = time.time() - start_time
            print(f"Step {step:3d}/{steps} | Train CE: {loss_ce.item():.4f} | Bal Loss: {bal_loss.item():.4f} | Val Loss: {val_loss:.4f} (PPL: {val_ppl:.2f}) | {elapsed:.1f}s")

    # Save checkpoint
    out_ckpt = "checkpoints/imf_mope_reasoning.pt"
    torch.save(model.state_dict(), out_ckpt)
    print(f"[+] Saved fine-tuned MoPE reasoning checkpoint to {out_ckpt}")


if __name__ == "__main__":
    train_mope_reasoning()
