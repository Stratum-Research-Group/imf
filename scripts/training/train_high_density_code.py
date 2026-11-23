"""
High-Density Code & Reasoning Multiplier Pretraining Engine.
Trains IMF Joint-Reconstruction & Polytope MoE Model on 20,000 verified programming problems
from CodeAlpaca combined with the 11.6M token hybrid corpus to drastically elevate
natural language instruction following and programmatic code generation.
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import time
import math
import json
import torch
import torch.nn.functional as F
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM


def assemble_and_train_high_density_code(
    code_alpaca_path: str = "data/expanded_corpus/code_alpaca_20k.json",
    base_tokens_path: str = "data/expanded_corpus/finetune_tokens_4k.pt",
    tokenizer_path: str = "checkpoints/hybrid_bpe_tokenizer_4k.json",
    init_checkpoint: str = "checkpoints/imf_fluency_lm_4k.pt",
    output_checkpoint: str = "checkpoints/imf_fluency_lm_4k.pt",
    max_steps: int = 1000,
    batch_size: int = 16,
    seq_len: int = 128,
    lr: float = 6e-5,
):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 76)
    print("IMF High-Density Code & Reasoning Multiplier Pretraining")
    print("=" * 76)

    tok = CodeBPETokenizer.load(tokenizer_path)
    vocab_size = len(tok.vocab)

    # 1. Load Code Alpaca and convert to structured training text
    print(f"[*] Loading Code Alpaca from {code_alpaca_path}...")
    with open(code_alpaca_path, "r", encoding="utf-8") as f:
        code_data = json.load(f)

    code_text_blocks = []
    for item in code_data:
        inst = item.get("instruction", "").strip()
        inp = item.get("input", "").strip()
        out = item.get("output", "").strip()
        if not out:
            continue
        if inp:
            block = f"# Problem: {inst}\n# Context: {inp}\n{out}\n"
        else:
            block = f"# Problem: {inst}\n{out}\n"
        code_text_blocks.append(block)

    full_code_text = "\n\n".join(code_text_blocks)
    print(f"[*] Formatted {len(code_text_blocks):,} programming problems ({len(full_code_text):,} chars).")

    # 2. Tokenize Code Blocks
    code_tokens = torch.tensor(tok.encode(full_code_text), dtype=torch.long)
    print(f"[*] Encoded {len(code_tokens):,} code tokens.")

    # 3. Interleave with base hybrid tokens (Stories + Lean 4 + Repo Code)
    base_tokens = torch.load(base_tokens_path, map_location="cpu").long()
    combined_tokens = torch.cat([base_tokens, code_tokens])
    n_tokens = len(combined_tokens)
    print(f"[✓] Total active pretraining tokens: {n_tokens:,} ({n_tokens/1e6:.2f}M tokens)")

    # 4. Initialize Model
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
        print(f"[*] Resuming from {init_checkpoint}...")
        model.load_state_dict(torch.load(init_checkpoint, map_location=device))

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, betas=(0.9, 0.95), weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_steps, eta_min=lr * 0.1)

    split = int(0.95 * n_tokens)
    train_tokens, val_tokens = combined_tokens[:split], combined_tokens[split:]

    def get_batch(source):
        high = len(source) - seq_len - 1
        ix = torch.randint(0, high, (batch_size,))
        x = torch.stack([source[i : i + seq_len] for i in ix])
        y = torch.stack([source[i + 1 : i + seq_len + 1] for i in ix])
        return x.to(device), y.to(device)

    print("\nStarting High-Density Pretraining Execution...")
    model.train()
    t0 = time.perf_counter()

    for step in range(1, max_steps + 1):
        x, y = get_batch(train_tokens)
        optimizer.zero_grad(set_to_none=True)

        _, _, metrics = model(x, targets=y)
        loss = metrics["total_loss"]
        loss.backward()

        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        if step % 100 == 0 or step == 1:
            model.eval()
            with torch.no_grad():
                vx, vy = get_batch(val_tokens)
                _, _, v_metrics = model(vx, targets=vy)
                v_loss = v_metrics["loss_pred"].item()
                v_ppl = math.exp(min(v_loss, 20.0))

            dt = time.perf_counter() - t0
            tok_s = (step * batch_size * seq_len) / max(dt, 1e-6)
            lr_curr = optimizer.param_groups[0]["lr"]

            print(
                f"[High-Density Step {step:4d}/{max_steps:4d}] "
                f"Train Loss: {loss.item():.4f} | "
                f"Val Loss: {v_loss:.4f} | "
                f"Val PPL: {v_ppl:6.2f} | "
                f"LR: {lr_curr:.2e} | "
                f"Throughput: {tok_s:,.0f} tok/s"
            )
            model.train()

    torch.save(model.state_dict(), output_checkpoint)
    print(f"\n[✓] High-Density training complete! Checkpoint saved to: {output_checkpoint}")


if __name__ == "__main__":
    assemble_and_train_high_density_code()
