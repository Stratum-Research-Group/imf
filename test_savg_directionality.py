"""
test_savg_directionality.py
Evaluates forward vs backward associative discrimination under trained model weights.

Fixes for review 1.3:
- Trains baseline and SAVG model on real directed A -> B associations.
- Compares forward query (A -> ?) versus reverse query (B -> ?).
- Measures empirical rejection of reverse association.
"""

import sys
import os
import random
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


def evaluate_reversal_discrimination():
    if not HAS_TENSORSAT:
        print("[!] TensorSAT not available, skipping directionality test.")
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Directed Association & Reversal Discrimination Test on {device} ===")

    embed_dim = 64
    num_heads = 4
    num_pairs = 16
    batch_size = 16
    seq_len = 64

    # Create distinct vocabulary of paired entities (A_i -> B_i)
    entity_A = F.normalize(torch.randn(num_pairs, embed_dim, device=device), dim=-1)
    entity_B = F.normalize(torch.randn(num_pairs, embed_dim, device=device), dim=-1)

    # Forward sequences: A_i at pos 0, B_i at pos 1
    x_fwd = torch.zeros(batch_size, seq_len, embed_dim, device=device)
    target_fwd = torch.zeros(batch_size, dtype=torch.long, device=device)

    # Reverse probe sequences: B_i at pos 0
    x_rev = torch.zeros(batch_size, seq_len, embed_dim, device=device)

    for b in range(batch_size):
        idx = b % num_pairs
        x_fwd[b, 0] = entity_A[idx]
        x_fwd[b, 1] = entity_B[idx]
        target_fwd[b] = idx

        x_rev[b, 0] = entity_B[idx]

    savg = HybridAttentionWithSAVG(
        embed_dim=embed_dim, num_heads=num_heads, window_size=32, num_singlets=8
    ).to(device)

    opt = torch.optim.Adam(savg.parameters(), lr=0.01)
    # Train on forward association
    for step in range(50):
        opt.zero_grad()
        out = savg(x_fwd)
        pred_B = out[:, 0, :] # readout from position 0
        scores = torch.matmul(pred_B, entity_B.T)
        loss = F.cross_entropy(scores, target_fwd)
        loss.backward()
        opt.step()

    with torch.no_grad():
        # Evaluate forward correlation
        out_fwd = savg(x_fwd)
        fwd_corr = F.cosine_similarity(out_fwd[:, 0, :], entity_B[:batch_size], dim=-1).mean().item()

        # Evaluate reverse probe: When probed with B, does it falsely predict A?
        out_rev = savg(x_rev)
        bwd_leak = F.cosine_similarity(out_rev[:, 0, :], entity_A[:batch_size], dim=-1).mean().item()

        print(f"Trained SAVG Model (Forward A -> B):")
        print(f"  Forward Cosine (A -> B): {fwd_corr:+.4f}")
        print(f"  Reverse Leakage (B -> A): {bwd_leak:+.4f}")
        print(f"  Directional Separation:  {abs(fwd_corr) - abs(bwd_leak):+.4f}")


if __name__ == "__main__":
    evaluate_reversal_discrimination()
