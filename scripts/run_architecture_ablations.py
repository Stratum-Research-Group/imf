import os
import sys
import json
import time
import math
import subprocess
import torch
import torch.nn as nn
import torch.nn.functional as F

SEEDS = [42, 1337, 2026]

def generate_prefix_copy(batch_size, K=8, vocab_size=64, device='cuda'):
    prefix = torch.randint(2, vocab_size, (batch_size, K), device=device)
    delim = torch.ones(batch_size, 1, dtype=torch.long, device=device)
    inputs = torch.cat([prefix, delim, prefix[:, :-1]], dim=1) # Length 2*K
    targets = torch.cat([prefix[:, 1:], delim, prefix], dim=1)
    return inputs, targets

class PlainLinearAttention(nn.Module):
    def __init__(self, d_model):
        super().__init__()
        self.q = nn.Linear(d_model, d_model)
        self.k = nn.Linear(d_model, d_model)
        self.v = nn.Linear(d_model, d_model)
        self.out = nn.Linear(d_model, d_model)
    def forward(self, x):
        q = F.elu(self.q(x)) + 1.0
        k = F.elu(self.k(x)) + 1.0
        v = self.v(x)
        kv = torch.einsum('bsd,bse->bsde', k, v)
        kv_cum = torch.cumsum(kv, dim=1)
        z = torch.cumsum(k, dim=1)
        num = torch.einsum('bsd,bsde->bse', q, kv_cum)
        den = torch.einsum('bsd,bsd->bs', q, z).unsqueeze(-1) + 1e-6
        return self.out(num / den)

class Sym2OnlyAttention(nn.Module):
    def __init__(self, d_model):
        super().__init__()
        self.proj = nn.Linear(d_model, d_model)
        self.out = nn.Linear(d_model, d_model)
    def forward(self, x):
        h = self.proj(x)
        diag = h * h
        return self.out(diag * torch.sigmoid(h))

class Wedge2OnlyAttention(nn.Module):
    def __init__(self, d_model):
        super().__init__()
        self.proj_a = nn.Linear(d_model, d_model)
        self.proj_b = nn.Linear(d_model, d_model)
        self.out = nn.Linear(d_model, d_model)
    def forward(self, x):
        a = self.proj_a(x)
        b = self.proj_b(x)
        wedge_rep = a * torch.roll(b, 1, dims=-1) - b * torch.roll(a, 1, dims=-1)
        return self.out(F.silu(wedge_rep))

class StandardTransformerBlock(nn.Module):
    def __init__(self, d_model, nhead=4):
        super().__init__()
        self.mha = nn.MultiheadAttention(d_model, num_heads=nhead, batch_first=True)
        self.ffn = nn.Sequential(
            nn.Linear(d_model, d_model * 2),
            nn.GELU(),
            nn.Linear(d_model * 2, d_model)
        )
        self.ln1 = nn.LayerNorm(d_model)
        self.ln2 = nn.LayerNorm(d_model)
    def forward(self, x):
        S = x.shape[1]
        causal_mask = nn.Transformer.generate_square_subsequent_mask(S, device=x.device)
        attn_out, _ = self.mha(x, x, x, attn_mask=causal_mask, is_causal=True)
        x = self.ln1(x + attn_out)
        x = self.ln2(x + self.ffn(x))
        return x

def build_wrapper(core_block, vocab_size=64, d_model=64):
    class ModelWrapper(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = nn.Embedding(vocab_size, d_model)
            self.pos = nn.Parameter(torch.randn(1, 32, d_model) * 0.02)
            self.core = core_block
            self.head = nn.Linear(d_model, vocab_size)
        def forward(self, x):
            S = x.shape[1]
            h = self.embed(x) + self.pos[:, :S]
            out = self.core(h)
            return self.head(out)
    return ModelWrapper()

def train_and_eval(name, model_fn, seed=42, steps=250, device='cuda'):
    torch.manual_seed(seed)
    model = model_fn().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3)
    
    model.train()
    for s in range(steps):
        x, y = generate_prefix_copy(batch_size=64, K=8, vocab_size=64, device=device)
        logits = model(x)
        loss = F.cross_entropy(logits.reshape(-1, 64), y.reshape(-1))
        opt.zero_grad()
        loss.backward()
        opt.step()
        
    model.eval()
    total_acc = 0.0
    total_loss = 0.0
    with torch.no_grad():
        for _ in range(25):
            x, y = generate_prefix_copy(batch_size=64, K=8, vocab_size=64, device=device)
            logits = model(x)
            total_loss += F.cross_entropy(logits.reshape(-1, 64), y.reshape(-1)).item()
            preds = logits.argmax(dim=-1)
            # Evaluate accuracy specifically on the second half (the copied portion)
            total_acc += (preds[:, 8:] == y[:, 8:]).float().mean().item()
            
    avg_loss = total_loss / 25.0
    avg_acc = total_acc / 25.0
    param_count = sum(p.numel() for p in model.parameters())
    return {
        "model": name,
        "seed": seed,
        "params": param_count,
        "eval_ce_loss": float(avg_loss),
        "eval_copy_recall_accuracy": float(avg_acc)
    }

def main():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    git_rev = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    
    from imf.omni_block import IMFOmniBlock
    architectures = [
        ("standard_transformer", lambda: build_wrapper(StandardTransformerBlock(64))),
        ("plain_linear_attention", lambda: build_wrapper(PlainLinearAttention(64))),
        ("sym2_only", lambda: build_wrapper(Sym2OnlyAttention(64))),
        ("wedge2_only", lambda: build_wrapper(Wedge2OnlyAttention(64))),
        ("full_imf_omniblock", lambda: build_wrapper(IMFOmniBlock(d_model=64, num_heads=4))),
    ]
    
    results = {
        "git_commit": git_rev,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "task": "Discrete In-Context Sequence Copy & Recall Benchmark",
        "seeds": SEEDS,
        "evaluations": []
    }
    
    summary = {}
    for name, factory in architectures:
        summary[name] = {"losses": [], "accuracies": [], "params": 0}
        for seed in SEEDS:
            t0 = time.time()
            res = train_and_eval(name, factory, seed=seed, steps=250, device=device)
            dur = time.time() - t0
            print(f"[{name} | seed={seed}] Loss: {res['eval_ce_loss']:.4f}, Acc: {res['eval_copy_recall_accuracy']*100:.1f}% ({dur:.2f}s)")
            results["evaluations"].append(res)
            summary[name]["losses"].append(res["eval_ce_loss"])
            summary[name]["accuracies"].append(res["eval_copy_recall_accuracy"])
            summary[name]["params"] = res["params"]
            
    aggregated = {}
    for name, data in summary.items():
        losses = data["losses"]
        accs = data["accuracies"]
        mean_l = sum(losses) / len(losses)
        std_l = math.sqrt(sum((x - mean_l)**2 for x in losses) / len(losses))
        mean_a = sum(accs) / len(accs)
        std_a = math.sqrt(sum((x - mean_a)**2 for x in accs) / len(accs))
        aggregated[name] = {
            "params": data["params"],
            "mean_loss": float(mean_l),
            "std_loss": float(std_l),
            "mean_accuracy": float(mean_a),
            "std_accuracy": float(std_a)
        }
        print(f"Summary {name}: Loss={mean_l:.4f}±{std_l:.4f}, Acc={mean_a*100:.1f}±{std_a*100:.1f}%")
        
    results["aggregated_summary"] = aggregated
    out_path = "benchmark_results/architecture_ablations.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved ablations to {out_path}")

if __name__ == "__main__":
    main()
