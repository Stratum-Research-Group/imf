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

def generate_mqar_batch(batch_size=64, seq_len=20, num_pairs=4, num_queries=2, vocab_size=64, device='cuda'):
    """
    True Multi-Query Associative Recall (MQAR) task:
    - Sequence embeds multiple random key-value bindings: (k0, v0), (k1, v1), ...
    - Keys are drawn uniquely without replacement from key token set (2..29).
    - Values are drawn from value token set (32..61).
    - Query marker delimiter token (1) separates memory storage phase from query phase.
    - Multiple query keys are presented at random query positions.
    - Target tokens are only active (-100 ignored elsewhere) at the query positions,
      requiring true content-addressed associative memory retrieval.
    """
    keys = torch.zeros(batch_size, num_pairs, dtype=torch.long, device=device)
    vals = torch.zeros(batch_size, num_pairs, dtype=torch.long, device=device)
    for b in range(batch_size):
        keys[b] = torch.randperm(28, device=device)[:num_pairs] + 2
        vals[b] = torch.randint(32, 62, (num_pairs,), device=device)
        
    x = torch.zeros(batch_size, seq_len, dtype=torch.long, device=device)
    for i in range(num_pairs):
        x[:, 2 * i] = keys[:, i]
        x[:, 2 * i + 1] = vals[:, i]
        
    delim_pos = 2 * num_pairs
    x[:, delim_pos] = 1
    
    targets = torch.full((batch_size, seq_len), -100, dtype=torch.long, device=device)
    for q in range(num_queries):
        pos = delim_pos + 1 + q
        q_pair = torch.randint(0, num_pairs, (batch_size,), device=device)
        x[:, pos] = keys[torch.arange(batch_size), q_pair]
        targets[:, pos] = vals[torch.arange(batch_size), q_pair]
        
    return x, targets


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


class Sym2TensorAttention(nn.Module):
    """
    Symmetric 2-tensor outer binding branch:
    S_t = 1/2 * (v_t k_t^T + k_t v_t^T)
    Accumulates symmetric bilinear associations causally over the sequence.
    """
    def __init__(self, d_model):
        super().__init__()
        self.k = nn.Linear(d_model, d_model, bias=False)
        self.v = nn.Linear(d_model, d_model, bias=False)
        self.q = nn.Linear(d_model, d_model, bias=False)
        self.out = nn.Linear(d_model, d_model, bias=False)
    def forward(self, x):
        k = self.k(x)
        v = self.v(x)
        q = self.q(x)
        kv = 0.5 * (torch.einsum('bsd,bse->bsde', v, k) + torch.einsum('bsd,bse->bsde', k, v))
        S_cum = torch.cumsum(kv, dim=1)
        y = torch.einsum('bsde,bse->bsd', S_cum, q)
        return self.out(y)


class Wedge2TensorAttention(nn.Module):
    """
    Skew-symmetric 2-form outer binding branch (Wedge product):
    W_t = 1/2 * (v_t k_t^T - k_t v_t^T) in so(d)
    Accumulates oriented 2-surface exterior bindings causally.
    """
    def __init__(self, d_model):
        super().__init__()
        self.k = nn.Linear(d_model, d_model, bias=False)
        self.v = nn.Linear(d_model, d_model, bias=False)
        self.q = nn.Linear(d_model, d_model, bias=False)
        self.out = nn.Linear(d_model, d_model, bias=False)
    def forward(self, x):
        k = self.k(x)
        v = self.v(x)
        q = self.q(x)
        wv = 0.5 * (torch.einsum('bsd,bse->bsde', v, k) - torch.einsum('bsd,bse->bsde', k, v))
        W_cum = torch.cumsum(wv, dim=1)
        y = torch.einsum('bsde,bse->bsd', W_cum, q)
        return self.out(y)


class StandardTransformerBlock(nn.Module):
    def __init__(self, d_model, nhead=4, d_ffn=212):
        super().__init__()
        layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, dim_feedforward=d_ffn, batch_first=True)
        self.enc = nn.TransformerEncoder(layer, num_layers=2)
    def forward(self, x):
        S = x.shape[1]
        causal_mask = nn.Transformer.generate_square_subsequent_mask(S, device=x.device)
        return self.enc(x, mask=causal_mask, is_causal=True)


