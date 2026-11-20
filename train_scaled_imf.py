"""
train_scaled_imf.py
Multi-layer Scaled IMF Pretraining on TinyStories (10M parameter regime, 6 layers, d_model=256, 8 heads).
Evaluates convergence, perplexity, and saves production checkpoint for streaming chat generation.
"""

import argparse
import time
import math
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf.bpe_tokenizer import BPETokenizer
from train_imf_corpus import IMFMultiHeadDecoderBlock


class ScaledIMFDecoderLM(nn.Module):
    """Deep Multi-Layer IMF Language Model (SAVG + 10D Decayotton Virtual Grid)."""
    def __init__(
        self,
        vocab_size: int,
        d_model: int = 256,
        num_heads: int = 8,
        n_layers: int = 6,
        preset: str = "decayotton_orthoplex",
        use_higher_arity: bool = False,
        arity_rank: int = 16,
    ):
        super().__init__()
        self.d_model = d_model
        self.vocab_size = vocab_size
        self.use_higher_arity = use_higher_arity
        self.tok_embed = nn.Embedding(vocab_size, d_model)
        self.blocks = nn.ModuleList([
            IMFMultiHeadDecoderBlock(
                d_model, num_heads, preset=preset, use_higher_arity=use_higher_arity, arity_rank=arity_rank
            )
            for _ in range(n_layers)
        ])
        self.ln_f = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size, bias=False)
        self.head.weight = self.tok_embed.weight

    def forward(self, idx: torch.Tensor):
        x = self.tok_embed(idx)
        for block in self.blocks:
            x = block(x)
        return self.head(self.ln_f(x))

    def init_streaming_states(self, batch_size: int, device: torch.device):
        return [b.savg.init_state(batch_size, device) for b in self.blocks]

    def generate_step(self, token_t: torch.Tensor, states):
        x = self.tok_embed(token_t)
        next_states = []
        for i, block in enumerate(self.blocks):
            x, next_st = block.step(x, states[i])
            next_states.append(next_st)
        return self.head(self.ln_f(x)), next_states


def load_dataset(corpus_path: Path, bpe_vocab_path: Path):
    cached_tokens_path = corpus_path.with_suffix(".pt")
    tokenizer = BPETokenizer.load(bpe_vocab_path)
    if cached_tokens_path.exists():
        print(f"[*] Loading pre-encoded tokens from cache: {cached_tokens_path}...")
        encoded = torch.load(cached_tokens_path)
    else:
        print(f"[*] Encoding {corpus_path} with BPE...")
        text = corpus_path.read_text(encoding="utf-8")
        encoded = torch.tensor(tokenizer.encode(text), dtype=torch.long)
        torch.save(encoded, cached_tokens_path)
        print(f"    Saved token cache ({len(encoded):,} tokens) to {cached_tokens_path}")

    n = int(0.95 * len(encoded))
    train_data = encoded[:n]
    val_data = encoded[n:]
    return tokenizer, train_data, val_data


def get_batch(data: torch.Tensor, batch_size: int, seq_len: int, device: torch.device):
    idx = torch.randint(0, len(data) - seq_len - 1, (batch_size,))
    x = torch.stack([data[i:i + seq_len] for i in idx]).to(device)
    y = torch.stack([data[i + 1:i + seq_len + 1] for i in idx]).to(device)
    return x, y


def evaluate(model, val_data, seq_len, device, eval_batches=25):
    model.eval()
    losses = []
    with torch.no_grad():
        for _ in range(eval_batches):
            x, y = get_batch(val_data, batch_size=8, seq_len=seq_len, device=device)
            logits = model(x)
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), y.view(-1))
            losses.append(loss.item())
    avg_loss = sum(losses) / len(losses)
    ppl = math.exp(min(avg_loss, 20.0))
    return avg_loss, ppl


