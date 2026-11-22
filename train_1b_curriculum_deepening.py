"""
train_1b_curriculum_deepening.py
Deepens training of the 1.14B Foundation Model on the 26.12M clean Frontier Technical Stream.
Continues from checkpoints/imf_foundation_1b_sft.pt for 600 steps.
Applies:
- Dynamic learning rate cosine schedule (2.5e-5 -> 3e-6)
- Gradient accumulation (8x) + bfloat16 mixed precision
- Activation checkpointing (fits comfortably within 16GB VRAM)
- Periodic validation checkpointing and .imf container updates
"""

import os
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
import math
import time
import sys
import torch
import torch.nn as nn

from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.kronecker_factorized_adamw import KroneckerFactorizedAdamW
from imf.imf_container import IMFWriter

def train_curriculum_deepening(
    max_steps: int = 600,
    lr: float = 2.5e-5,
    min_lr: float = 3.0e-6,
    batch_size: int = 1,
    grad_accum_steps: int = 8,
    seq_len: int = 128,
):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 80)
    print("  IMF 1.14B Foundation Model: Curriculum Deepening (600 Steps)")
    print("=" * 80)
    print(f"Device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    base_checkpoint_pt = "checkpoints/imf_foundation_1b_sft.pt"
    sft_tokens_path = "data/frontier_corpus/frontier_technical_tokens_4k.pt"
    tokenizer_path = "checkpoints/hybrid_bpe_tokenizer_4k.json"
    output_pt = "checkpoints/imf_foundation_1b_sft.pt"
    output_imf = "checkpoints/imf_foundation_1b.imf"

    tok = CodeBPETokenizer.load(tokenizer_path)
    vocab_size = len(tok.vocab)

    # 1. Load Tokens
    print(f"[*] Loading clean frontier technical stream from {sft_tokens_path}...")
    tokens = torch.load(sft_tokens_path, map_location="cpu").long()
    n_tokens = len(tokens)
    split = int(0.98 * n_tokens)
    train_tokens = tokens[:split]
    val_tokens = tokens[split:]
    print(f"[✓] Train Tokens: {len(train_tokens):,} | Val Tokens: {len(val_tokens):,}")

    # 2. Instantiate and Load 1.14B Weights
    print(f"[*] Loading weights from {base_checkpoint_pt}...")
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
    torch.cuda.empty_cache()

    # Enable activation checkpointing on all layers
    for layer in model.layers:
        layer.use_checkpointing = True

    # Freeze Lie group rotation generators to preserve energy enclosure geometry
    for layer in model.layers:
        layer.ssm.raw_generator.requires_grad = False
        layer.ssm.log_delta.requires_grad = False

    model.train()
    print(f"[✓] 1.14B Model loaded on {device}. Parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"    Current GPU VRAM: {torch.cuda.memory_allocated() / (1024**3):.2f} GB / 16.0 GB")

    # 3. Optimizer Setup: KroneckerFactorizedAdamW (16MB Footprint)
    optimizer = KroneckerFactorizedAdamW(
        model.parameters(),
        lr=lr,
        betas=(0.0, 0.999),
        weight_decay=0.01,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max_steps, eta_min=min_lr)

    def get_batch(source):
        ix = torch.randint(0, len(source) - seq_len - 1, (batch_size,))
        x = torch.stack([source[i : i + seq_len] for i in ix]).to(device)
        y = torch.stack([source[i + 1 : i + 1 + seq_len] for i in ix]).to(device)
        return x, y

    print(f"\n[*] Commencing 1.14B Curriculum Deepening ({max_steps} steps, Batch={batch_size*grad_accum_steps}, SeqLen={seq_len})...")
    start_time = time.perf_counter()
    running_loss = 0.0

    for step in range(1, max_steps + 1):
        optimizer.zero_grad()
        loss_accum = 0.0

        for _ in range(grad_accum_steps):
            x, y = get_batch(train_tokens)
            with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                logits, _, metrics = model(x, targets=y)
                loss = metrics["total_loss"] / grad_accum_steps
            loss.backward()
            loss_accum += loss.item()

        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

        running_loss += loss_accum

        if step % 25 == 0 or step == 1 or step == max_steps:
            model.eval()
            with torch.no_grad():
                vx, vy = get_batch(val_tokens)
                with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                    _, _, v_metrics = model(vx, targets=vy)
                    v_loss = v_metrics["loss_pred"].item()
                    v_ppl = math.exp(min(v_loss, 20.0))
            model.train()

            avg_loss = running_loss / (25 if step % 25 == 0 else 1)
            running_loss = 0.0
            cur_lr = scheduler.get_last_lr()[0]
            elapsed = time.perf_counter() - start_time
            tok_per_sec = (step * batch_size * grad_accum_steps * seq_len) / elapsed
            print(f"Step {step:3d}/{max_steps} | Train Loss: {avg_loss:.4f} | Val Loss: {v_loss:.4f} | "
                  f"Val PPL: {v_ppl:6.2f} | LR: {cur_lr:.2e} | {tok_per_sec:.0f} tok/s | Elapsed: {elapsed/60:.1f}m")

        # Save milestone checkpoint every 200 steps
        if step % 200 == 0:
            print(f"[*] Checkpoint milestone at step {step}: Saving PyTorch weights...")
            cpu_sd = {k: v.cpu() for k, v in model.state_dict().items()}
            torch.save(cpu_sd, output_pt)
            del cpu_sd

    # 4. Final Packaging
    print("\n[*] Packaging upgraded 1.14B weights into PyTorch and .imf container...")
    model.eval()
    cpu_state_dict = {k: v.cpu() for k, v in model.state_dict().items()}
    torch.save(cpu_state_dict, output_pt)
    print(f"[✓] Saved PyTorch weights to {output_pt}")

    writer = IMFWriter(output_imf, model_config={
        "vocab_size": vocab_size,
        "d_model": 576,
        "num_layers": 16,
        "num_heads": 8,
        "polytope_dim": 8,
        "num_experts": 16,
        "alignment": "Curriculum-Deepened-600",
    })
    for k, v in cpu_state_dict.items():
        writer.add_tensor(k, v)
    writer.write()
    print(f"[✓] Successfully upgraded {output_imf} in-place!")

if __name__ == "__main__":
    train_curriculum_deepening()
