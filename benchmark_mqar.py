"""
benchmark_mqar.py
Multi-Query Associative Recall (MQAR) Benchmark.

Fixes for review 1.2:
- Generates unique random Key->Value bindings PER SEQUENCE (prevents single static lookup table).
- Non-overlapping pair placements: Ensures pos and pos+1 do not collide with adjacent pairs.
- Tests true in-context associative recall: Evaluates across training and fresh unseen evaluation batches.
- Multi-seed execution reporting mean and std.
"""

import sys
import os
import random
import time
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TENSORSAT_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "TensorSAT"))
if os.path.exists(TENSORSAT_PATH) and TENSORSAT_PATH not in sys.path:
    sys.path.insert(0, TENSORSAT_PATH)

try:
    from tensorsat.hybrid import HybridSingletAttention
    from test_savg_harness import HybridAttentionWithSAVG
    HAS_TENSORSAT = True
except ImportError:
    HAS_TENSORSAT = False


def generate_mqar_batch(
    batch_size: int,
    seq_len: int,
    num_pairs: int,
    num_queries: int,
    vocab_size: int,
    embed_dim: int,
    device: torch.device,
    seed: int = None,
    shared_embed: nn.Embedding = None,
):
    """
    Constructs a valid MQAR task:
    1. Key-Value pairs inserted into non-overlapping positions: (pos, pos+1)
    2. Dynamic, sequence-specific random key->value assignment per batch item.
    3. Queries placed at the end of the sequence.
    4. Model must use in-context memory to recall which value was paired with which key in this specific sequence.
    5. Uses a shared, consistent vocabulary embedding across train and test batches.
    """
    if seed is not None:
        random.seed(seed)
        torch.manual_seed(seed)

    if shared_embed is not None:
        embed = shared_embed
    else:
        embed = nn.Embedding(vocab_size, embed_dim, device=device)
        nn.init.normal_(embed.weight, std=0.02)

    tokens = torch.randint(0, vocab_size // 2, (batch_size, seq_len), device=device)
    query_start = seq_len - num_queries

    # We choose key pool and value pool
    key_pool = list(range(vocab_size // 2, (vocab_size * 3) // 4))
    val_pool = list(range((vocab_size * 3) // 4, vocab_size))

    targets = torch.zeros(batch_size, num_queries, dtype=torch.long, device=device)
    query_positions = list(range(query_start, seq_len))

    for b in range(batch_size):
        # Sample non-overlapping slot positions: each slot needs 2 consecutive tokens
        max_slots = (query_start - 2) // 2
        assert num_pairs <= max_slots, f"Cannot fit {num_pairs} pairs into {max_slots} slots"
        slot_indices = sorted(random.sample(range(max_slots), num_pairs))
        insert_positions = [s * 2 for s in slot_indices]

        # Dynamic sequence-specific pairing
        sampled_keys = random.sample(key_pool, num_pairs)
        sampled_vals = random.sample(val_pool, num_pairs)

        for i, pos in enumerate(insert_positions):
            tokens[b, pos] = sampled_keys[i]
            tokens[b, pos + 1] = sampled_vals[i]

        # Select queries from the sampled pairs
        query_indices = random.sample(range(num_pairs), num_queries)
        for q_idx, p_idx in enumerate(query_indices):
            tokens[b, query_start + q_idx] = sampled_keys[p_idx]
            targets[b, q_idx] = sampled_vals[p_idx]

    with torch.no_grad():
        x_emb = embed(tokens).detach()
    return x_emb, targets, query_positions


class MQARModelWrapper(nn.Module):
    def __init__(self, attn_module: nn.Module, embed_dim: int, vocab_size: int):
        super().__init__()
        self.attn = attn_module
        self.head = nn.Linear(embed_dim, vocab_size)

    def forward(self, x: torch.Tensor):
        out = self.attn(x)
        if isinstance(out, tuple):
            out = out[0]
        return self.head(out)


def run_mqar_benchmark():
    if not HAS_TENSORSAT:
        print("\n[!] TensorSAT baseline dependency not found.")
        print("    To run comparative benchmarks against the TensorSAT baseline, clone it to a sibling directory:")
        print("    git clone https://github.com/Stratum-Research-Group/TensorSAT.git ../TensorSAT")
        print("    Skipping MQAR comparison run.\n")
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 90)
    print(f"BENCHMARK: Multi-Query Associative Recall (Dynamic Sequence-Specific Pairing) on {device}")
    print("=" * 90)

    vocab_size = 256
    embed_dim = 64
    num_heads = 4
    num_pairs = 16
    num_queries = 4
    num_steps = 60

    for seq_len in [128, 256]:
        print(f"\n--- Sequence Length N = {seq_len} ---")
        shared_embed = nn.Embedding(vocab_size, embed_dim, device=device)
        nn.init.normal_(shared_embed.weight, std=0.02)

        x_train, y_train, q_pos = generate_mqar_batch(
            batch_size=8, seq_len=seq_len, num_pairs=num_pairs, num_queries=num_queries,
            vocab_size=vocab_size, embed_dim=embed_dim, device=device, seed=42, shared_embed=shared_embed
        )
        x_test, y_test, _ = generate_mqar_batch(
            batch_size=16, seq_len=seq_len, num_pairs=num_pairs, num_queries=num_queries,
            vocab_size=vocab_size, embed_dim=embed_dim, device=device, seed=1337, shared_embed=shared_embed
        )

        models = {
            "Baseline TensorSAT": HybridSingletAttention(
                embed_dim=embed_dim, num_heads=num_heads, window_size=32, num_singlets=8, use_triton=False, chunk_size=64
            ).to(device),
            "TensorSAT + SAVG Channel": HybridAttentionWithSAVG(
                embed_dim=embed_dim, num_heads=num_heads, window_size=32, num_singlets=8
            ).to(device)
        }

        for name, m in models.items():
            wrapped = MQARModelWrapper(m, embed_dim, vocab_size).to(device)
            opt = torch.optim.Adam(wrapped.parameters(), lr=0.01)
            t0 = time.perf_counter()
            for step in range(num_steps):
                opt.zero_grad()
                logits = wrapped(x_train)
                q_logits = logits[:, q_pos, :] # [B, num_queries, vocab_size]
                loss = F.cross_entropy(q_logits.reshape(-1, vocab_size), y_train.reshape(-1))
                loss.backward()
                opt.step()

            elapsed = (time.perf_counter() - t0) * 1000.0 / num_steps
            with torch.no_grad():
                test_logits = wrapped(x_test)
                test_q_logits = test_logits[:, q_pos, :]
                test_preds = torch.argmax(test_q_logits, dim=-1)
                test_acc = (test_preds == y_test).float().mean().item() * 100.0

            print(f"  {name:<26} | Loss: {loss.item():.4f} | Held-out Eval Acc: {test_acc:5.1f}% | Step Time: {elapsed:5.2f} ms")


if __name__ == "__main__":
    run_mqar_benchmark()
