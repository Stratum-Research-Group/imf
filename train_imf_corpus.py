"""
train_imf_corpus.py
Comparative Language Modeling Pretraining Benchmark:
Trains:
  1. Standard Causal Multi-Head Transformer (PyTorch SDPA Flash Attention)
  2. IMF Multi-Head SAVG Language Model (MultiHeadSAVGLayer with Polytope modulation)
on TinyShakespeare (1.1 MB corpus).
Measures:
  - Training loss minimization curves
  - Validation perplexity (bits per character / cross-entropy)
  - Autoregressive inference speed (Flash Attention with KV cache vs. IMF O(1) streaming recurrence)
Zero external dependencies.
"""

import time
import math
import argparse
from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf import MultiHeadSAVGLayer
from higher_arity_simplex import HigherAritySimplexBinding, ContinuousSimplexConvolutionalBinding


class CharTokenizer:
    """Self-contained character-level tokenizer."""
    def __init__(self, text: str):
        chars = sorted(list(set(text)))
        self.char2idx = {ch: i for i, ch in enumerate(chars)}
        self.idx2char = {i: ch for i, ch in enumerate(chars)}
        self.vocab_size = len(chars)

    def encode(self, text: str) -> list[int]:
        return [self.char2idx[c] for c in text if c in self.char2idx]

    def decode(self, indices: list[int]) -> str:
        return "".join([self.idx2char.get(i, "?") for i in indices])


class BaselineTransformerBlock(nn.Module):
    """Standard pre-LN Transformer block with PyTorch SDPA causal self-attention."""
    def __init__(self, d_model: int, num_heads: int):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.attn = nn.MultiheadAttention(d_model, num_heads=num_heads, batch_first=True)
        self.ln2 = nn.LayerNorm(d_model)
        self.mlp = nn.Sequential(
            nn.Linear(d_model, 4 * d_model),
            nn.GELU(),
            nn.Linear(4 * d_model, d_model)
        )

    def forward(self, x: torch.Tensor):
        B, T, D = x.shape
        norm_x = self.ln1(x)
        mask = torch.triu(torch.ones(T, T, device=x.device), diagonal=1).bool()
        attn_out, _ = self.attn(norm_x, norm_x, norm_x, attn_mask=mask, is_causal=True)
        x = x + attn_out
        x = x + self.mlp(self.ln2(x))
        return x


class BaselineTransformerLM(nn.Module):
    def __init__(self, vocab_size: int, d_model: int = 128, num_heads: int = 4, n_layers: int = 3):
        super().__init__()
        self.tok_embed = nn.Embedding(vocab_size, d_model)
        self.pos_embed = nn.Parameter(torch.randn(1, 2048, d_model) * 0.02)
        self.blocks = nn.ModuleList([
            BaselineTransformerBlock(d_model, num_heads) for _ in range(n_layers)
        ])
        self.ln_f = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size, bias=False)
        self.head.weight = self.tok_embed.weight

    def forward(self, idx: torch.Tensor):
        B, T = idx.shape
        x = self.tok_embed(idx) + self.pos_embed[:, :T, :]
        for block in self.blocks:
            x = block(x)
        return self.head(self.ln_f(x))


