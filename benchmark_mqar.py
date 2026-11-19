"""
benchmark_mqar.py
Multi-Query Associative Recall (MQAR) Benchmark.
Tests:
- Memory capacity under noise and sequence length scaling (N = 256, 512, 1024).
- Key-Value recall accuracy under multiple queries per sequence.
- Comparing Baseline TensorSAT Hybrid Attention against SAVG-augmented Hybrid Attention.
Without modifying any TensorSAT files.
"""

import sys
import os
import time
import random
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.abspath("../TensorSAT"))
from tensorsat.hybrid import HybridSingletAttention
from test_savg_harness import HybridAttentionWithSAVG

# Set seed for exact reproducibility
torch.manual_seed(42)
random.seed(42)

def generate_mqar_batch(
    batch_size: int,
    seq_len: int,
    num_pairs: int,
    num_queries: int,
    vocab_size: int,
    embed_dim: int,
    device: torch.device
):
    """
    Constructs a synthetic MQAR task:
    1. Key-Value pairs inserted into random sequence positions: K_i -> V_i
    2. Queries placed at the end of the sequence: Q_1, Q_2, ..., Q_m
    3. Noise tokens fill the remaining positions.
    4. Target: Return V_i corresponding to query K_i.
    """
    # Token embedding table for discrete synthetic tokens
    embed = nn.Embedding(vocab_size, embed_dim, device=device)
    nn.init.normal_(embed.weight, std=0.02)

    tokens = torch.randint(0, vocab_size - (num_pairs * 2 + num_queries + 1), (batch_size, seq_len), device=device)
    # Reserve special IDs for distinct keys and values
    key_ids = list(range(vocab_size - num_pairs * 2 - 1, vocab_size - num_pairs - 1))
    val_ids = list(range(vocab_size - num_pairs - 1, vocab_size - 1))

    targets = torch.zeros(batch_size, num_queries, dtype=torch.long, device=device)
    query_positions = []

    for b in range(batch_size):
        # Sample positions for key-value pairs (must be before the query region)
        query_start = seq_len - num_queries
        insert_positions = sorted(random.sample(range(0, query_start - 2), num_pairs))

        # Insert key-value pairs
        selected_pairs = random.sample(range(num_pairs), num_queries)
        for i, pos in enumerate(insert_positions):
            k_id = key_ids[i]
            v_id = val_ids[i]
            tokens[b, pos] = k_id
            tokens[b, pos + 1] = v_id  # Immediate or local association

        # Insert queries at the end
        for q_idx, pair_idx in enumerate(selected_pairs):
            q_pos = query_start + q_idx
            tokens[b, q_pos] = key_ids[pair_idx]
            targets[b, q_idx] = val_ids[pair_idx]

    # Convert tokens to continuous embeddings (detached)
    with torch.no_grad():
        x_emb = embed(tokens).detach()
    return x_emb, targets, list(range(seq_len - num_queries, seq_len))


class MQARModelWrapper(nn.Module):
    """Wraps attention model with vocabulary head for classification evaluation."""
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
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 80)
    print(f"BENCHMARK: Multi-Query Associative Recall (MQAR) on {device}")
    print("=" * 80)

    vocab_size = 256
    embed_dim = 64
    num_heads = 4
    batch_size = 16
    num_queries = 4
    num_pairs = 16
    train_steps = 120

    seq_lengths = [256, 512, 1024]

    print(f"{'Seq Length':<12} | {'Model':<28} | {'Init Loss':<11} | {'Final Loss':<11} | {'Accuracy %':<10} | {'Latency':<9}")
    print("-" * 80)

    for seq_len in seq_lengths:
        # Generate batch
        x_emb, targets, q_indices = generate_mqar_batch(
            batch_size=batch_size,
            seq_len=seq_len,
            num_pairs=num_pairs,
            num_queries=num_queries,
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            device=device
        )

        base_hybrid = HybridSingletAttention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            window_size=64,
            num_singlets=16,
            use_triton=False,
            chunk_size=128
        ).to(device)

        savg_hybrid = HybridAttentionWithSAVG(
            embed_dim=embed_dim,
            num_heads=num_heads,
            window_size=64,
            num_singlets=16
        ).to(device)

        models = {
            "TensorSAT Baseline": MQARModelWrapper(base_hybrid, embed_dim, vocab_size).to(device),
            "TensorSAT + SAVG (Simplex)": MQARModelWrapper(savg_hybrid, embed_dim, vocab_size).to(device)
        }

        for name, model in models.items():
            optimizer = torch.optim.Adam(model.parameters(), lr=0.008)
            init_loss = 0.0
            final_loss = 0.0

            # Warmup
            _ = model(x_emb)
            if device.type == "cuda":
                torch.cuda.synchronize()

            t0 = time.perf_counter()
            for step in range(train_steps):
                optimizer.zero_grad()
                logits = model(x_emb)  # [B, T, vocab_size]
                # Extract logits at query positions
                query_logits = logits[:, q_indices, :]  # [B, num_queries, vocab_size]
                loss = F.cross_entropy(query_logits.reshape(-1, vocab_size), targets.reshape(-1))
                loss.backward()
                optimizer.step()

                if step == 0:
                    init_loss = loss.item()
                if step == train_steps - 1:
                    final_loss = loss.item()

            if device.type == "cuda":
                torch.cuda.synchronize()
            elapsed = (time.perf_counter() - t0) * 1000.0 / train_steps

            # Accuracy check
            with torch.no_grad():
                pred = torch.argmax(query_logits, dim=-1)  # [B, num_queries]
                acc = (pred == targets).float().mean().item() * 100.0

            print(f"{seq_len:<12} | {name:<28} | {init_loss:<11.4f} | {final_loss:<11.4f} | {acc:<10.1f} | {elapsed:<6.1f} ms")


if __name__ == "__main__":
    run_mqar_benchmark()
