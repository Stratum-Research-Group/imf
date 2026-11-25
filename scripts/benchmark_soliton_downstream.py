import os
import sys
import json
import time
import subprocess
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf.omni_block import IMFOmniBlock

def get_text_tokens(device, vocab_size=256):
    with open("data/real_text_sample.txt", "r", encoding="utf-8") as f:
        text = f.read()
    raw_bytes = list(text.encode("utf-8"))
    tokens = torch.tensor([b % vocab_size for b in raw_bytes], dtype=torch.long, device=device)
    split_idx = int(len(tokens) * 0.8)
    return tokens[:split_idx], tokens[split_idx:]

def make_batches(tokens, batch_size=8, seq_len=128):
    n_batches = (len(tokens) - 1) // (batch_size * seq_len)
    total_tokens = n_batches * batch_size * seq_len
    x_flat = tokens[:total_tokens]
    y_flat = tokens[1:total_tokens + 1]
    return x_flat.view(n_batches, batch_size, seq_len), y_flat.view(n_batches, batch_size, seq_len)

def evaluate_seed(seed, use_soliton, train_x, train_y, held_x, held_y, device):
    torch.manual_seed(seed)
    vocab_size = 256
    dim = 64
    block = IMFOmniBlock(d_model=dim, num_heads=4)
    if not use_soliton:
        block.branch_soliton_act = nn.Identity()
        block.soliton_activation = nn.Identity()
        
    model = nn.Sequential(
        nn.Embedding(vocab_size, dim),
        block,
        nn.LayerNorm(dim),
        nn.Linear(dim, vocab_size)
    ).to(device)
    
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3)
    model.train()
    steps = min(80, len(train_x))
    for s in range(steps):
        logits = model(train_x[s])
        loss = F.cross_entropy(logits.view(-1, vocab_size), train_y[s].view(-1))
        opt.zero_grad()
        loss.backward()
        opt.step()
        
    model.eval()
    total_loss = 0.0
    with torch.no_grad():
        for b in range(len(held_x)):
            logits = model(held_x[b])
            l = F.cross_entropy(logits.view(-1, vocab_size), held_y[b].view(-1))
            total_loss += l.item()
    return total_loss / max(len(held_x), 1)

def main():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    git_rev = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    train_tok, held_tok = get_text_tokens(device=device)
    train_x, train_y = make_batches(train_tok, batch_size=16, seq_len=128)
    held_x, held_y = make_batches(held_tok, batch_size=16, seq_len=128)
    
    seeds = [42, 1337, 2026]
    losses_with = []
    losses_without = []
    
    t0 = time.time()
    for s in seeds:
        lw = evaluate_seed(s, True, train_x, train_y, held_x, held_y, device)
        lwo = evaluate_seed(s, False, train_x, train_y, held_x, held_y, device)
        losses_with.append(lw)
        losses_without.append(lwo)
        print(f"Seed {s}: With Soliton={lw:.4f} | Without={lwo:.4f} (Delta={((lwo-lw)/lwo)*100:+.2f}%)")
        
    dur = time.time() - t0
    mean_w = sum(losses_with) / len(losses_with)
    mean_wo = sum(losses_without) / len(losses_without)
    
    delta = (mean_wo - mean_w) / mean_wo * 100.0
    verdict = f"Soliton activation yields {delta:+.2f}% loss delta across 3 seeds"
    
    results = {
        "git_commit": git_rev,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "task": "Next-Token Real Text Language Modeling (3 Seeds)",
        "seeds": seeds,
        "model_with_soliton": {
            "losses": losses_with,
            "mean_loss": float(mean_w)
        },
        "model_without_soliton": {
            "losses": losses_without,
            "mean_loss": float(mean_wo)
        },
        "soliton_relative_improvement_pct": float(delta),
        "verdict": verdict
    }
    
    out_path = "benchmark_results/soliton_downstream_metric.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Summary: Mean With={mean_w:.4f} vs Without={mean_wo:.4f} -> Delta={delta:+.2f}% ({dur:.1f}s)")
    print(f"Saved to {out_path}")

if __name__ == '__main__':
    main()
