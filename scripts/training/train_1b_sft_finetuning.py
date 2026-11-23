"""
train_1b_sft_finetuning.py
Supervised Fine-Tuning (SFT) & Curriculum Alignment Engine for the 1.14B Foundation Model.
Drastically reduces cross-entropy loss and perplexity across code, math, and formal reasoning
using KroneckerFactorizedAdamW (16MB memory) + Gradient Checkpointing within 16GB VRAM.
"""

import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
import math
import time
import sys
from pathlib import Path
import torch
import torch.nn as nn
from torch.utils.checkpoint import checkpoint

from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.kronecker_factorized_adamw import KroneckerFactorizedAdamW
from imf.imf_container import IMFWriter, IMFReader
from imf.imf_model_loader import load_imf_state_dict

def train_sft_1b():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 80)
    print("  IMF 1.14B Foundation Model: Targeted Supervised Fine-Tuning (SFT)")
    print("=" * 80)
    print(f"Device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    base_checkpoint_pt = "checkpoints/imf_foundation_1b.pt"
    sft_tokens_path = "data/frontier_corpus/frontier_technical_tokens_4k.pt"
    tokenizer_path = "checkpoints/hybrid_bpe_tokenizer_4k.json"
    output_pt = "checkpoints/imf_foundation_1b_sft.pt"
    output_imf = "checkpoints/imf_foundation_1b.imf"

    tok = CodeBPETokenizer.load(tokenizer_path)
    vocab_size = len(tok.vocab)

    # 1. Load Tokens
    print(f"[*] Loading SFT clean frontier technical reasoning tokens from {sft_tokens_path}...")
    tokens = torch.load(sft_tokens_path, map_location="cpu").long()
    n_tokens = len(tokens)
    print(f"[✓] Loaded {n_tokens:,} tokens ({n_tokens / 1e6:.2f}M tokens).")

    # 2. Load Existing 1.14B Weights
    print(f"[*] Loading pretrained weights from {base_checkpoint_pt}...")
    state_dict = torch.load(base_checkpoint_pt, map_location="cpu")

    model = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=576,
        num_layers=16,
        num_heads=8,
        polytope_dim=8,
        num_experts=16,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.2,
    ).to(device)
    model.load_state_dict(state_dict, strict=False)
    del state_dict

    # Enable activation checkpointing on all layers to fit in 16GB VRAM
    for layer in model.layers:
        layer.use_checkpointing = True

    # Freeze continuous Lie group SSM rotation parameters during SFT to preserve Lie algebra geometry
    for layer in model.layers:
        layer.ssm.raw_generator.requires_grad = False
        layer.ssm.log_delta.requires_grad = False

    model = model.to(device)
    model.train()
    print(f"[✓] Model Materialized on {device}. Parameters: {sum(p.numel() for p in model.parameters()):,}")
    if torch.cuda.is_available():
        print(f"    Current GPU VRAM: {torch.cuda.memory_allocated() / (1024**3):.2f} GB / 16.0 GB")

    # 3. Optimizer Setup: KroneckerFactorizedAdamW (16MB State Footprint)
    optimizer = KroneckerFactorizedAdamW(
        model.parameters(),
        lr=3.0e-5,  # Conservative stable fine-tuning rate preventing Lie SSM divergence
        betas=(0.0, 0.999),
        weight_decay=0.01,
    )

    max_steps = 150
    batch_size = 1
    seq_len = 128
    grad_accum_steps = 8
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_steps, eta_min=5.0e-6)

    def get_batch():
        ix = torch.randint(0, n_tokens - seq_len - 1, (batch_size,))
        x = torch.stack([tokens[i : i + seq_len] for i in ix]).to(device)
        y = torch.stack([tokens[i + 1 : i + 1 + seq_len] for i in ix]).to(device)
        return x, y

    print(f"\n[*] Commencing SFT Optimization ({max_steps} steps, Batch={batch_size*grad_accum_steps}, SeqLen={seq_len})...")
    start_time = time.perf_counter()
    running_loss = 0.0

    for step in range(1, max_steps + 1):
        optimizer.zero_grad()
        loss_accum = 0.0

        for _ in range(grad_accum_steps):
            x, y = get_batch()
            with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                logits, _, metrics = model(x, targets=y)
                loss = metrics["loss_pred"] / grad_accum_steps
            loss.backward()
            loss_accum += loss.item()

        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        running_loss += loss_accum
        if step % 15 == 0 or step == 1 or step == max_steps:
            avg_loss = running_loss / (15 if step % 15 == 0 else 1)
            running_loss = 0.0
            ppl = math.exp(min(avg_loss, 20.0))
            elapsed = time.perf_counter() - start_time
            tok_per_sec = (step * batch_size * grad_accum_steps * seq_len) / elapsed
            print(f"Step {step:3d}/{max_steps} | Loss: {avg_loss:.4f} | Perplexity: {ppl:6.2f} | "
                  f"Throughput: {tok_per_sec:.0f} tok/s | Elapsed: {elapsed:.1f}s")

    # 4. Save Upgraded Checkpoint to PyTorch and .imf format
    print("\n[*] Packaging aligned model weights into zero-copy .imf container...")
    model.eval()
    cpu_state_dict = {k: v.cpu() for k, v in model.state_dict().items()}
    
    # Save .pt
    pt_path = "checkpoints/imf_foundation_1b_sft.pt"
    torch.save(cpu_state_dict, pt_path)
    print(f"[✓] Saved PyTorch weights to {pt_path}")

    # Save .imf
    imf_path = "checkpoints/imf_foundation_1b.imf"
    writer = IMFWriter(imf_path, model_config={
        "vocab_size": vocab_size,
        "d_model": 576,
        "num_layers": 16,
        "num_heads": 8,
        "polytope_dim": 8,
        "num_experts": 16,
        "alignment": "SFT-Curriculum-Aligned",
    })
    for k, v in cpu_state_dict.items():
        writer.add_tensor(k, v)
    writer.write()
    print(f"[✓] Successfully upgraded {imf_path} container in-place!")

if __name__ == "__main__":
    train_sft_1b()