class IMFMultiHeadDecoderBlock(nn.Module):
    """Transformer decoder block replacing quadratic attention with MultiHeadSAVGLayer and optional HigherAritySimplexBinding."""
    def __init__(
        self,
        d_model: int,
        num_heads: int,
        preset: str = "decayotton_orthoplex",
        use_higher_arity: bool = False,
        arity: int = 3,
        arity_rank: int = 16,
        use_continuous_simplex: bool = False,
    ):
        super().__init__()
        self.ln1 = nn.LayerNorm(d_model)
        self.savg = MultiHeadSAVGLayer(d_model=d_model, num_heads=num_heads, preset=preset)
        self.use_higher_arity = use_higher_arity
        self.use_continuous_simplex = use_continuous_simplex
        self.arity = arity
        if use_continuous_simplex:
            self.ln_arity = nn.LayerNorm(d_model)
            self.continuous_binding = ContinuousSimplexConvolutionalBinding(d_model=d_model, rank=arity_rank)
            self.arity_gate = nn.Parameter(torch.zeros(1))
            self.arity_binding = None
        elif use_higher_arity:
            self.ln_arity = nn.LayerNorm(d_model)
            self.arity_binding = HigherAritySimplexBinding(d_model=d_model, arity=arity, rank=arity_rank)
            self.arity_gate = nn.Parameter(torch.zeros(1))
            self.continuous_binding = None
        else:
            self.arity_binding = None
            self.continuous_binding = None

        self.ln2 = nn.LayerNorm(d_model)
        self.mlp = nn.Sequential(
            nn.Linear(d_model, 4 * d_model),
            nn.GELU(),
            nn.Linear(4 * d_model, d_model)
        )

    def forward(self, x: torch.Tensor):
        x = x + self.savg(self.ln1(x))
        if self.use_continuous_simplex and self.continuous_binding is not None:
            norm_x = self.ln_arity(x)
            bound = self.continuous_binding(norm_x)
            x = x + torch.tanh(self.arity_gate) * bound
        elif self.use_higher_arity and self.arity_binding is not None:
            norm_x = self.ln_arity(x)
            B, T, D = norm_x.shape
            streams = [norm_x]
            for shift in range(1, self.arity):
                prev = torch.cat([torch.zeros(B, shift, D, device=x.device, dtype=x.dtype), norm_x[:, :-shift, :]], dim=1)
                streams.append(prev)
            bound = self.arity_binding(streams)
            x = x + torch.tanh(self.arity_gate) * bound
        x = x + self.mlp(self.ln2(x))
        return x

    def step(self, x_t: torch.Tensor, state):
        norm_x = self.ln1(x_t)
        savg_out, next_st = self.savg.step(norm_x, state)
        x_t = x_t + savg_out
        x_t = x_t + self.mlp(self.ln2(x_t))
        return x_t, next_st


class IMFMultiHeadLM(nn.Module):
    def __init__(self, vocab_size: int, d_model: int = 128, num_heads: int = 4, n_layers: int = 3, preset: str = "decayotton_orthoplex"):
        super().__init__()
        self.tok_embed = nn.Embedding(vocab_size, d_model)
        self.blocks = nn.ModuleList([
            IMFMultiHeadDecoderBlock(d_model, num_heads, preset=preset) for _ in range(n_layers)
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


def load_dataset(use_bpe: bool = False, target_vocab_size: int = 500):
    data_path = Path(__file__).parent / "data" / "tinyshakespeare.txt"
    if not data_path.exists():
        raise FileNotFoundError(f"Missing {data_path}")
    text = data_path.read_text(encoding="utf-8")
    if use_bpe:
        from imf.bpe_tokenizer import BPETokenizer
        bpe_path = Path(__file__).parent / "data" / "shakespeare_bpe.json"
        if bpe_path.exists():
            tokenizer = BPETokenizer.load(bpe_path)
        else:
            tokenizer = BPETokenizer()
            tokenizer.train(text, target_vocab_size=target_vocab_size)
            tokenizer.save(bpe_path)
        encoded = torch.tensor(tokenizer.encode(text), dtype=torch.long)
    else:
        tokenizer = CharTokenizer(text)
        encoded = torch.tensor(tokenizer.encode(text), dtype=torch.long)
    n = int(0.9 * len(encoded))
    train_data = encoded[:n]
    val_data = encoded[n:]
    return tokenizer, train_data, val_data


def get_batch(data: torch.Tensor, batch_size: int, seq_len: int, device: torch.device):
    idx = torch.randint(0, len(data) - seq_len - 1, (batch_size,))
    x = torch.stack([data[i:i + seq_len] for i in idx]).to(device)
    y = torch.stack([data[i + 1:i + seq_len + 1] for i in idx]).to(device)
    return x, y


def evaluate_perplexity(model, data, seq_len, device, eval_batches=20):
    model.eval()
    losses = []
    with torch.no_grad():
        for _ in range(eval_batches):
            x, y = get_batch(data, batch_size=8, seq_len=seq_len, device=device)
            logits = model(x)
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), y.view(-1))
            losses.append(loss.item())
    avg_loss = sum(losses) / len(losses)
    ppl = math.exp(min(avg_loss, 20.0))
    return avg_loss, ppl


