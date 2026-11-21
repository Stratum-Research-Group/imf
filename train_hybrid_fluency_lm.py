"""
train_hybrid_fluency_lm.py
High-throughput pretraining on the 3.46M-token hybrid corpus (Natural Language + Code + Proofs).
Upgrades IMF from a synthetic mathematical prototype to a fluent language and code generator.
"""

import math
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.code_bpe_tokenizer import CodeBPETokenizer


def train_fluency_lm(
    tokens_path: str = "data/hybrid_corpus/training_tokens_4k.pt",
    tokenizer_path: str = "checkpoints/hybrid_bpe_tokenizer_4k.json",
    output_checkpoint: str = "checkpoints/imf_fluency_lm_4k.pt",
    max_steps: int = 2000,
    batch_size: int = 16,
    seq_len: int = 128,
    lr: float = 6e-4,
):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 76)
    print("IMF Fluent Natural Language & Free-Form Code Pretraining Engine")
    print("=" * 76)
    print(f"Device: {device} | Sequence Length: {seq_len} | Batch Size: {batch_size}")

    # Load pre-tokenized dataset
    tokens = torch.load(tokens_path, map_location="cpu").long()
    n_tokens = len(tokens)
    print(f"Loaded {n_tokens:,} training tokens from {tokens_path}")

    # Split train / validation (95% / 5%)
    split_idx = int(0.95 * n_tokens)
    train_tokens = tokens[:split_idx]
    val_tokens = tokens[split_idx:]

    tok = CodeBPETokenizer.load(tokenizer_path)
    vocab_size = len(tok.vocab)
    print(f"Loaded tokenizer from {tokenizer_path} (Vocab size: {vocab_size})")

    # Initialize scaled IMF architecture with Polytope MoE and Continuous Lie SSM
    # Model parameters ~ 45M (optimized for high-speed convergence on 16GB VRAM)
    model = IMFJointReconPredictorLM(
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

    total_params = sum(p.numel() for p in model.parameters())
    print(f"Model initialized: {total_params:,} parameters ({total_params/1e6:.2f}M)")

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.95), weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_steps, eta_min=lr * 0.1)

    def get_batch(data_source: torch.Tensor):
        high = len(data_source) - seq_len - 1
        ix = torch.randint(0, high, (batch_size,))
        x = torch.stack([data_source[i : i + seq_len] for i in ix])
        y = torch.stack([data_source[i + 1 : i + seq_len + 1] for i in ix])
        return x.to(device), y.to(device)

    print("\nStarting Training Run...")
    model.train()
    t_start = time.perf_counter()

    for step in range(1, max_steps + 1):
        x, y = get_batch(train_tokens)
        optimizer.zero_grad(set_to_none=True)

        pred_logits, recon_logits, metrics = model(x, targets=y)
        loss = metrics["total_loss"]
        loss.backward()

        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        if step % 100 == 0 or step == 1:
            model.eval()
            with torch.no_grad():
                vx, vy = get_batch(val_tokens)
                v_pred, _, v_metrics = model(vx, targets=vy)
                v_loss = v_metrics["loss_pred"].item()
                v_ppl = math.exp(min(v_loss, 20.0))

            dt = time.perf_counter() - t_start
            tok_per_sec = (step * batch_size * seq_len) / max(dt, 1e-6)
            lr_curr = optimizer.param_groups[0]["lr"]

            print(
                f"[Step {step:4d}/{max_steps:4d}] "
                f"Train Loss: {loss.item():.4f} | "
                f"Val Loss: {v_loss:.4f} | "
                f"Val PPL: {v_ppl:6.2f} | "
                f"LR: {lr_curr:.2e} | "
                f"Throughput: {tok_per_sec:,.0f} tok/s"
            )
            model.train()

    # Save trained fluency model
    torch.save(model.state_dict(), output_checkpoint)
    print(f"\n[✓] Fluency pretraining finished! Saved checkpoint to: {output_checkpoint}")

    # Generate test completions using top-k temperature sampling with repetition penalty
    print("\n" + "=" * 76)
    print("Zero-Shot Qualitative Evaluation (Top-k=40, Temperature=0.7, Rep-Penalty=1.2):")
    print("=" * 76)
    model.eval()
    test_prompts = [
        "def quicksort(arr):",
        "Once upon a time, a little girl named Lily",
    ]

    for p in test_prompts:
        prompt_ids = tok.encode(p)
        curr = torch.tensor([prompt_ids], dtype=torch.long, device=device)
        generated_tokens = []

        with torch.no_grad():
            for _ in range(40):
                logits, _, _ = model(curr)
                next_logits = logits[0, -1, :].clone() / 0.7

                # Repetition penalty
                for token_id in set(curr[0].tolist()):
                    if next_logits[token_id] > 0:
                        next_logits[token_id] /= 1.2
                    else:
                        next_logits[token_id] *= 1.2

                # Top-k filtering
                topk_vals, topk_inds = torch.topk(next_logits, k=40)
                probs = F.softmax(topk_vals, dim=-1)
                idx_choice = torch.multinomial(probs, num_samples=1)
                next_tok = topk_inds[idx_choice].unsqueeze(0)

                curr = torch.cat([curr, next_tok], dim=1)

        gen_text = tok.decode(curr[0].tolist())
        print(f"\n--- Prompt: {repr(p)} ---")
        print(gen_text)


if __name__ == "__main__":
    train_fluency_lm()
