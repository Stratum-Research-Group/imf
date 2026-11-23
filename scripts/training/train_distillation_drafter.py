"""
Phase 1: Knowledge Distillation of IMF-107.7M Flagship into 4.35M Ultra-Fast Drafter.
Distills teacher logits and latent representations into a lightweight Polytope drafter.
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import math
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

torch.set_num_threads(1)
torch.set_num_interop_threads(1)

from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.omni_118_master_synthesizer import Omni118MasterSynthesizer
from train_flagship_omnilm_mope import IMFOmniLMMoPE


def train_distillation():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Starting IMF Knowledge Distillation on {device}...", flush=True)

    tok = CodeBPETokenizer.load("checkpoints/code_bpe_tokenizer.json")
    vocab_size = len(tok.vocab)

    # 1. Load Teacher (107.7M Model)
    teacher = IMFOmniLMMoPE(
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
    teacher_path = "checkpoints/imf_scaled_125m_omni118.pt"
    teacher.load_state_dict(torch.load(teacher_path, map_location=device))
    teacher.eval()
    for p in teacher.parameters():
        p.requires_grad = False
    print(f"[✓] Loaded Teacher Model ({sum(p.numel() for p in teacher.parameters()):,} params)", flush=True)

    # 2. Initialize Lightweight Student Model (d_model=128, 2 layers, 4 heads, 8 experts ~4.35M)
    student = IMFOmniLMMoPE(
        vocab_size=vocab_size,
        d_model=128,
        num_layers=2,
        num_heads=4,
        polytope_dim=5,
        num_experts=8,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.1,
    ).to(device)
    student_params = sum(p.numel() for p in student.parameters())
    print(f"[✓] Initialized Student Model ({student_params:,} params)", flush=True)

    # 3. Dataset across Omni-118 domains
    syn = Omni118MasterSynthesizer(seed=1337)
    train_samples = syn.generate_corpus(num_samples=3200)
    val_samples = syn.generate_corpus(num_samples=320)

    def encode(samples, seq_len=128):
        data = []
        for text, _ in samples:
            ids = tok.encode(text)
            if len(ids) >= seq_len:
                data.append(ids[:seq_len])
        return torch.tensor(data, dtype=torch.long)

    train_data = encode(train_samples, seq_len=128).to(device)
    val_data = encode(val_samples, seq_len=128).to(device)

    optimizer = optim.AdamW(student.parameters(), lr=1e-3, weight_decay=1e-2)
    temperature = 2.0
    alpha_kl = 0.6
    alpha_ce = 0.4

    batch_size = 32
    num_batches = len(train_data) // batch_size
    steps = 100
    start_t = time.perf_counter()

    for step in range(1, steps + 1):
        student.train()
        b_idx = (step - 1) % num_batches
        batch = train_data[b_idx * batch_size : (b_idx + 1) * batch_size]
        inputs = batch[:, :-1]
        targets = batch[:, 1:]

        with torch.no_grad():
            with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                t_logits, _, _ = teacher(inputs)
                t_logits = t_logits.detach()

        optimizer.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", dtype=torch.bfloat16):
            s_logits, _, s_metrics = student(inputs, targets=targets)
            ce_loss = s_metrics["loss_pred"]
            
            # KL Divergence Distillation Loss
            p_s = F.log_softmax(s_logits / temperature, dim=-1)
            p_t = F.softmax(t_logits / temperature, dim=-1)
            kl_loss = F.kl_div(p_s, p_t, reduction="batchmean") * (temperature ** 2)

            loss = alpha_ce * ce_loss + alpha_kl * kl_loss

        loss.backward()
        torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0)
        optimizer.step()

        if step % 10 == 0 or step == steps:
            student.eval()
            with torch.no_grad():
                val_in = val_data[:32, :-1]
                val_tg = val_data[:32, 1:]
                with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                    v_logits, _, v_metrics = student(val_in, targets=val_tg)
                val_ce = v_metrics["loss_pred"].item()
                val_ppl = math.exp(min(val_ce, 20.0))

            dt = time.perf_counter() - start_t
            print(
                f"Distill Step {step:3d}/{steps} | "
                f"Loss: {loss.item():.4f} (KL: {kl_loss.item():.4f}, CE: {ce_loss.item():.4f}) | "
                f"Val PPL: {val_ppl:.2f} | Elapsed: {dt:.1f}s",
                flush=True,
            )

    out_path = "checkpoints/imf_drafter_distilled_15m.pt"
    torch.save(student.state_dict(), out_path)
    print(f"[✓] Saved Distilled 4.35M Drafter Checkpoint to {out_path}", flush=True)


if __name__ == "__main__":
    train_distillation()
