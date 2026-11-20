"""
Train Flagship IMF-OmniLM-MoPE-100 (k=4 Active Polytope Experts).
Integrates:
- All 100 Universal Specialized Expert Domains.
- Optimal k = 4 active experts per token on a d=5 convex polytope.
- Joint Reconstruction + Prediction (L = L_pred + 0.3 * L_recon).
- Continuous Lie-Group SSM + Simplex Attention + Holonomy Gauge Complex.
- Bidirectional Cut-Reasoning for multi-hop deduction chains.
"""

import os
import math
import time
import torch
import torch.nn as nn
import torch.optim as optim

from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.omni_100_master_synthesizer import Omni100MasterSynthesizer
from train_flagship_omnilm_mope import IMFOmniLMMoPE


def train_flagship_100_k4():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Launching Flagship IMF-OmniLM-MoPE-100 (k=4) Pretraining on {device}...")

    # 1. Dataset & Tokenizer across 100 Master Domains
    synthesizer = Omni100MasterSynthesizer(seed=42)
    train_samples = synthesizer.generate_corpus(num_samples=12800)
    val_samples = synthesizer.generate_corpus(num_samples=1280)

    tok_path = "checkpoints/code_bpe_tokenizer.json"
    tokenizer = CodeBPETokenizer.load(tok_path)
    vocab_size = len(tokenizer.vocab)

    def encode_corpus(samples, seq_len=256):
        data = []
        for text, _ in samples:
            ids = tokenizer.encode(text)
            if len(ids) >= seq_len:
                data.append(ids[:seq_len])
        return torch.tensor(data, dtype=torch.long)

    train_data = encode_corpus(train_samples, seq_len=256).to(device)
    val_data = encode_corpus(val_samples, seq_len=256).to(device)

    # 2. Model Setup: 100 Domains, 32 Geometric Polytope Experts, k = 4
    model = IMFOmniLMMoPE(
        vocab_size=vocab_size,
        d_model=128,
        num_layers=2,
        num_heads=4,
        polytope_dim=5,
        num_experts=32,
        top_k=4,              # <-- Optimal k=4 active experts
        max_seq_len=256,
        alpha_recon=0.3,
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters())
    print(f"[*] Total Flagship IMF-100 (k=4) Parameters: {total_params:,}")

    optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-2)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=500, eta_min=1e-5)

    batch_size = 16
    num_batches = len(train_data) // batch_size
    steps = 500
    start_time = time.perf_counter()

    for step in range(1, steps + 1):
        model.train()
        batch_idx = (step - 1) % num_batches
        batch = train_data[batch_idx * batch_size : (batch_idx + 1) * batch_size]
        inputs = batch[:, :-1]
        targets = batch[:, 1:]

        optimizer.zero_grad()
        logits, recon_logits, metrics = model(inputs, targets=targets)
        loss = metrics["total_loss"]
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        if step % 100 == 0 or step == steps:
            model.eval()
            with torch.no_grad():
                val_inputs = val_data[:32, :-1]
                val_targets = val_data[:32, 1:]
                _, _, val_metrics = model(val_inputs, targets=val_targets)
                val_loss = val_metrics["loss_pred"].item()
                val_ppl = math.exp(min(val_loss, 20.0))

            elapsed = time.perf_counter() - start_time
            print(
                f"Step {step:3d}/{steps} | "
                f"Train Pred: {metrics['loss_pred'].item():.4f} | "
                f"Recon: {metrics['loss_recon'].item():.4f} | "
                f"Val Loss: {val_loss:.4f} (PPL: {val_ppl:.2f}) | "
                f"{elapsed:.1f}s"
            )

    os.makedirs("checkpoints", exist_ok=True)
    ckpt_path = "checkpoints/imf_omnilm_100_k4_flagship.pt"
    torch.save(model.state_dict(), ckpt_path)
    print(f"[+] Saved 100-Domain k=4 Flagship checkpoint to {ckpt_path}")


if __name__ == "__main__":
    train_flagship_100_k4()
