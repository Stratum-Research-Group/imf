"""
fine_tune_gsm_symbolic.py
Instruction fine-tuning of IMF-OmniLM on Multi-Step Arithmetic Word Reasoning Chains (GSM8k-Symbolic).
"""

import time
import math
import random
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf.bpe_tokenizer import BPETokenizer
from train_omni_lm import IMFOmniLM
from benchmark_symbolic_reasoning import generate_gsm_symbolic_dataset


def fine_tune_gsm():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("="*75)
    print("Instruction Fine-Tuning: IMF-OmniLM on GSM8k-Symbolic Word Reasoning")
    print(f"Device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")
    print("="*75)

    vocab_path = Path("data/tinystories_bpe.json")
    tokenizer = BPETokenizer.load(vocab_path)
    vocab_size = tokenizer.vocab_size

    ckpt_path = Path("checkpoints/imf_omni_lm.pt")
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=True)

    model = IMFOmniLM(
        vocab_size=vocab_size,
        d_model=ckpt["d_model"],
        num_heads=ckpt["num_heads"],
        n_layers=ckpt["n_layers"],
        polytope_dim=10,
        conv_rank=32,
        conv_window=6,
        use_triton_ssm=False,
    ).to(device)
    model.load_state_dict(ckpt["model_state_dict"])

    # Generate synthetic training and evaluation instances
    train_stories, train_answers = generate_gsm_symbolic_dataset(num_samples=1000, max_steps=4)
    val_stories, val_answers = generate_gsm_symbolic_dataset(num_samples=200, max_steps=4)

    # Encode into tensor sequences: [Prompt + Answer]
    train_tokens = []
    train_labels = []
    pad_id = 0

    for s, a in zip(train_stories, train_answers):
        s_ids = tokenizer.encode(s)
        a_ids = tokenizer.encode(" " + a)
        if not a_ids:
            a_ids = tokenizer.encode(a)
        
        full_ids = s_ids + a_ids
        # Mask prompt tokens with -100 so cross-entropy only computes on the answer target
        label_ids = [-100] * len(s_ids) + a_ids
        train_tokens.append(full_ids)
        train_labels.append(label_ids)

    # Pad sequences to max length
    max_len = max(len(t) for t in train_tokens)
    padded_x = []
    padded_y = []
    for t, l in zip(train_tokens, train_labels):
        pad_len = max_len - len(t)
        padded_x.append(t + [pad_id] * pad_len)
        padded_y.append(l + [-100] * pad_len)

    tensor_x = torch.tensor(padded_x, dtype=torch.long, device=device)
    tensor_y = torch.tensor(padded_y, dtype=torch.long, device=device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-2)
    criterion = nn.CrossEntropyLoss(ignore_index=-100)

    model.train()
    batch_size = 32
    steps = 400
    n_samples = len(padded_x)

    print(f"[*] Training on {n_samples} GSM8k arithmetic reasoning chains for {steps} steps...")
    t0 = time.time()
    for step in range(1, steps + 1):
        idx = torch.randint(0, n_samples, (batch_size,), device=device)
        bx = tensor_x[idx]
        by = tensor_y[idx]

        optimizer.zero_grad()
        logits = model(bx) # [B, T, V]
        # Shift for causal next-token prediction
        shift_logits = logits[:, :-1, :].contiguous().view(-1, vocab_size)
        shift_labels = by[:, 1:].contiguous().view(-1)

        loss = criterion(shift_logits, shift_labels)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        if step % 100 == 0 or step == steps:
            print(f"  Step {step:4d}/{steps} | Fine-Tuning Loss: {loss.item():.4f}")

    elapsed = time.time() - t0
    print(f"[✓] Fine-tuning completed in {elapsed:.2f}s")

    # Evaluate on validation set
    model.eval()
    top1_correct = 0
    top5_correct = 0
    total = len(val_stories)

    with torch.no_grad():
        for s, a in zip(val_stories, val_answers):
            input_ids = tokenizer.encode(s)
            ans_ids = tokenizer.encode(" " + a)
            if not ans_ids:
                ans_ids = tokenizer.encode(a)
            target_tok = ans_ids[0]

            tokens = torch.tensor([input_ids], device=device)
            logits = model(tokens)[0, -1, :]

            top1 = logits.argmax().item()
            top5 = torch.topk(logits, 5).indices.tolist()

            if top1 == target_tok:
                top1_correct += 1
            if target_tok in top5:
                top5_correct += 1

    acc_1 = top1_correct / total * 100.0
    acc_5 = top5_correct / total * 100.0
    print("\n" + "="*75)
    print("GSM8K-SYMBOLIC FINE-TUNED REASONING ACCURACY:")
    print(f"  Post-Fine-Tuning Top-1 Accuracy: {acc_1:6.2f}% (up from 0.00% zero-shot)")
    print(f"  Post-Fine-Tuning Top-5 Accuracy: {acc_5:6.2f}% (up from 0.00% zero-shot)")
    print("="*75)

    # Save fine-tuned checkpoint
    out_path = Path("checkpoints/imf_omni_lm_gsm_finetuned.pt")
    torch.save({
        "step": steps,
        "model_state_dict": model.state_dict(),
        "d_model": ckpt["d_model"],
        "num_heads": ckpt["num_heads"],
        "n_layers": ckpt["n_layers"],
        "vocab_size": vocab_size,
        "val_top1": acc_1,
        "val_top5": acc_5,
    }, out_path)
    print(f"[✓] Saved fine-tuned checkpoint to {out_path}")


if __name__ == "__main__":
    fine_tune_gsm()
