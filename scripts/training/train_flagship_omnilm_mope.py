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
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.omni_64_multidomain_synthesizer import Omni64DomainSynthesizer
from imf.execution_verifier import MultiLanguageExecutionVerifier
from imf.omnilm_mope import IMFOmniLMMoPE


def train_flagship_omnilm_mope():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Launching Flagship IMF-OmniLM-MoPE Pretraining on {device}...")

    # 1. Dataset & Tokenizer across 64 Omni Domains
    synthesizer = Omni64DomainSynthesizer(seed=42)
    train_samples = synthesizer.generate_corpus(num_samples=12800)
    val_samples = synthesizer.generate_corpus(num_samples=1280)

    tok_path = "checkpoints/code_bpe_tokenizer.json"
    tokenizer = CodeBPETokenizer.load(tok_path)
    vocab_size = len(tokenizer.vocab)

    def encode_corpus(samples, seq_len=256):
        full_tokens = []
        for text, _ in samples:
            full_tokens.extend(tokenizer.encode(text))
        num_batches = len(full_tokens) // seq_len
        full_tokens = full_tokens[:num_batches * seq_len]
        return torch.tensor(full_tokens, dtype=torch.long).reshape(-1, seq_len)

    train_data = encode_corpus(train_samples, seq_len=256).to(device)
    val_data = encode_corpus(val_samples, seq_len=256).to(device)

    # 2. Model Setup: Scaled to 32 Active Geometric Domain Experts
    model = IMFOmniLMMoPE(
        vocab_size=vocab_size,
        d_model=128,
        num_layers=2,
        num_heads=4,
        polytope_dim=5,
        num_experts=32,
        top_k=2,
        max_seq_len=256,
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
