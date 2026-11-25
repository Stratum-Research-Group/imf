import os
import sys
import json
import time
import subprocess
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf.omni_block import IMFOmniBlock

def evaluate_soliton_downstream(device='cuda', steps=300, batch_size=8, seq_len=256, dim=64):
    torch.manual_seed(42)
    git_rev = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    
    # Model WITH Poincare Soliton Activation (default)
    block_with = IMFOmniBlock(d_model=dim, num_heads=4)
    model_with_soliton = nn.Sequential(
        nn.Linear(dim, dim),
        block_with,
        nn.LayerNorm(dim),
        nn.Linear(dim, dim)
    ).to(device)
    
    # Model WITHOUT Poincare Soliton Activation (bypassed with identity)
    torch.manual_seed(42)
    block_no = IMFOmniBlock(d_model=dim, num_heads=4)
    block_no.branch_soliton_act = nn.Identity()
    block_no.soliton_activation = nn.Identity()
    
    model_no_soliton = nn.Sequential(
        nn.Linear(dim, dim),
        block_no,
        nn.LayerNorm(dim),
        nn.Linear(dim, dim)
    ).to(device)
    
    # Synthetic language modeling next-token prediction task
    vocab_size = 512
    embed = nn.Embedding(vocab_size, dim).to(device)
    head_with = nn.Linear(dim, vocab_size).to(device)
    head_no = nn.Linear(dim, vocab_size).to(device)
    
    opt_with = torch.optim.AdamW(list(model_with_soliton.parameters()) + list(head_with.parameters()), lr=1e-3)
    opt_no = torch.optim.AdamW(list(model_no_soliton.parameters()) + list(head_no.parameters()), lr=1e-3)
    
    # Fixed synthetic token corpus stream
    torch.manual_seed(100)
    data = torch.randint(0, vocab_size, (steps + 50, batch_size, seq_len), device=device)
    
    loss_history_with = []
    loss_history_no = []
    
    t0 = time.time()
    for s in range(steps):
        tokens = data[s]
        inputs = tokens[:, :-1]
        targets = tokens[:, 1:]
        
        # Train WITH soliton
        h_with = model_with_soliton(embed(inputs))
        logits_with = head_with(h_with)
        loss_w = F.cross_entropy(logits_with.reshape(-1, vocab_size), targets.reshape(-1))
        opt_with.zero_grad()
        loss_w.backward()
        opt_with.step()
        loss_history_with.append(loss_w.item())
        
        # Train WITHOUT soliton
        h_no = model_no_soliton(embed(inputs))
        logits_no = head_no(h_no)
        loss_n = F.cross_entropy(logits_no.reshape(-1, vocab_size), targets.reshape(-1))
        opt_no.zero_grad()
        loss_n.backward()
        opt_no.step()
        loss_history_no.append(loss_n.item())
        
    dur = time.time() - t0
    
    # Evaluation on held-out 50 steps
    eval_loss_with = 0.0
    eval_loss_no = 0.0
    model_with_soliton.eval()
    model_no_soliton.eval()
    with torch.no_grad():
        for s in range(steps, steps + 50):
            tokens = data[s]
            inputs = tokens[:, :-1]
            targets = tokens[:, 1:]
            
            h_with = model_with_soliton(embed(inputs))
            l_w = F.cross_entropy(head_with(h_with).reshape(-1, vocab_size), targets.reshape(-1))
            eval_loss_with += l_w.item()
            
            h_no = model_no_soliton(embed(inputs))
            l_n = F.cross_entropy(head_no(h_no).reshape(-1, vocab_size), targets.reshape(-1))
            eval_loss_no += l_n.item()
            
    eval_loss_with /= 50.0
    eval_loss_no /= 50.0
    
    delta = (eval_loss_no - eval_loss_with) / eval_loss_no * 100.0
    
    results = {
        "git_commit": git_rev,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "task": "Next-Token Synthetic Autoregressive Prediction",
        "steps": steps,
        "eval_steps": 50,
        "batch_size": batch_size,
        "seq_len": seq_len,
        "dim": dim,
        "wall_clock_seconds": dur,
        "model_with_soliton": {
            "initial_loss": loss_history_with[0],
            "final_train_loss": loss_history_with[-1],
            "held_out_eval_loss": eval_loss_with
        },
        "model_without_soliton": {
            "initial_loss": loss_history_no[0],
            "final_train_loss": loss_history_no[-1],
            "held_out_eval_loss": eval_loss_no
        },
        "soliton_relative_improvement_pct": delta,
        "verdict": "Soliton nonlinear activation achieves lower held-out perplexity/loss" if delta > 0 else "No significant downstream advantage"
    }
    
    os.makedirs("benchmark_results", exist_ok=True)
    out_path = "benchmark_results/soliton_downstream_metric.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"Downstream Soliton Evaluation Complete ({dur:.2f}s):")
    print(f"  With Soliton:    Held-Out Loss = {eval_loss_with:.4f}")
    print(f"  Without Soliton: Held-Out Loss = {eval_loss_no:.4f}")
    print(f"  Relative Delta:  {delta:+.2f}%")
    print(f"Saved results to {out_path}")

if __name__ == "__main__":
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    evaluate_soliton_downstream(device=device)