class Generic2LayerBlock(nn.Module):
    def __init__(self, AttnCls, d_model=64, d_ffn=212):
        super().__init__()
        self.a1 = AttnCls(d_model)
        self.ffn1 = nn.Sequential(nn.Linear(d_model, d_ffn), nn.GELU(), nn.Linear(d_ffn, d_model))
        self.ln1 = nn.LayerNorm(d_model)
        self.ln2 = nn.LayerNorm(d_model)
        self.a2 = AttnCls(d_model)
        self.ffn2 = nn.Sequential(nn.Linear(d_model, d_ffn), nn.GELU(), nn.Linear(f_ffn := d_ffn, d_model))
        self.ln3 = nn.LayerNorm(d_model)
        self.ln4 = nn.LayerNorm(d_model)
    def forward(self, x):
        x = self.ln1(x + self.a1(x))
        x = self.ln2(x + self.ffn1(x))
        x = self.ln3(x + self.a2(x))
        x = self.ln4(x + self.ffn2(x))
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
        x, y = generate_mqar_batch(batch_size=64, seq_len=20, num_pairs=4, num_queries=2, vocab_size=64, device=device)
        logits = model(x)
        loss = F.cross_entropy(logits.view(-1, 64), y.view(-1), ignore_index=-100)
        opt.zero_grad()
        loss.backward()
        opt.step()
        
    model.eval()
    total_acc = 0.0
    total_loss = 0.0
    eval_iters = 25
    with torch.no_grad():
        for _ in range(eval_iters):
            x, y = generate_mqar_batch(batch_size=64, seq_len=20, num_pairs=4, num_queries=2, vocab_size=64, device=device)
            logits = model(x)
            total_loss += F.cross_entropy(logits.view(-1, 64), y.view(-1), ignore_index=-100).item()
            mask = (y != -100)
            preds = logits.argmax(dim=-1)
            total_acc += (preds[mask] == y[mask]).float().mean().item()
            
    avg_loss = total_loss / eval_iters
    avg_acc = total_acc / eval_iters
    param_count = sum(p.numel() for p in model.parameters())
    return {
        "model": name,
        "seed": seed,
        "params": param_count,
        "eval_ce_loss": float(avg_loss),
        "eval_mqar_accuracy": float(avg_acc)
    }


def main():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    git_rev = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    
    from imf.omni_block import IMFOmniBlock
    
    # All baseline models parameter-matched to IMFOmniBlock (98,920 parameters ±0.5%)
    architectures = [
        ("standard_transformer", lambda: build_wrapper(StandardTransformerBlock(64, nhead=4, d_ffn=212))),
        ("plain_linear_attention", lambda: build_wrapper(Generic2LayerBlock(PlainLinearAttention, 64, d_ffn=212))),
        ("sym2_tensor_attention", lambda: build_wrapper(Generic2LayerBlock(Sym2TensorAttention, 64, d_ffn=214))),
        ("wedge2_tensor_attention", lambda: build_wrapper(Generic2LayerBlock(Wedge2TensorAttention, 64, d_ffn=214))),
        ("full_imf_omniblock", lambda: build_wrapper(IMFOmniBlock(d_model=64, num_heads=4))),
    ]
    
    results = {
        "git_commit": git_rev,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "task": "Content-Addressed Multi-Query Associative Recall (MQAR) Benchmark",
        "description": "Models parameter-matched within ±0.5% (approx 98.9k params) evaluated across 3 random seeds",
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
            print(f"[{name} | seed={seed}] Loss: {res['eval_ce_loss']:.4f}, Acc: {res['eval_mqar_accuracy']*100:.1f}%, Params: {res['params']} ({dur:.2f}s)")
            results["evaluations"].append(res)
            summary[name]["losses"].append(res["eval_ce_loss"])
            summary[name]["accuracies"].append(res["eval_mqar_accuracy"])
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
        print(f"Summary {name} ({data['params']} params): Loss={mean_l:.4f}±{std_l:.4f}, Acc={mean_a*100:.1f}±{std_a*100:.1f}%")
        
    results["aggregated_summary"] = aggregated
    out_path = "benchmark_results/architecture_ablations.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved parameter-matched MQAR ablations to {out_path}")

if __name__ == "__main__":
    main()
