"""
Train IMF-235M Foundation Model using LieRiemannianAdamW + Activation Checkpointing.
Applies:
1. Lie algebra matrix-rotations along SO(d) geodesics via Cayley transform for continuous SSM rotators.
2. Formally verified 8-bit quantized Cut-RSI optimization for non-rotator weights.
3. Gradient activation checkpointing to avoid peak activation memory accumulation.
4. Pretraining & high-density code reasoning on the 15.33M-token hybrid corpus.
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
from imf.lie_riemannian_adamw import LieRiemannianAdamW


def train_235m_with_lie_riemannian(
    code_alpaca_path: str = "data/expanded_corpus/code_alpaca_20k.json",
    base_tokens_path: str = "data/expanded_corpus/finetune_tokens_4k.pt",
    tokenizer_path: str = "checkpoints/hybrid_bpe_tokenizer_4k.json",
    init_checkpoint: str = "checkpoints/imf_scaled_235m_fluency.pt",
    output_checkpoint: str = "checkpoints/imf_scaled_235m_fluency.pt",
    max_steps: int = 300,
    batch_size: int = 8,
    seq_len: int = 128,
    lr: float = 8e-5,
):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 80)
    print("IMF-235M Pretraining with LieRiemannianAdamW & Gradient Checkpointing")
    print("=" * 80)

    tok = CodeBPETokenizer.load(tokenizer_path)
    vocab_size = len(tok.vocab)

    # 1. Load active tokens
    print(f"[*] Preparing high-density tokens...")
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

    # 2. Instantiate IMF-235M Model
    model = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=384,
        num_layers=6,
        num_heads=6,
        polytope_dim=8,
        num_experts=20,
        top_k=2,
        max_seq_len=seq_len,
        alpha_recon=0.2,
    )
    
    if os.path.exists(init_checkpoint):
        print(f"[*] Resuming from checkpoint: {init_checkpoint}")
        model.load_state_dict(torch.load(init_checkpoint, map_location="cpu"))

    # Enable activation checkpointing on all OmniBlocks!
    for layer in model.layers:
        layer.use_checkpointing = True

    model = model.to(device)
    print(f"[✓] Model loaded on {device} (Total parameters: {sum(p.numel() for p in model.parameters()):,})")

    # 3. Partition parameters into SO(d) rotators vs. General feedforward
    rotator_params = []
    general_params = []

    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        # Rotators in Lie SSM: raw_generator is [heads, head_dim, head_dim] or [d, d]
        if "raw_generator" in name or ("corners" in name and param.dim() == 2 and param.size(0) == param.size(1)):
            rotator_params.append(param)
        elif param.dim() == 2 and param.size(0) == param.size(1) and param.size(0) <= 64:
            rotator_params.append(param)
        else:
            general_params.append(param)

    print(f"[*] Parameter separation: {len(rotator_params)} SO(d) rotator tensors, {len(general_params)} general tensors.")

    param_groups = [
        {"params": rotator_params, "is_rotator": True, "lr": lr, "weight_decay": 0.0},
        {"params": general_params, "is_rotator": False, "lr": lr, "weight_decay": 0.01},
    ]

    optimizer = LieRiemannianAdamW(param_groups, betas=(0.9, 0.95))
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_steps, eta_min=lr * 0.1)

    split = int(0.95 * n_tokens)
    train_tokens, val_tokens = combined_tokens[:split], combined_tokens[split:]

    def get_batch(source):
        high = len(source) - seq_len - 1
        ix = torch.randint(0, high, (batch_size,))
        x = torch.stack([source[i : i + seq_len] for i in ix])
        y = torch.stack([source[i + 1 : i + seq_len + 1] for i in ix])
        return x.to(device), y.to(device)

    print("\n[*] Starting optimization...")
    model.train()
    t0 = time.perf_counter()

    for step in range(1, max_steps + 1):
        x, y = get_batch(train_tokens)
        optimizer.zero_grad()

        _, _, metrics = model(x, targets=y)
        loss = metrics["total_loss"]
        loss.backward()

        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        if step % 50 == 0 or step == 1:
            model.eval()
            with torch.no_grad():
                vx, vy = get_batch(val_tokens)
                _, _, v_metrics = model(vx, targets=vy)
                v_loss = v_metrics["loss_pred"].item()
                v_ppl = math.exp(min(v_loss, 20.0))

            dt = time.perf_counter() - t0
            tok_s = (step * batch_size * seq_len) / max(dt, 1e-6)
            mem_mb = torch.cuda.max_memory_allocated() / (1024 * 1024) if torch.cuda.is_available() else 0.0

            print(
                f"[Step {step:4d}/{max_steps:4d}] "
                f"Train Loss: {loss.item():.4f} | "
                f"Val Loss: {v_loss:.4f} | "
                f"Val PPL: {v_ppl:6.2f} | "
                f"VRAM: {mem_mb:,.0f} MB | "
                f"Speed: {tok_s:,.0f} tok/s"
            )
            model.train()

    torch.save(model.state_dict(), output_checkpoint)
    print(f"\n[✓] 235M Fine-Tuning complete! Saved checkpoint to: {output_checkpoint}")


if __name__ == "__main__":
    train_235m_with_lie_riemannian()
