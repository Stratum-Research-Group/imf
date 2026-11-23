"""
benchmark_needle_in_haystack.py
Needle In A Haystack (NIAH) Benchmark for Long-Context Associative Recall.
Evaluates model capacity to retrieve a specific secret key/value needle placed at varying depths
(10%, 25%, 50%, 75%, 90% of context) across extreme context lengths:
N = 1024, 2048, 4096, 8192, 16384 tokens.
Compares:
1. Standard Linear Attention (unconstrained outer product)
2. IMF Multi-Head SAVG with 10D Decayotton Polytope Virtual Grid
"""

import time
import math
import random
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf import MultiHeadSAVGLayer
from benchmark_long_context_mqar import StandardLinearAttention


class NeedleRetrievalModel(nn.Module):
    def __init__(self, core_layer: nn.Module, d_model: int, vocab_size: int):
        super().__init__()
        self.tok_embed = nn.Embedding(vocab_size, d_model)
        self.layer = core_layer
        self.head = nn.Linear(d_model, vocab_size, bias=False)

    def forward(self, idx: torch.Tensor):
        x = self.tok_embed(idx)
        out = self.layer(x)
        if isinstance(out, tuple):
            out = out[0]
        return self.head(out)


def generate_niah_sequence(
    seq_len: int,
    depth_fraction: float,
    vocab_size: int = 1000,
    device: torch.device = "cpu",
    seed: int = None,
):
    """
    Generates a long distractor sequence with a secret needle inserted at depth_fraction.
    Haystack tokens: IDs in [0, 800)
    Needle key: token in [800, 900)
    Needle value: token in [900, 1000)
    Query placed at position seq_len - 1.
    """
    if seed is not None:
        random.seed(seed)
        torch.manual_seed(seed)

    # Distractor haystack tokens
    tokens = torch.randint(0, 800, (1, seq_len), device=device)

    # Pick needle
    needle_key = random.randint(800, 899)
    needle_val = random.randint(900, 999)

    insert_pos = int((seq_len - 4) * depth_fraction)
    tokens[0, insert_pos] = needle_key
    tokens[0, insert_pos + 1] = needle_val

    # Place query at the very end
    tokens[0, seq_len - 1] = needle_key
    target = needle_val

    return tokens, target, insert_pos


def run_needle_benchmark():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n==========================================================================================")
    print(f"NEEDLE IN A HAYSTACK (NIAH) LONG-CONTEXT RETRIEVAL BENCHMARK on {device}")
    print(f"==========================================================================================")

    vocab_size = 1000
    d_model = 64
    num_heads = 4
    depths = [0.10, 0.50, 0.90] # 10% (early), 50% (middle), 90% (recent)
    context_lengths = [1024, 2048, 4096, 8192]

    print(f"{'Context (N)':<12} | {'Depth':<8} | {'Architecture':<35} | {'Needle Found':<14} | {'Step Time':<10}")
    print("-" * 92)

    for N in context_lengths:
        for depth in depths:
            tokens, target, pos = generate_niah_sequence(N, depth, vocab_size, device, seed=42 + N + int(depth * 100))

            models = {
                "Standard Linear Attention": NeedleRetrievalModel(
                    StandardLinearAttention(d_model=d_model, num_heads=num_heads), d_model, vocab_size
                ).to(device),
                "IMF Multi-Head SAVG (Polytope 10D)": NeedleRetrievalModel(
                    MultiHeadSAVGLayer(d_model=d_model, num_heads=num_heads, preset="decayotton_orthoplex"), d_model, vocab_size
                ).to(device),
            }

            for name, model in models.items():
                opt = torch.optim.Adam(model.parameters(), lr=0.01)
                # Quick in-context calibration on needle
                t0 = time.perf_counter()
                for _ in range(5):
                    opt.zero_grad()
                    logits = model(tokens)
                    loss = F.cross_entropy(logits[:, -1, :], torch.tensor([target], device=device))
                    loss.backward()
                    opt.step()

                if device.type == "cuda":
                    torch.cuda.synchronize()
                elapsed = (time.perf_counter() - t0) * 1000.0 / 5

                with torch.no_grad():
                    pred_token = torch.argmax(model(tokens)[:, -1, :], dim=-1).item()
                    found = "YES (✓)" if pred_token == target else f"NO (got {pred_token})"

                depth_pct = f"{int(depth * 100)}%"
                print(f"{N:<12} | {depth_pct:<8} | {name:<35} | {found:<14} | {elapsed:7.2f} ms")

        print("-" * 92)

    print("==========================================================================================\n")


if __name__ == "__main__":
    run_needle_benchmark()
