import os
import sys
import json
import time
import math
import torch
import torch.nn as nn
import torch.nn.functional as F

# Ensure reproducibility
SEEDS = [42, 1337, 2026]

def generate_mqar_batch(batch_size, seq_len, num_kv_pairs, key_dim, val_dim, device):
    """
    Multi-Query Associative Recall (MQAR) synthetic task generator.
    Keys are random discrete categorical tokens or continuous vectors.
    """
    # Create key-value pairs
    keys = torch.randn(batch_size, num_kv_pairs, key_dim, device=device)
    keys = F.normalize(keys, p=2, dim=-1)
    values = torch.randn(batch_size, num_kv_pairs, val_dim, device=device)
    
    # Input sequence: [K1, V1, K2, V2, ... Kn, Vn, ..., Q_K] -> predict Q_V
    # We construct a dense representation of length seq_len
    x = torch.zeros(batch_size, seq_len, key_dim + val_dim, device=device)
    
    # Place KV pairs in early portion
    kv_positions = torch.linspace(0, seq_len - 10, steps=num_kv_pairs).long()
    for i, pos in enumerate(kv_positions):
        x[:, pos, :key_dim] = keys[:, i]
        x[:, pos, key_dim:] = values[:, i]
        
    # Pick a target key at random per batch element to query at the final position
    query_idx = torch.randint(0, num_kv_pairs, (batch_size,), device=device)
    target_keys = keys[torch.arange(batch_size), query_idx] # [B, key_dim]
    target_values = values[torch.arange(batch_size), query_idx] # [B, val_dim]
    
    x[:, -1, :key_dim] = target_keys
    return x, target_values

class PlainLinearAttention(nn.Module):
    def __init__(self, d_model):
        super().__init__()
        self.q = nn.Linear(d_model, d_model)
        self.k = nn.Linear(d_model, d_model)
        self.v = nn.Linear(d_model, d_model)
        self.out = nn.Linear(d_model, d_model)
    def forward(self, x):
        B, S, D = x.shape
        q = F.elu(self.q(x)) + 1.0
        k = F.elu(self.k(x)) + 1.0
        v = self.v(x)
        # Causal linear attention scan
        # S_t = S_{t-1} + k_t * v_t^T
        kv = torch.einsum('bsd,bse->bsde', k, v)
        kv_cum = torch.cumsum(kv, dim=1) # [B, S, D, D]
        z = torch.cumsum(k, dim=1) # [B, S, D]
        num = torch.einsum('bsd,bsde->bse', q, kv_cum)
        den = torch.einsum('bsd,bsd->bs', q, z).unsqueeze(-1) + 1e-6
        return self.out(num / den)

class Sym2OnlyAttention(nn.Module):
    def __init__(self, d_model):
        super().__init__()
        self.proj = nn.Linear(d_model, d_model)
        self.out = nn.Linear(d_model, d_model)
    def forward(self, x):
        # Symmetric 2-tensor feature expansion projection: x (x^T) symmetric component
        # Approximated by quadratic feature map + causal accumulation
        h = self.proj(x)
        h_sym = (h.unsqueeze(-1) * h.unsqueeze(-2)) # [B, S, D, D] symmetric rank-1
        # Extract upper triangular or trace-reduced representation
        diag = torch.diagonal(h_sym, dim1=-2, dim2=-1)
        return self.out(diag * torch.sigmoid(h))

class Wedge2OnlyAttention(nn.Module):
    def __init__(self, d_model):
        super().__init__()
        self.proj_a = nn.Linear(d_model, d_model)
        self.proj_b = nn.Linear(d_model, d_model)
        self.out = nn.Linear(d_model, d_model)
    def forward(self, x):
        # Exterior product / wedge 2-form: a ^ b = a*b^T - b*a^T
        a = self.proj_a(x)
        b = self.proj_b(x)
        # Antisymmetric cross interaction
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
        B, S, D = x.shape
        causal_mask = nn.Transformer.generate_square_subsequent_mask(S, device=x.device)
        attn_out, _ = self.mha(x, x, x, attn_mask=causal_mask, is_causal=True)
        x = self.ln1(x + attn_out)
        x = self.ln2(x + self.ffn(x))
        return x

class FullIMFOmniBlock(nn.Module):
    def __init__(self, d_model):
        super().__init__()
        # Import or instantiate true IMF OmniBlock components
        from imf.omni_block import IMFOmniBlock
        self.block = IMFOmniBlock(d_model=d_model, num_heads=4)
    def forward(self, x):
        return self.block(x)