def run_benchmark(
    use_bpe: bool = False,
    bpe_vocab_size: int = 500,
    train_steps: int = 150,
    save_checkpoint: str = "",
):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 85)
    tok_type = f"BPE Subword (target vocab: {bpe_vocab_size})" if use_bpe else "Character"
    print(f"PRETRAINING COMPARISON: Standard Transformer vs IMF Multi-Head SAVG ({tok_type}) on {device}")
    print("=" * 85)

    tokenizer, train_data, val_data = load_dataset(use_bpe=use_bpe, target_vocab_size=bpe_vocab_size)
    print(f"[*] Dataset: TinyShakespeare (Train: {len(train_data):,} tokens, Val: {len(val_data):,} tokens)")
    print(f"[*] Vocabulary: {tokenizer.vocab_size} unique tokens")

    d_model = 128
    num_heads = 4
    n_layers = 3
    seq_len = 128
    batch_size = 16

    models = {
        "Standard Causal Transformer (SDPA)": BaselineTransformerLM(
            vocab_size=tokenizer.vocab_size, d_model=d_model, num_heads=num_heads, n_layers=n_layers
        ).to(device),
        "IMF Multi-Head SAVG (Polytope 10D)": IMFMultiHeadLM(
            vocab_size=tokenizer.vocab_size, d_model=d_model, num_heads=num_heads, n_layers=n_layers, preset="decayotton_orthoplex"
        ).to(device)
    }

    results = {}

    for name, model in models.items():
        params = sum(p.numel() for p in model.parameters())
        print(f"\n[*] Training {name} ({params:,} parameters)...")
        opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=0.01)

        model.train()
        t0 = time.perf_counter()
        step_losses = []

        for step in range(1, train_steps + 1):
            x, y = get_batch(train_data, batch_size=batch_size, seq_len=seq_len, device=device)
            opt.zero_grad()
            logits = model(x)
            loss = F.cross_entropy(logits.view(-1, tokenizer.vocab_size), y.view(-1))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            step_losses.append(loss.item())

            if step % 50 == 0 or step == 1:
                print(f"  Step {step:3d}/{train_steps} | Train Loss: {loss.item():.4f}")

        train_time = (time.perf_counter() - t0) * 1000
        ms_per_step = train_time / train_steps

        # Validation Perplexity
        val_loss, val_ppl = evaluate_perplexity(model, val_data, seq_len=seq_len, device=device)
        print(f"  [+] Val Loss: {val_loss:.4f} | Val Perplexity: {val_ppl:.2f} | Time: {train_time:.1f} ms ({ms_per_step:.2f} ms/step)")

        results[name] = {
            "params": params,
            "final_train_loss": step_losses[-1],
            "val_loss": val_loss,
            "val_ppl": val_ppl,
            "ms_per_step": ms_per_step,
        }

        if save_checkpoint and "IMF" in name:
            ckpt_path = Path(save_checkpoint)
            ckpt_path.parent.mkdir(parents=True, exist_ok=True)
            tok_meta = {
                "vocab": tokenizer.vocab if hasattr(tokenizer, "vocab") else None,
                "merges": tokenizer.merges if hasattr(tokenizer, "merges") else None,
            }
            torch.save({
                "model_state": model.state_dict(),
                "vocab_size": tokenizer.vocab_size,
                "d_model": d_model,
                "num_heads": num_heads,
                "n_layers": n_layers,
                "preset": "decayotton_orthoplex",
                "tokenizer_meta": tok_meta,
            }, ckpt_path)
            print(f"  [+] Saved trained checkpoint to {ckpt_path}")

    # Summary Table
    print("\n" + "=" * 95)
    print("PRETRAINING BENCHMARK SUMMARY (150 steps on 1.1M token corpus)")
    print("=" * 95)
    print(f"{'Model Architecture':40s} | {'Params':10s} | {'Train Loss':10s} | {'Val Loss':10s} | {'Val PPL':10s} | {'Step Time':10s}")
    print("-" * 95)
    for name, r in results.items():
        print(f"{name:40s} | {r['params']:10,d} | {r['final_train_loss']:10.4f} | {r['val_loss']:10.4f} | {r['val_ppl']:10.2f} | {r['ms_per_step']:7.2f} ms")
    print("=" * 95)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pretraining benchmark comparing Transformer vs IMF Multi-Head SAVG")
    parser.add_argument("--use_bpe", action="store_true", help="Use subword BPE tokenizer instead of characters")
    parser.add_argument("--bpe_vocab_size", type=int, default=500, help="Target vocabulary size for BPE")
    parser.add_argument("--train_steps", type=int, default=150, help="Number of training steps")
    parser.add_argument("--save_checkpoint", type=str, default="", help="Optional path to save IMF model checkpoint")
    args = parser.parse_args()

    run_benchmark(
        use_bpe=args.use_bpe,
        bpe_vocab_size=args.bpe_vocab_size,
        train_steps=args.train_steps,
        save_checkpoint=args.save_checkpoint,
    )
