"""
Train Scaled IMF-OmniLM-MoPE-118 (125M Parameter Scale).
Trained on NVIDIA RTX 5060 Ti utilizing:
- 118-Domain Master Synthesizer.
- Polytope Barycentric MoPE (k=4 active experts, d=5).
- Continuous Lie-Group SSM + Simplex Attention + Holonomy Gauge.
- Joint Reconstruction Regularization (L = L_pred + 0.3 * L_recon).
- Native Mixed Precision (torch.cuda.amp.autocast).
"""

import os
import math
import time
import torch
import torch.nn as nn
import torch.optim as optim

from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.omni_118_master_synthesizer import Omni118MasterSynthesizer
from train_flagship_omnilm_mope import IMFOmniLMMoPE


def train_scaled_125m():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Launching Scaled IMF-125M-Omni118 Pretraining on {device}...")

    # 1. Dataset across all 118 Domains
    syn = Omni118MasterSynthesizer(seed=42)
    train_samples = syn.generate_corpus(num_samples=6400)
    val_samples = syn.generate_corpus(num_samples=640)

    tok_path = "checkpoints/code_bpe_tokenizer.json"
    tok = CodeBPETokenizer.load(tok_path)
    vocab_size = len(tok.vocab)

    def encode(samples, seq_len=128):
        data = []
        for text, _ in samples:
            ids = tok.encode(text)
            if len(ids) >= seq_len:
                data.append(ids[:seq_len])
        return torch.tensor(data, dtype=torch.long)

    train_data = encode(train_samples, seq_len=128).to(device)
    val_data = encode(val_samples, seq_len=128).to(device)

    # 2. Scaled Model: d_model=256, 4 layers, 8 heads, 32 experts (k=4)
    # Balanced to train rapidly within available ~11GB free GPU VRAM
    model = IMFOmniLMMoPE(
        vocab_size=vocab_size,
        d_model=256,
        num_layers=4,
        num_heads=8,
        polytope_dim=5,
        num_experts=32,
        top_k=4,
        max_seq_len=128,
        alpha_recon=0.3,
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters())
    print(f"[*] Total Scaled Parameters: {total_params:,}")

    optimizer = optim.AdamW(model.parameters(), lr=8e-4, weight_decay=1e-2)
    scaler = torch.amp.GradScaler('cuda')

    batch_size = 16
    num_batches = len(train_data) // batch_size
    steps = 100
    start_time = time.perf_counter()

    for step in range(1, steps + 1):
        model.train()
        b_idx = (step - 1) % num_batches
        batch = train_data[b_idx * batch_size : (b_idx + 1) * batch_size]
        inputs = batch[:, :-1]
        targets = batch[:, 1:]

        optimizer.zero_grad()
        with torch.amp.autocast('cuda', dtype=torch.float16):
            logits, recon_logits, metrics = model(inputs, targets=targets)
            loss = metrics["total_loss"]

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()

        if step % 10 == 0 or step == steps:
            model.eval()
            with torch.no_grad():
                val_in = val_data[:32, :-1]
                val_tg = val_data[:32, 1:]
                with torch.amp.autocast('cuda', dtype=torch.float16):
                    _, _, val_m = model(val_in, targets=val_tg)
                val_loss = val_m["loss_pred"].item()
                val_ppl = math.exp(min(val_loss, 20.0))

            elapsed = time.perf_counter() - start_time
            print(
                f"Step {step:3d}/{steps} | "
                f"Train Loss: {loss.item():.4f} | "
                f"Val Loss: {val_loss:.4f} (PPL: {val_ppl:.2f}) | "
                f"Elapsed: {elapsed:.1f}s",
                flush=True,
            )

    os.makedirs("checkpoints", exist_ok=True)
    out_path = "checkpoints/imf_scaled_125m_omni118.pt"
    torch.save(model.state_dict(), out_path)
    print(f"[+] Saved Scaled 125M Checkpoint to {out_path}", flush=True)


if __name__ == "__main__":
    train_scaled_125m()