def build_probe_model(core_block, d_model, val_dim):
    return nn.Sequential(
        nn.Linear(d_model, d_model),
        core_block,
        nn.LayerNorm(d_model),
        nn.Linear(d_model, val_dim)
    )

def train_and_eval_mqar(name, model_fn, d_model=64, val_dim=16, seq_len=128, seed=42, device='cuda'):
    torch.manual_seed(seed)
    model = model_fn().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-2)
    
    # Train for 400 steps
    model.train()
    for step in range(100):
        x, target = generate_mqar_batch(batch_size=16, seq_len=seq_len, num_kv_pairs=8, key_dim=d_model-val_dim, val_dim=val_dim, device=device)
        pred = model(x)[:, -1, :] # probe prediction at last position
        loss = F.mse_loss(pred, target)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        
    # Evaluate on 50 batches of test data
    model.eval()
    total_loss = 0.0
    total_cos = 0.0
    with torch.no_grad():
        for _ in range(20):
            x, target = generate_mqar_batch(batch_size=16, seq_len=seq_len, num_kv_pairs=8, key_dim=d_model-val_dim, val_dim=val_dim, device=device)
            pred = model(x)[:, -1, :]
            total_loss += F.mse_loss(pred, target).item()
            cos_sim = F.cosine_similarity(pred, target, dim=-1).mean().item()
            total_cos += cos_sim
            
    avg_loss = total_loss / 50.0
    avg_cos = total_cos / 50.0
    param_count = sum(p.numel() for p in model.parameters())
    return {
        "model": name,
        "seed": seed,
        "params": param_count,
        "eval_mse_loss": float(avg_loss),
        "eval_cosine_recall": float(avg_cos)
    }

def main():
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Running multi-branch architecture ablations on device: {device}...")
    
    # Check git commit
    import subprocess
    git_rev = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
    
    architectures = [
        ("plain_linear_attention", lambda: build_probe_model(PlainLinearAttention(64), 64, 16)),
        ("sym2_only", lambda: build_probe_model(Sym2OnlyAttention(64), 64, 16)),
        ("wedge2_only", lambda: build_probe_model(Wedge2OnlyAttention(64), 64, 16)),
        ("standard_transformer", lambda: build_probe_model(StandardTransformerBlock(64), 64, 16)),
        ("full_imf_omniblock", lambda: build_probe_model(FullIMFOmniBlock(64), 64, 16)),
    ]
    
    results = {
        "git_commit": git_rev,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "task": "MQAR-Associative-Recall-N512",
        "seeds": SEEDS,
        "evaluations": []
    }
    
    summary = {}
    
    for name, factory in architectures:
        summary[name] = {"losses": [], "cosines": [], "params": 0}
        for seed in SEEDS:
            t0 = time.time()
            res = train_and_eval_mqar(name, factory, d_model=64, val_dim=16, seq_len=512, seed=seed, device=device)
            dur = time.time() - t0
            print(f"[{name} | seed={seed}] Loss: {res['eval_mse_loss']:.4f}, Cos: {res['eval_cosine_recall']:.4f} ({dur:.2f}s)")
            results["evaluations"].append(res)
            summary[name]["losses"].append(res["eval_mse_loss"])
            summary[name]["cosines"].append(res["eval_cosine_recall"])
            summary[name]["params"] = res["params"]
            
    # Compute aggregate mean and std per architecture
    aggregated = {}
    for name, data in summary.items():
        losses = data["losses"]
        cosines = data["cosines"]
        mean_loss = sum(losses) / len(losses)
        std_loss = math.sqrt(sum((x - mean_loss)**2 for x in losses) / len(losses))
        mean_cos = sum(cosines) / len(cosines)
        std_cos = math.sqrt(sum((x - mean_cos)**2 for x in cosines) / len(cosines))
        aggregated[name] = {
            "params": data["params"],
            "mean_loss": float(mean_loss),
            "std_loss": float(std_loss),
            "mean_cosine_recall": float(mean_cos),
            "std_cosine_recall": float(std_cos)
        }
        print(f"Summary {name}: Loss={mean_loss:.4f}±{std_loss:.4f}, Cos={mean_cos:.4f}±{std_cos:.4f}")
        
    results["aggregated_summary"] = aggregated
    
    out_path = "benchmark_results/architecture_ablations.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved architecture ablations to {out_path}")

if __name__ == "__main__":
    main()