def main():
    parser = argparse.ArgumentParser(description="Multi-layer Scaled IMF Pretraining on TinyStories")
    parser.add_argument("--d_model", type=int, default=256, help="Embedding dimension")
    parser.add_argument("--num_heads", type=int, default=8, help="Number of heads")
    parser.add_argument("--n_layers", type=int, default=6, help="Number of layers")
    parser.add_argument("--seq_len", type=int, default=128, help="Sequence length")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size")
    parser.add_argument("--train_steps", type=int, default=200, help="Training steps")
    parser.add_argument("--lr", type=float, default=1.5e-3, help="Peak learning rate")
    parser.add_argument("--use_higher_arity", action="store_true", help="Enable CP-factorized 3-simplex hyperface binding")
    parser.add_argument("--save_path", type=str, default="checkpoints/imf_tinystories_scaled.pt", help="Checkpoint save path")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 85)
    print(f"SCALED IMF PRETRAINING (Multi-Layer Polytope Virtual Grid) on {device}")
    print("=" * 85)

    corpus_file = Path("data/tinystories_sample.txt")
    bpe_file = Path("data/tinystories_bpe.json")
    if not corpus_file.exists() or not bpe_file.exists():
        raise FileNotFoundError("Missing TinyStories dataset or BPE tokenizer json in data/")

    tokenizer, train_data, val_data = load_dataset(corpus_file, bpe_file)
    print(f"[*] Dataset: TinyStories (Train: {len(train_data):,} tokens, Val: {len(val_data):,} tokens)")
    print(f"[*] Vocabulary: {tokenizer.vocab_size} tokens")

    model = ScaledIMFDecoderLM(
        vocab_size=tokenizer.vocab_size,
        d_model=args.d_model,
        num_heads=args.num_heads,
        n_layers=args.n_layers,
        preset="decayotton_orthoplex",
        use_higher_arity=args.use_higher_arity,
    ).to(device)

    params = sum(p.numel() for p in model.parameters())
    print(f"[*] Architecture: {args.n_layers} layers, d_model={args.d_model}, {args.num_heads} heads ({params:,} parameters)")

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)

    # Cosine annealing schedule with warmup
    warmup_steps = min(500, args.train_steps // 10)
    def get_lr(step):
        if step < warmup_steps:
            return float(step) / float(max(1, warmup_steps))
        progress = float(step - warmup_steps) / float(max(1, args.train_steps - warmup_steps))
        return 0.1 + 0.9 * 0.5 * (1.0 + math.cos(math.pi * progress))

    scheduler = torch.optim.lr_scheduler.LambdaLR(opt, lr_lambda=get_lr)

    print(f"\n[*] Starting Pretraining for {args.train_steps} steps (Warmup: {warmup_steps} steps)...")
    model.train()
    t0 = time.perf_counter()

    for step in range(1, args.train_steps + 1):
        x, y = get_batch(train_data, batch_size=args.batch_size, seq_len=args.seq_len, device=device)
        opt.zero_grad()
        logits = model(x)
        loss = F.cross_entropy(logits.view(-1, tokenizer.vocab_size), y.view(-1))
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        scheduler.step()

        if step % 500 == 0 or step == 100 or step == 1:
            curr_lr = opt.param_groups[0]["lr"]
            print(f"  Step {step:5d}/{args.train_steps} | Loss: {loss.item():.4f} | LR: {curr_lr:.2e}")

    total_time = (time.perf_counter() - t0) * 1000.0
    ms_per_step = total_time / args.train_steps

    val_loss, val_ppl = evaluate(model, val_data, seq_len=args.seq_len, device=device)
    print(f"\n[+] Training Complete:")
    print(f"    Total Time : {total_time:.1f} ms ({ms_per_step:.2f} ms/step)")
    print(f"    Val Loss   : {val_loss:.4f}")
    print(f"    Val PPL    : {val_ppl:.2f}")

    # Save checkpoint
    save_path = Path(args.save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({
        "model_state": model.state_dict(),
        "vocab_size": tokenizer.vocab_size,
        "d_model": args.d_model,
        "num_heads": args.num_heads,
        "n_layers": args.n_layers,
        "preset": "decayotton_orthoplex",
        "tokenizer_meta": {
            "vocab": tokenizer.vocab,
            "merges": tokenizer.merges,
        }
    }, save_path)
    print(f"[+] Saved model checkpoint to {save_path}")


if __name__ == "__main__":
    main()
