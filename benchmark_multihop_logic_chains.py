"""
benchmark_multihop_logic_chains.py
Synthetic Logic & Multi-Hop Theorem Proving Benchmark.

Evaluates deductive reasoning capabilities across multi-hop logic chains:
Premises:
  A_0 -> A_1
  A_1 -> A_2
  ...
  A_{k-1} -> A_k
Query:
  Does A_0 entail A_k? (True)
  Does A_0 entail Distractor_k? (False)

Compares:
1. Standard Pairwise Multi-Head Softmax Attention (O(k) composition degradation)
2. Pairwise Fused SAVG Attention (Symmetric-Antisymmetric Virtual Grid)
3. Higher-Arity Simplex Binding (Arity-3 Triplet hyperfaces)
4. IMF-OmniBlock (Unified Unitary Lie SSM + Continuous Simplex Convolution + SU(2) Gauge Curvature)

Measures:
- Deduction Accuracy across k = 3, 5, 8, 12 hops
- Forward step latency (ms)
- Context length robustness
"""

import time
import random
import torch
import torch.nn as nn
import torch.nn.functional as F

from multihead_savg import MultiHeadSAVGLayer
from higher_arity_simplex import ContinuousSimplexConvolutionalBinding
from imf.omni_block import IMFOmniBlock


class StandardAttentionModel(nn.Module):
    def __init__(self, vocab_size: int, d_model: int = 128, num_heads: int = 4):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.attn = nn.MultiheadAttention(d_model, num_heads, batch_first=True)
        self.norm = nn.RMSNorm(d_model)
        self.classifier = nn.Linear(d_model, 2)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        x = self.embedding(input_ids)
        x_norm = self.norm(x)
        T = input_ids.shape[1]
        attn_mask = torch.triu(torch.full((T, T), float("-inf"), device=input_ids.device), diagonal=1)
        attn_out, _ = self.attn(x_norm, x_norm, x_norm, attn_mask=attn_mask, is_causal=True)
        x = x + attn_out
        # Readout from final token
        return self.classifier(x[:, -1, :])


class SAVGModel(nn.Module):
    def __init__(self, vocab_size: int, d_model: int = 128, num_heads: int = 4):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.savg = MultiHeadSAVGLayer(d_model, num_heads)
        self.norm = nn.RMSNorm(d_model)
        self.classifier = nn.Linear(d_model, 2)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        x = self.embedding(input_ids)
        x_norm = self.norm(x)
        savg_out = self.savg(x_norm)
        x = x + savg_out
        return self.classifier(x[:, -1, :])


class HigherAritySimplexModel(nn.Module):
    def __init__(self, vocab_size: int, d_model: int = 128, rank: int = 32, window: int = 4):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.binding = ContinuousSimplexConvolutionalBinding(d_model=d_model, rank=rank, default_window=window)
        self.norm = nn.RMSNorm(d_model)
        self.classifier = nn.Linear(d_model, 2)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        x = self.embedding(input_ids)
        x_norm = self.norm(x)
        simplex_out = self.binding(x_norm)
        x = x + simplex_out
        return self.classifier(x[:, -1, :])


class IMFOmniModel(nn.Module):
    def __init__(self, vocab_size: int, d_model: int = 128, num_heads: int = 4):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.omni = IMFOmniBlock(
            d_model=d_model,
            num_heads=num_heads,
            polytope_dim=8,
            conv_rank=32,
            conv_window=6,
            use_triton_ssm=False,
        )
        self.classifier = nn.Linear(d_model, 2)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        x = self.embedding(input_ids)
        x = self.omni(x)
        return self.classifier(x[:, -1, :])


def generate_logic_dataset(num_samples: int, k_hops: int, vocab_offset: int = 10, total_predicates: int = 200):
    """
    Generates multi-hop synthetic deduction chains.
    Each chain has k premises: (A_0, IMPLIES, A_1), ..., (A_{k-1}, IMPLIES, A_k)
    Query: (A_0, QUERY, Target) -> Label: 1 if Target == A_k else 0
    Special tokens:
      IMPLIES: 1, QUERY: 2, TRUE: 3, FALSE: 4, PAD: 0
    """
    samples = []
    labels = []
    
    for _ in range(num_samples):
        # Sample distinct predicates
        chain_len = k_hops + 1
        nodes = random.sample(range(vocab_offset, vocab_offset + total_predicates), chain_len)
        
        # Build premises
        tokens = []
        for i in range(k_hops):
            tokens.extend([nodes[i], 1, nodes[i+1]]) # A_i -> A_{i+1}
        
        # 50% positive (Target == nodes[-1]), 50% negative (Target == distractor)
        is_positive = random.random() < 0.5
        if is_positive:
            target = nodes[-1]
            label = 1
        else:
            # Pick a distractor not in the chain
            distractor_pool = [p for p in range(vocab_offset, vocab_offset + total_predicates) if p not in nodes]
            target = random.choice(distractor_pool)
            label = 0
            
        # Query tokens
        tokens.extend([nodes[0], 2, target])
        samples.append(tokens)
        labels.append(label)

    return torch.tensor(samples, dtype=torch.long), torch.tensor(labels, dtype=torch.long)


