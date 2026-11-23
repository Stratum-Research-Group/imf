"""
benchmark_long_context_mqar.py
Long-Context Multi-Query Associative Recall (MQAR) Benchmark (N = 512, 1024, 2048, 4096).
Evaluates whether IMF Multi-Head SAVG with 10D Polytope memory anchors maintains
associative recall across long contexts without state saturation or noise bleed,
compared to standard Linear Attention / Recurrent baselines.
"""

import time
import math
import random
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf import MultiHeadSAVGLayer


class StandardLinearAttention(nn.Module):
    """Standard unconstrained outer-product linear attention baseline."""
    def __init__(self, d_model: int, num_heads: int = 4):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_h = d_model // num_heads
        self.W_q = nn.Linear(d_model, d_model, bias=False)
        self.W_k = nn.Linear(d_model, d_model, bias=False)
        self.W_v = nn.Linear(d_model, d_model, bias=False)
        self.out_proj = nn.Linear(d_model, d_model, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, D = x.shape
        q = F.elu(self.W_q(x)) + 1.0
        k = F.elu(self.W_k(x)) + 1.0
        v = self.W_v(x)

        q = q.view(B, T, self.num_heads, self.d_h).transpose(1, 2)
        k = k.view(B, T, self.num_heads, self.d_h).transpose(1, 2)
        v = v.view(B, T, self.num_heads, self.d_h).transpose(1, 2)

        # Causal linear attention recurrence
        out = torch.empty_like(v)
        S = torch.zeros(B, self.num_heads, self.d_h, self.d_h, device=x.device, dtype=x.dtype)
        z = torch.zeros(B, self.num_heads, self.d_h, 1, device=x.device, dtype=x.dtype)

        for t in range(T):
            k_t = k[:, :, t, :].unsqueeze(-1) # [B, H, d_h, 1]
            v_t = v[:, :, t, :].unsqueeze(-2) # [B, H, 1, d_h]
            q_t = q[:, :, t, :].unsqueeze(-2) # [B, H, 1, d_h]

            S = S + torch.matmul(k_t, v_t)
            z = z + k_t

            num = torch.matmul(q_t, S) # [B, H, 1, d_h]
            den = torch.matmul(q_t, z).clamp(min=1e-5)
            out[:, :, t, :] = (num / den).squeeze(-2)

        out = out.transpose(1, 2).contiguous().view(B, T, D)
        return self.out_proj(out)


def generate_long_mqar_batch(
    batch_size: int,
    seq_len: int,
    num_pairs: int,
    num_queries: int,
    vocab_size: int,
    device: torch.device,
    seed: int = None,
):
    """Generates synthetic long-context token IDs with key-value pairs separated by noise distractor tokens."""
    if seed is not None:
        random.seed(seed)
        torch.manual_seed(seed)

    tokens = torch.randint(0, vocab_size // 3, (batch_size, seq_len), device=device)
    query_start = seq_len - num_queries

    key_pool = list(range(vocab_size // 3, (vocab_size * 2) // 3))
    val_pool = list(range((vocab_size * 2) // 3, vocab_size))

    targets = torch.zeros(batch_size, num_queries, dtype=torch.long, device=device)
    query_positions = list(range(query_start, seq_len))

    for b in range(batch_size):
        # Distribute pairs randomly across context before query positions
        max_slots = (query_start - 4) // 2
        slot_indices = sorted(random.sample(range(max_slots), num_pairs))
        insert_positions = [s * 2 for s in slot_indices]

        sampled_keys = random.sample(key_pool, num_pairs)
        sampled_vals = [random.choice(val_pool) for _ in range(num_pairs)]

        for pos, k, v in zip(insert_positions, sampled_keys, sampled_vals):
            tokens[b, pos] = k
            tokens[b, pos + 1] = v

        query_indices = random.sample(range(num_pairs), num_queries)
        for q_idx, p_idx in enumerate(query_indices):
            tokens[b, query_start + q_idx] = sampled_keys[p_idx]
            targets[b, q_idx] = sampled_vals[p_idx]

    return tokens, targets, query_positions


class LongMQARModel(nn.Module):
    def __init__(self, core_module: nn.Module, d_model: int, vocab_size: int):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, d_model)
        nn.init.normal_(self.embed.weight, std=0.02)
        self.core = core_module
        self.head = nn.Linear(d_model, vocab_size)

    def forward(self, token_ids: torch.Tensor):
        x = self.embed(token_ids)
        h = self.core(x)
        return self.head(h)


def run_long_context_benchmark():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 95)
    print(f"LONG-CONTEXT MQAR BENCHMARK (N = 512, 1024, 2048, 4096) on {device}")
    print("=" * 95)

    vocab_size = 256
    d_model = 64
    num_heads = 4
    num_pairs = 32
    num_queries = 8
    num_steps = 75

    contexts = [512, 1024, 2048, 4096]
    results = []

    for seq_len in contexts:
        print(f"\n--- Context Length N = {seq_len} tokens ---")
        x_train, y_train, q_pos = generate_long_mqar_batch(
            batch_size=8, seq_len=seq_len, num_pairs=num_pairs, num_queries=num_queries,
            vocab_size=vocab_size, device=device, seed=42
        )
        x_eval, y_eval, _ = generate_long_mqar_batch(
            batch_size=16, seq_len=seq_len, num_pairs=num_pairs, num_queries=num_queries,
            vocab_size=vocab_size, device=device, seed=1337
        )

        models = {
            "Standard Linear Attention": StandardLinearAttention(d_model=d_model, num_heads=num_heads).to(device),
            "IMF Multi-Head SAVG (Polytope 10D)": MultiHeadSAVGLayer(d_model=d_model, num_heads=num_heads, preset="decayotton_orthoplex").to(device),
        }

        for name, core in models.items():
            model = LongMQARModel(core, d_model, vocab_size).to(device)
            opt = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=1e-4)

            model.train()
            t0 = time.perf_counter()
            for step in range(1, num_steps + 1):
                opt.zero_grad()
                logits = model(x_train)
                q_logits = logits[:, q_pos, :]
                loss = F.cross_entropy(q_logits.reshape(-1, vocab_size), y_train.reshape(-1))
                loss.backward()
                opt.step()

            step_time = (time.perf_counter() - t0) * 1000.0 / num_steps

            model.eval()
            with torch.no_grad():
                eval_logits = model(x_eval)[:, q_pos, :]
                eval_preds = torch.argmax(eval_logits, dim=-1)
                eval_acc = (eval_preds == y_eval).float().mean().item() * 100.0

            print(f"  {name:<36} | Loss: {loss.item():.4f} | Held-out Acc: {eval_acc:5.1f}% | Latency: {step_time:6.2f} ms")
            results.append({
                "context": seq_len,
                "model": name,
                "train_loss": loss.item(),
                "eval_acc": eval_acc,
                "step_time": step_time,
            })

    print("\n" + "=" * 95)
    print("LONG-CONTEXT ASSOCIATIVE RECALL SUMMARY")
    print("=" * 95)
    print(f"{'Context Length (N)':20s} | {'Model Architecture':36s} | {'Train Loss':12s} | {'Eval Acc %':10s} | {'Step Time':10s}")
    print("-" * 95)
    for r in results:
        print(f"{r['context']:<20d} | {r['model']:36s} | {r['train_loss']:12.4f} | {r['eval_acc']:9.1f}% | {r['step_time']:7.2f} ms")
    print("=" * 95)


if __name__ == "__main__":
    run_long_context_benchmark()
