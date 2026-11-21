"""
Fine-tuning pipeline for IMF-129.8M on the expanded 11.6M-token hybrid corpus
(TinyStoriesV2 full dialogues + TheAlgorithms standard Python library + IMF Lean 4 theorems).
Initializes from checkpoints/imf_fluency_lm_4k.pt to accelerate convergence.
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import time
import math
import torch
import torch.nn.functional as F
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM


def run_expanded_finetune(
    tokens_path: str = "data/expanded_corpus/finetune_tokens_4k.pt",
    tokenizer_path: str = "checkpoints/hybrid_bpe_tokenizer_4k.json",
    init_checkpoint: str = "checkpoints/imf_fluency_lm_4k.pt",
    output_checkpoint: str = "checkpoints/imf_fluency_lm_4k.pt",
    max_steps: int = 1500,
    batch_size: int = 16,
    seq_len: int = 128,
    lr: float = 8e-5,
):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 76)
    print("IMF Expanded Hybrid Fine-Tuning Engine (11.6M Tokens)")
    print("=" * 76)
    print(f"Device: {device} | Sequence Length: {seq_len} | Batch Size: {batch_size}")

    tokens = torch.load(tokens_path, map_location="cpu").long()
    n_tokens = len(tokens)
    print(f"Loaded {n_tokens:,} fine-tuning tokens from {tokens_path}")

    # 95% train / 5% val
    split_idx = int(0.95 * n_tokens)
    train_tokens = tokens[:split_idx]
    val_tokens = tokens[split_idx:]

    tok = CodeBPETokenizer.load(tokenizer_path)
    vocab_size = len(tok.vocab)
    print(f"Loaded tokenizer from {tokenizer_path} (Vocab size: {vocab_size})")

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

    if os.path.exists(init_checkpoint):
        print(f"[*] Resuming weights from {init_checkpoint}...")
        state_dict = torch.load(init_checkpoint, map_location=device)
        model.load_state_dict(state_dict)
    else:
        print("[!] No prior checkpoint found, starting fresh initialization.")

    total_params = sum(p.numel() for p in model.parameters())
    print(f"Model parameters: {total_params:,} ({total_params/1e6:.2f}M)")

    # Fine-tuning optimizer with gentle cosine decay
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.95), weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_steps, eta_min=lr * 0.1)

    def get_batch(data_source: torch.Tensor):
        high = len(data_source) - seq_len - 1
        ix = torch.randint(0, high, (batch_size,))
        x = torch.stack([data_source[i : i + seq_len] for i in ix])
        y = torch.stack([data_source[i + 1 : i + seq_len + 1] for i in ix])
        return x.to(device), y.to(device)

    print("\nStarting Fine-Tuning Execution...")
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

        if step % 150 == 0 or step == 1:
            model.eval()
            with torch.no_grad():
                # Evaluate across multiple validation batches for stable estimate
                v_losses = []
                for _ in range(5):
                    vx, vy = get_batch(val_tokens)
                    _, _, v_metrics = model(vx, targets=vy)
                    v_losses.append(v_metrics["loss_pred"].item())
                v_loss = sum(v_losses) / len(v_losses)
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

    # Save fine-tuned checkpoint
    torch.save(model.state_dict(), output_checkpoint)
    print(f"\n[✓] Fine-tuning completed! Saved weights to: {output_checkpoint}")

    # Inspect test prompts
    print("\n" + "=" * 76)
    print("Fine-Tuned Qualitative Generations (Top-k=40, Temp=0.6, Rep-Penalty=1.2):")
    print("=" * 76)
    model.eval()
    test_prompts = [
        "Once upon a time, a little girl named Lily",
        "def quicksort(arr):",
        "def binary_search(arr, target):",
        "theorem add_comm (n m : Nat) :",
    ]

    for p in test_prompts:
        p_ids = tok.encode(p)
        curr = torch.tensor([p_ids], dtype=torch.long, device=device)
        with torch.no_grad():
            for _ in range(45):
                logits, _, _ = model(curr)
                next_logits = logits[0, -1, :].clone() / 0.6
                for tid in set(curr[0].tolist()):
                    if next_logits[tid] > 0:
                        next_logits[tid] /= 1.2
                    else:
                        next_logits[tid] *= 1.2
                val, idx = torch.topk(next_logits, min(40, next_logits.size(-1)))
                probs = F.softmax(val, dim=-1)
                choice = torch.multinomial(probs, num_samples=1)
                nxt = torch.gather(idx, -1, choice)
                curr = torch.cat([curr, nxt.unsqueeze(0)], dim=1)

        gen_text = tok.decode(curr[0].tolist())
        print(f"\n--- Prompt: '{p}' ---")
        print(gen_text)


if __name__ == "__main__":
    run_expanded_finetune(max_steps=1500, lr=8e-5)