def train_and_eval(model: nn.Module, train_x: torch.Tensor, train_y: torch.Tensor, test_x: torch.Tensor, test_y: torch.Tensor, steps: int = 400, lr: float = 1e-3, device: str = "cuda"):
    model = model.to(device)
    train_x, train_y = train_x.to(device), train_y.to(device)
    test_x, test_y = test_x.to(device), test_y.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-2)
    criterion = nn.CrossEntropyLoss()

    model.train()
    batch_size = 64
    num_samples = train_x.shape[0]

    t0 = time.time()
    for step in range(steps):
        idx = torch.randint(0, num_samples, (batch_size,), device=device)
        bx, by = train_x[idx], train_y[idx]

        optimizer.zero_grad()
        logits = model(bx)
        loss = criterion(logits, by)
        loss.backward()
        optimizer.step()

    train_time = time.time() - t0

    model.eval()
    with torch.no_grad():
        test_logits = model(test_x)
        preds = test_logits.argmax(dim=-1)
        acc = (preds == test_y).float().mean().item() * 100.0

    return acc, train_time


def run_benchmark():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"==========================================================================")
    print(f"IMF Frontier Benchmark: Multi-Hop Theorem Proving & Deductive Reasoning")
    print(f"Device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")
    print(f"==========================================================================")

    vocab_size = 300
    d_model = 128
    hops_list = [3, 5, 8, 12]

    results = {
        "Standard Pairwise Attention": {},
        "Fused SAVG Attention": {},
        "Higher-Arity Simplex (m=3)": {},
        "IMF-OmniBlock (Unified)": {},
    }

    for k in hops_list:
        print(f"\n--- Testing Multi-Hop Depth: k = {k} Hops ---")
        train_x, train_y = generate_logic_dataset(num_samples=2000, k_hops=k)
        test_x, test_y = generate_logic_dataset(num_samples=500, k_hops=k)

        # 1. Standard Attention
        m_attn = StandardAttentionModel(vocab_size=vocab_size, d_model=d_model, num_heads=4)
        acc_attn, t_attn = train_and_eval(m_attn, train_x, train_y, test_x, test_y, steps=300, device=device)
        results["Standard Pairwise Attention"][k] = acc_attn
        print(f"  [Standard Attention]      Accuracy: {acc_attn:6.2f}% | Train Time: {t_attn:.2f}s")

        # 2. SAVG Attention
        m_savg = SAVGModel(vocab_size=vocab_size, d_model=d_model, num_heads=4)
        acc_savg, t_savg = train_and_eval(m_savg, train_x, train_y, test_x, test_y, steps=300, device=device)
        results["Fused SAVG Attention"][k] = acc_savg
        print(f"  [Fused SAVG Attention]    Accuracy: {acc_savg:6.2f}% | Train Time: {t_savg:.2f}s")

        # 3. Higher-Arity Simplex (Continuous Convolution)
        m_simplex = HigherAritySimplexModel(vocab_size=vocab_size, d_model=d_model, rank=32, window=4)
        acc_simplex, t_simplex = train_and_eval(m_simplex, train_x, train_y, test_x, test_y, steps=300, device=device)
        results["Higher-Arity Simplex (m=3)"][k] = acc_simplex
        print(f"  [Simplex Arity-3 Binding] Accuracy: {acc_simplex:6.2f}% | Train Time: {t_simplex:.2f}s")

        # 4. IMF-OmniBlock
        m_omni = IMFOmniModel(vocab_size=vocab_size, d_model=d_model, num_heads=4)
        acc_omni, t_omni = train_and_eval(m_omni, train_x, train_y, test_x, test_y, steps=300, device=device)
        results["IMF-OmniBlock (Unified)"][k] = acc_omni
        print(f"  [IMF-OmniBlock (Unified)] Accuracy: {acc_omni:6.2f}% | Train Time: {t_omni:.2f}s")

    print("\n" + "="*74)
    print("FINAL SUMMARY: Multi-Hop Deductive Reasoning Accuracy (%)")
    print("="*74)
    header = f"{'Architecture':<32} | " + " | ".join([f"k={k} hops" for k in hops_list])
    print(header)
    print("-" * len(header))
    for model_name, accs in results.items():
        row = f"{model_name:<32} | " + " | ".join([f"{accs[k]:8.2f}%" for k in hops_list])
        print(row)
    print("="*74)


if __name__ == "__main__":
    run_benchmark()
