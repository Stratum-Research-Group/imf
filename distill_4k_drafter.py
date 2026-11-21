"""
Distill a 15M matching speculative drafter for the 4K BPE vocabulary
using knowledge distillation from IMFJointReconPredictorLM (129.8M target).
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import time
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM


def distill_4k_drafter(
    tokens_path: str = "data/expanded_corpus/finetune_tokens_4k.pt",
    tokenizer_path: str = "checkpoints/hybrid_bpe_tokenizer_4k.json",
    target_checkpoint: str = "checkpoints/imf_fluency_lm_4k.pt",
    output_checkpoint: str = "checkpoints/imf_drafter_fluency_4k.pt",
    max_steps: int = 500,
    batch_size: int = 16,
    seq_len: int = 128,
    lr: float = 3e-4,
):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 76)
    print("IMF 4K Speculative Drafter Distillation Engine (15M Parameters)")
    print("=" * 76)

    tok = CodeBPETokenizer.load(tokenizer_path)
    vocab_size = len(tok.vocab)
    tokens = torch.load(tokens_path, map_location="cpu").long()

    # 1. Target Teacher Model (129.8M)
    print(f"[*] Loading Target Teacher Model from {target_checkpoint}...")
    teacher = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=384,
        num_layers=4,
        num_heads=6,
        polytope_dim=8,
        num_experts=16,
        top_k=2,
        max_seq_len=seq_len,
        alpha_recon=0.2,
    ).to(device)
    teacher.load_state_dict(torch.load(target_checkpoint, map_location=device))
    teacher.eval()
    for p in teacher.parameters():
        p.requires_grad = False

    # 2. Student Drafter Model (15.2M)
    print(f"[*] Initializing Student Drafter Model...")
    student = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=128,
        num_layers=2,
        num_heads=4,
        polytope_dim=4,
        num_experts=8,
        top_k=2,
        max_seq_len=seq_len,
        alpha_recon=0.1,
    ).to(device)
    student_params = sum(p.numel() for p in student.parameters())
    print(f"Student parameters: {student_params:,} ({student_params/1e6:.2f}M)")

    optimizer = torch.optim.AdamW(student.parameters(), lr=lr, betas=(0.9, 0.95), weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_steps, eta_min=lr * 0.1)

    def get_batch():
        high = len(tokens) - seq_len - 1
        ix = torch.randint(0, high, (batch_size,))
        x = torch.stack([tokens[i : i + seq_len] for i in ix])
        y = torch.stack([tokens[i + 1 : i + seq_len + 1] for i in ix])
        return x.to(device), y.to(device)

    print("\nStarting Distillation...")
    student.train()
    t0 = time.perf_counter()

    for step in range(1, max_steps + 1):
        x, y = get_batch()
        optimizer.zero_grad(set_to_none=True)

        # Teacher logits (no grad)
        with torch.no_grad():
            t_logits, _, _ = teacher(x)

        # Student logits
        s_logits, _, metrics = student(x, targets=y)

        # Knowledge Distillation Loss (KL divergence + Hard Cross-Entropy)
        T = 2.0
        p_t = F.softmax(t_logits / T, dim=-1)
        log_p_s = F.log_softmax(s_logits / T, dim=-1)
        loss_kd = F.kl_div(log_p_s, p_t, reduction="batchmean") * (T * T)

        loss_ce = metrics["loss_pred"]
        loss = 0.6 * loss_kd + 0.4 * loss_ce

        loss.backward()
        torch.nn.utils.clip_grad_norm_(student.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        if step % 100 == 0 or step == 1:
            dt = time.perf_counter() - t0
            tok_s = (step * batch_size * seq_len) / max(dt, 1e-6)
            print(
                f"[Drafter Step {step:3d}/{max_steps:3d}] "
                f"Total Loss: {loss.item():.4f} | "
                f"KD Loss: {loss_kd.item():.4f} | "
                f"CE Loss: {loss_ce.item():.4f} | "
                f"Throughput: {tok_s:,.0f} tok/s"
            )

    torch.save(student.state_dict(), output_checkpoint)
    print(f"\n[✓] Distillation complete! Saved drafter to {output_checkpoint}")


if __name__ == "__main__":
    distill_4k_drafter()
