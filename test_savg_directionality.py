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
    print(f"=== Directed Association & In-Context Reversal Discrimination Test on {device} ===")

    embed_dim = 64
    num_heads = 4
    num_pairs = 16
    batch_size = 16
    seq_len = 64

    # Create distinct vocabulary of paired entities (A_i -> B_i)
    entity_A = F.normalize(torch.randn(num_pairs, embed_dim, device=device), dim=-1)
    entity_B = F.normalize(torch.randn(num_pairs, embed_dim, device=device), dim=-1)

    # In-context sequence format:
    # Fact placed at pos 0 (A) and pos 1 (B)
    # Query placed at pos 2:
    #   Forward query: pos 2 = A_idx, target = B_idx (readout at pos 2)
    #   Reverse probe: pos 2 = B_idx, target should reject (not retrieve A_idx as if B->A)
    def make_sequences(pairs_idx):
        N = len(pairs_idx)
        x_f = torch.zeros(N, seq_len, embed_dim, device=device)
        x_r = torch.zeros(N, seq_len, embed_dim, device=device)
        tgt = torch.zeros(N, dtype=torch.long, device=device)

        for b, idx in enumerate(pairs_idx):
            # Context
            x_f[b, 0] = entity_A[idx]
            x_f[b, 1] = entity_B[idx]
            # Forward query at pos 2
            x_f[b, 2] = entity_A[idx]
            tgt[b] = idx

            # Reverse probe sequence: same context A->B, probe with B at pos 2
            x_r[b, 0] = entity_A[idx]
            x_r[b, 1] = entity_B[idx]
            x_r[b, 2] = entity_B[idx]

        return x_f, x_r, tgt

    train_indices = list(range(batch_size))
    x_fwd, x_rev, target_fwd = make_sequences(train_indices)

    models = {
        "Baseline TensorSAT": HybridSingletAttention(
            embed_dim=embed_dim, num_heads=num_heads, window_size=32, num_singlets=8, use_triton=False, chunk_size=32
        ).to(device),
        "TensorSAT + SAVG": HybridAttentionWithSAVG(
            embed_dim=embed_dim, num_heads=num_heads, window_size=32, num_singlets=8
        ).to(device)
    }

    for name, model in models.items():
        opt = torch.optim.Adam(model.parameters(), lr=0.01)
        # Train on forward association query at pos 2
        for step in range(50):
            opt.zero_grad()
            out = model(x_fwd)
            if isinstance(out, tuple):
                out = out[0]
            pred_B = out[:, 2, :] # readout from position 2
            scores = torch.matmul(pred_B, entity_B.T)
            loss = F.cross_entropy(scores, target_fwd)
            loss.backward()
            opt.step()

        with torch.no_grad():
            out_fwd = model(x_fwd)
            if isinstance(out_fwd, tuple):
                out_fwd = out_fwd[0]
            pred_fwd = out_fwd[:, 2, :]
            fwd_scores = torch.matmul(pred_fwd, entity_B.T)
            fwd_acc = (torch.argmax(fwd_scores, dim=-1) == target_fwd).float().mean().item() * 100.0
            fwd_corr = F.cosine_similarity(pred_fwd, entity_B[target_fwd], dim=-1).mean().item()

            # Reverse probe: Probe at pos 2 with B, measure if it predicts A
            out_rev = model(x_rev)
            if isinstance(out_rev, tuple):
                out_rev = out_rev[0]
            pred_rev = out_rev[:, 2, :]
            rev_scores = torch.matmul(pred_rev, entity_A.T)
            rev_false_recall = (torch.argmax(rev_scores, dim=-1) == target_fwd).float().mean().item() * 100.0
            bwd_leak = F.cosine_similarity(pred_rev, entity_A[target_fwd], dim=-1).mean().item()

            print(f"\n{name}:")
            print(f"  Forward Acc (A -> B):    {fwd_acc:5.1f}% (Cosine: {fwd_corr:+.4f})")
            print(f"  Reverse Leak (B -> A):   {rev_false_recall:5.1f}% (Cosine: {bwd_leak:+.4f})")
            print(f"  Directional Separation:  {fwd_corr - bwd_leak:+.4f}")


if __name__ == "__main__":
    evaluate_reversal_discrimination()
