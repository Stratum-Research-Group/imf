"""
Train 1.14 Billion Parameter IMF Foundation Model with:
1. INT4 / FP8 compressed SwiGLU / MoE parameters via ETHQuantizedLinear.
2. 16MB KroneckerFactorizedAdamW optimizer.
3. Gradient activation checkpointing (sub-linear memory scaling).
4. Multi-step pretraining on the 15.33M token high-density code and reasoning corpus.
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
from imf.kronecker_factorized_adamw import KroneckerFactorizedAdamW


def train_1b_foundation_model(
    code_alpaca_path: str = "data/expanded_corpus/code_alpaca_20k.json",
    base_tokens_path: str = "data/expanded_corpus/finetune_tokens_4k.pt",
    tokenizer_path: str = "checkpoints/hybrid_bpe_tokenizer_4k.json",
    output_checkpoint: str = "checkpoints/imf_foundation_1b.pt",
    max_steps: int = 200,
    batch_size: int = 2,
    seq_len: int = 128,
    lr: float = 1e-4,
):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 80)
    print("IMF 1.14 Billion Parameter Foundation Pretraining (16MB Optimizer + Chkpt)")
    print("=" * 80)

    tok = CodeBPETokenizer.load(tokenizer_path)
    vocab_size = len(tok.vocab)

    # 1. Load active tokens
    print("[*] Loading high-density pretraining tokens...")
    base_tokens = torch.load(base_tokens_path, map_location="cpu").long()
    with open(code_alpaca_path, "r", encoding="utf-8") as f:
        code_data = json.load(f)
    code_blocks = [
        f"# Problem: {item.get('instruction', '').strip()}\n{item.get('output', '').strip()}\n"
        for item in code_data if item.get('output', '').strip()
    ]
    code_tokens = torch.tensor(tok.encode("\n\n".join(code_blocks)), dtype=torch.long)
    combined_tokens = torch.cat([base_tokens, code_tokens])
    n_tokens = len(combined_tokens)
    print(f"[✓] Active Corpus: {n_tokens:,} tokens ({n_tokens / 1e6:.2f}M tokens)")

    # 2. Instantiate 1.14B Model (16 layers, d_model=576, 16 experts per layer)
    print("[*] Instantiating 1.14B IMF Joint Reconstruction Predictor...")
    model = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=576,
        num_layers=16,
        num_heads=8,
        polytope_dim=8,
        num_experts=16,
        top_k=2,
        max_seq_len=seq_len,
        alpha_recon=0.2,
    )

    n_params = sum(p.numel() for p in model.parameters())
    print(f"[✓] Model instantiated: {n_params:,} parameters ({n_params / 1e9:.3f}B params)")

    # Enable activation checkpointing on all layers
    for layer in model.layers:
        layer.use_checkpointing = True

    model = model.to(device)
    static_mem_mb = torch.cuda.memory_allocated() / (1024 * 1024)
    print(f"[✓] Model loaded on {device}: {static_mem_mb:,.1f} MB ({static_mem_mb / 1024:.2f} GB)")

    # 3. Initialize 16MB Kronecker Factorized Optimizer
    optimizer = KroneckerFactorizedAdamW(
        model.parameters(),
        lr=lr,
        betas=(0.0, 0.999),
        weight_decay=0.01,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_steps, eta_min=lr * 0.1)

    split = int(0.95 * n_tokens)
    train_tokens, val_tokens = combined_tokens[:split], combined_tokens[split:]

    def get_batch(source):
        high = len(source) - seq_len - 1
        ix = torch.randint(0, high, (batch_size,))
        x = torch.stack([source[i : i + seq_len] for i in ix])
        y = torch.stack([source[i + 1 : i + seq_len + 1] for i in ix])
        return x.to(device), y.to(device)

    print("\n[*] Starting 1.14B parameter optimization loop...")
    model.train()
    t0 = time.perf_counter()

    for step in range(1, max_steps + 1):
        x, y = get_batch(train_tokens)
        optimizer.zero_grad()

        with torch.autocast("cuda", dtype=torch.bfloat16):
            _, _, metrics = model(x, targets=y)
            loss = metrics["total_loss"]

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        if step % 25 == 0 or step == 1:
            model.eval()
            with torch.no_grad():
                vx, vy = get_batch(val_tokens)
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    _, _, v_metrics = model(vx, targets=vy)
                    v_loss = v_metrics["loss_pred"].item()
                    v_ppl = math.exp(min(v_loss, 20.0))

            dt = time.perf_counter() - t0
            tok_s = (step * batch_size * seq_len) / max(dt, 1e-6)
            mem_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)

            print(
                f"[1.14B Step {step:3d}/{max_steps:3d}] "
                f"Train Loss: {loss.item():.4f} | "
                f"Val Loss: {v_loss:.4f} | "
                f"Val PPL: {v_ppl:6.2f} | "
                f"Peak VRAM: {mem_mb:,.0f} MB ({mem_mb / 1024:.2f} GB) | "
                f"Speed: {tok_s:,.0f} tok/s"
            )
            model.train()

    torch.save(model.state_dict(), output_checkpoint)
    print(f"\n[✓] 1.14B Pretraining complete! Checkpoint saved to: {output_checkpoint}")


if __name__ == "__main__":
    train_1b_foundation_model()
