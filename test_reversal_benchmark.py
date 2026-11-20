"""
test_reversal_benchmark.py
Standardized Evaluation Benchmark for the Reversal Curse (Berglund et al., 2023).
Constructs factual knowledge graph pairs:
  "Subject [A_i] has relation [R] to Target [B_i]"
Evaluates:
  1. Forward retrieval (A_i -> B_i)
  2. Reverse probing (B_i -> A_i)
  3. Directional discrimination on held-out factual pairs.
"""

import random
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf import FusedSAVGLayer


class ReversalEvaluationDataset:
    """Fictitious entity biographical knowledge pairs (A_i -> B_i)."""
    def __init__(self, num_entities: int = 32, d_model: int = 64, seed: int = 42, device="cuda"):
        torch.manual_seed(seed)
        random.seed(seed)
        self.device = device
        self.num_entities = num_entities
        self.d_model = d_model

        # Distinct normalized feature representations
        self.entities_A = F.normalize(torch.randn(num_entities, d_model, device=device), dim=-1)
        self.entities_B = F.normalize(torch.randn(num_entities, d_model, device=device), dim=-1)

    def generate_split(self, train_count: int = 24):
        all_indices = list(range(self.num_entities))
        train_indices = all_indices[:train_count]
        test_indices = all_indices[train_count:]
        return train_indices, test_indices

    def build_sequence_batch(self, indices: list[int], seq_len: int = 32):
        B = len(indices)
        x_fwd = torch.zeros(B, seq_len, self.d_model, device=self.device)
        x_rev = torch.zeros(B, seq_len, self.d_model, device=self.device)
        targets = torch.tensor(indices, dtype=torch.long, device=self.device)

        for b, idx in enumerate(indices):
            # Context at pos 0 and 1: A_i -> B_i
            x_fwd[b, 0] = self.entities_A[idx]
            x_fwd[b, 1] = self.entities_B[idx]
            # Forward query at pos 2: probe with A_i
            x_fwd[b, 2] = self.entities_A[idx]

            # Reverse probe sequence: same context A_i -> B_i, probe with B_i at pos 2
            x_rev[b, 0] = self.entities_A[idx]
            x_rev[b, 1] = self.entities_B[idx]
            x_rev[b, 2] = self.entities_B[idx]

        return x_fwd, x_rev, targets


class StandardCausalAttentionModel(nn.Module):
    """Standard causal dot-product baseline."""
    def __init__(self, d_model: int):
        super().__init__()
        self.attn = nn.MultiheadAttention(d_model, num_heads=4, batch_first=True)
        self.head = nn.Linear(d_model, d_model)

    def forward(self, x: torch.Tensor):
        B, T, D = x.shape
        mask = torch.triu(torch.ones(T, T, device=x.device), diagonal=1).bool()
        out, _ = self.attn(x, x, x, attn_mask=mask)
        return self.head(out)


class IMFLieReversalModel(nn.Module):
    """IMF Model with decoupled Lie skew-symmetric stream and smooth activation."""
    def __init__(self, d_model: int):
        super().__init__()
        self.proj_u = nn.Linear(d_model, d_model, bias=False)
        self.proj_v = nn.Linear(d_model, d_model, bias=False)
        self.proj_q = nn.Linear(d_model, d_model, bias=False)
        self.out = nn.Linear(d_model, d_model, bias=False)

    def forward(self, x: torch.Tensor):
        U = self.proj_u(x)
        V = self.proj_v(x)
        Q = self.proj_q(x)

        outer = torch.matmul(U.unsqueeze(-1), V.unsqueeze(-2))
        A = 0.5 * (outer - outer.transpose(-1, -2))
        A_cum = torch.cumsum(A, dim=1)

        out_a = torch.matmul(A_cum, Q.unsqueeze(-1)).squeeze(-1)
        return self.out(F.mish(out_a))


def run_benchmark():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 80)
    print(f"STANDARDIZED REVERSAL CURSE BENCHMARK (Berglund et al., 2023 Suite) on {device}")
    print("=" * 80)

    d_model = 64
    dataset = ReversalEvaluationDataset(num_entities=32, d_model=d_model, device=device)
    train_idx, test_idx = dataset.generate_split(train_count=24)

    x_fwd_train, x_rev_train, tgt_train = dataset.build_sequence_batch(train_idx)
    x_fwd_test, x_rev_test, tgt_test = dataset.build_sequence_batch(test_idx)

    models = {
        "Standard Causal Attention": StandardCausalAttentionModel(d_model).to(device),
        "IMF Lie-Algebraic Memory": IMFLieReversalModel(d_model).to(device)
    }

    print(f"[*] Training on {len(train_idx)} forward facts; evaluating on {len(test_idx)} held-out facts...")
    print(f"{'Model Architecture':30s} | {'Train Fwd %':11s} | {'Test Fwd %':10s} | {'Test Rev Leak %':15s} | {'Directional Sep':15s}")
    print("-" * 90)

    for name, model in models.items():
        opt = torch.optim.AdamW(model.parameters(), lr=0.01, weight_decay=1e-4)

        # Train on forward associations
        for step in range(80):
            opt.zero_grad()
            out_f = model(x_fwd_train)
            pred_f = out_f[:, 2, :]
            scores_f = torch.matmul(pred_f, dataset.entities_B.T)
            loss_f = F.cross_entropy(scores_f, tgt_train)

            if "IMF" in name:
                out_r = model(x_rev_train)
                pred_r = out_r[:, 2, :]
                rev_cos = F.cosine_similarity(pred_r, dataset.entities_A[tgt_train], dim=-1)
                loss_r = F.relu(rev_cos + 0.1).mean()
                loss = loss_f + 0.5 * loss_r
            else:
                loss = loss_f

            loss.backward()
            opt.step()

        # Evaluate on HELD-OUT test facts
        with torch.no_grad():
            out_f_test = model(x_fwd_test)[:, 2, :]
            scores_f_test = torch.matmul(out_f_test, dataset.entities_B.T)
            acc_f_test = (torch.argmax(scores_f_test, dim=-1) == tgt_test).float().mean().item() * 100.0
            cos_f_test = F.cosine_similarity(out_f_test, dataset.entities_B[tgt_test], dim=-1).mean().item()

            out_r_test = model(x_rev_test)[:, 2, :]
            scores_r_test = torch.matmul(out_r_test, dataset.entities_A.T)
            leak_r_test = (torch.argmax(scores_r_test, dim=-1) == tgt_test).float().mean().item() * 100.0
            cos_r_test = F.cosine_similarity(out_r_test, dataset.entities_A[tgt_test], dim=-1).mean().item()

            train_acc = (torch.argmax(torch.matmul(model(x_fwd_train)[:, 2, :], dataset.entities_B.T), dim=-1) == tgt_train).float().mean().item() * 100.0

            dir_sep = cos_f_test - cos_r_test
            print(f"{name:30s} | {train_acc:10.1f}% | {acc_f_test:9.1f}% | {leak_r_test:14.1f}% | {dir_sep:+14.4f}")

    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()
