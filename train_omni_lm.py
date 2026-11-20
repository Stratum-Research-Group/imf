"""
train_omni_lm.py
Pretraining Multi-Layer IMF-OmniLM on TinyStories.
Uses IMF-OmniBlock layers (Unitary SO(d_h) SSM, Continuous Simplex Convolution, SU(2) Gauge Polytope).
"""

import argparse
import time
import math
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf.bpe_tokenizer import BPETokenizer
from imf.omni_block import IMFOmniBlock


class IMFOmniLM(nn.Module):
    """
    Multi-layer Language Model built with IMF-OmniBlocks.
    """
    def __init__(
        self,
        vocab_size: int,
        d_model: int = 256,
        num_heads: int = 8,
        n_layers: int = 4,
        polytope_dim: int = 10,
        conv_rank: int = 32,
        conv_window: int = 6,
        use_triton_ssm: bool = False, # Set False during training for autograd compatibility
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.tok_embed = nn.Embedding(vocab_size, d_model)
        self.blocks = nn.ModuleList([
            IMFOmniBlock(
                d_model=d_model,
                num_heads=num_heads,
                polytope_dim=polytope_dim,
                conv_rank=conv_rank,
                conv_window=conv_window,
                use_triton_ssm=use_triton_ssm,
            )
            for _ in range(n_layers)
        ])
        self.ln_f = nn.RMSNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size, bias=False)
        self.head.weight = self.tok_embed.weight

    def forward(self, idx: torch.Tensor) -> torch.Tensor:
        x = self.tok_embed(idx)
        for block in self.blocks:
            x = block(x)
        return self.head(self.ln_f(x))


def get_batch(data: torch.Tensor, batch_size: int, seq_len: int, device: torch.device):
    ix = torch.randint(0, len(data) - seq_len - 1, (batch_size,))
    x = torch.stack([data[i:i + seq_len] for i in ix])
    y = torch.stack([data[i + 1:i + seq_len + 1] for i in ix])
    return x.to(device, non_blocking=True), y.to(device, non_blocking=True)


def train_omni_lm(
    corpus_pt: Path,
    vocab_path: Path,
    out_checkpoint: Path,
    d_model: int = 256,
    num_heads: int = 8,
    n_layers: int = 4,
    steps: int = 1000,
    batch_size: int = 16,
    seq_len: int = 128,
    lr: float = 8e-4,
    device_str: str = "cuda",
):
    device = torch.device(device_str if torch.cuda.is_available() else "cpu")
    print(f"[*] Training IMF-OmniLM on {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    tokenizer = BPETokenizer.load(vocab_path)
    vocab_size = tokenizer.vocab_size
    print(f"[*] Loaded BPE Tokenizer: vocab_size = {vocab_size}")

    data = torch.load(corpus_pt, weights_only=True)
    if isinstance(data, dict) and "tokens" in data:
        data = data["tokens"]
    n_tokens = len(data)
    n_val = min(50000, int(n_tokens * 0.05))
    train_data = data[:-n_val]
    val_data = data[-n_val:]
    print(f"[*] Corpus loaded: {len(train_data):,} train tokens, {len(val_data):,} val tokens")

    model = IMFOmniLM(
        vocab_size=vocab_size,
        d_model=d_model,
        num_heads=num_heads,
        n_layers=n_layers,
        polytope_dim=10,
        conv_rank=32,
        conv_window=6,
        use_triton_ssm=False,
    ).to(device)

    param_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[*] Model instantiated: {param_count:,} parameters ({param_count * 4 / (1024**2):.2f} MB)")

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-2, betas=(0.9, 0.98))
    criterion = nn.CrossEntropyLoss()

    best_val_loss = float("inf")
    t0 = time.time()
    model.train()

    print("\n" + "="*70)
    print(f"{'Step':<8} | {'Train Loss':<12} | {'Train PPL':<12} | {'ms/step':<10} | {'ETA':<10}")
    print("="*70)

    for step in range(1, steps + 1):
        step_t0 = time.time()
        x, y = get_batch(train_data, batch_size, seq_len, device)

        optimizer.zero_grad()
        logits = model(x)
        loss = criterion(logits.view(-1, vocab_size), y.view(-1))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        step_ms = (time.time() - step_t0) * 1000.0

        if step % 100 == 0 or step == steps:
            ppl = math.exp(min(loss.item(), 20.0))
            eta_s = (steps - step) * (step_ms / 1000.0)
            print(f"{step:<8} | {loss.item():<12.4f} | {ppl:<12.2f} | {step_ms:<10.1f} | {eta_s:<9.1f}s")

    total_time = time.time() - t0
    print("="*70)
    print(f"[✓] Pretraining completed in {total_time:.2f}s ({total_time / steps * 1000.0:.2f} ms/step average)")

    # Validation
    model.eval()
    val_losses = []
    with torch.no_grad():
        for _ in range(30):
            vx, vy = get_batch(val_data, batch_size, seq_len, device)
            v_logits = model(vx)
            v_loss = criterion(v_logits.view(-1, vocab_size), vy.view(-1))
            val_losses.append(v_loss.item())
    avg_val_loss = sum(val_losses) / len(val_losses)
    val_ppl = math.exp(min(avg_val_loss, 20.0))
    print(f"\n[★] Final Validation Loss: {avg_val_loss:.4f} | Validation Perplexity: {val_ppl:.2f}")

    # Save checkpoint
    out_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "step": steps,
        "model_state_dict": model.state_dict(),
        "d_model": d_model,
        "num_heads": num_heads,
        "n_layers": n_layers,
        "vocab_size": vocab_size,
        "val_loss": avg_val_loss,
        "val_ppl": val_ppl,
    }, out_checkpoint)
    print(f"[✓] Saved production checkpoint to {out_checkpoint}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seq-len", type=int, default=128)
    parser.add_argument("--d-model", type=int, default=256)
    parser.add_argument("--num-heads", type=int, default=8)
    parser.add_argument("--n-layers", type=int, default=4)
    args = parser.parse_args()

    train_omni_lm(
        corpus_pt=Path("data/tinystories_sample.pt"),
        vocab_path=Path("data/tinystories_bpe.json"),
        out_checkpoint=Path("checkpoints/imf_omni_lm.pt"),
        d_model=args.d_model,
        num_heads=args.num_heads,
        n_layers=args.n_layers,
        steps=args.steps,
        batch_size=args.batch_size,
        seq_len=args.seq_len,
    )
