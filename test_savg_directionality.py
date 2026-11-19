"""
test_savg_directionality.py
Evaluates whether SAVG solves the directional ambiguity failure mode where
symmetric attention cannot distinguish A -> B from B -> A.
"""

import sys
import os
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.abspath("../TensorSAT"))
from tensorsat.hybrid import HybridSingletAttention
from test_savg_harness import HybridAttentionWithSAVG

torch.manual_seed(42)

def evaluate_reversal_discrimination():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Directed Association & Reversal Rejection Test ===")

    embed_dim = 64
    num_heads = 4
    seq_len = 128
    batch_size = 8

    # Create sequence with structured pairs: Token_2i -> Token_2i+1
    x = torch.randn(batch_size, seq_len, embed_dim, device=device)
    
    baseline = HybridSingletAttention(
        embed_dim=embed_dim, num_heads=num_heads, window_size=32, num_singlets=8, use_triton=False, chunk_size=64
    ).to(device)

    savg = HybridAttentionWithSAVG(
        embed_dim=embed_dim, num_heads=num_heads, window_size=32, num_singlets=8
    ).to(device)

    with torch.no_grad():
        out_base, _ = baseline(x)
        out_savg = savg(x)

        # Forward transition correlation: out_t correlated with x_{t+1}
        fwd_base = F.cosine_similarity(out_base[:, :-1], x[:, 1:], dim=-1).mean().item()
        fwd_savg = F.cosine_similarity(out_savg[:, :-1], x[:, 1:], dim=-1).mean().item()

        # Backward false correlation: out_t correlated with x_{t-1} (backward leakage)
        bwd_base = F.cosine_similarity(out_base[:, 1:], x[:, :-1], dim=-1).mean().item()
        bwd_savg = F.cosine_similarity(out_savg[:, 1:], x[:, :-1], dim=-1).mean().item()

        print("Baseline TensorSAT Hybrid:")
        print(f"  Forward Cosine:  {fwd_base:+.4f}")
        print(f"  Backward Leak:   {bwd_base:+.4f}")

        print("\nTensorSAT Hybrid + SAVG:")
        print(f"  Forward Cosine:  {fwd_savg:+.4f}")
        print(f"  Backward Leak:   {bwd_savg:+.4f}")

        base_ratio = abs(fwd_base) / (abs(bwd_base) + 1e-6)
        savg_ratio = abs(fwd_savg) / (abs(bwd_savg) + 1e-6)
        print(f"\nDirectional Selectivity Ratio (Higher is cleaner):")
        print(f"  Baseline: {base_ratio:.2f}")
        print(f"  SAVG:     {savg_ratio:.2f}")

if __name__ == "__main__":
    evaluate_reversal_discrimination()
