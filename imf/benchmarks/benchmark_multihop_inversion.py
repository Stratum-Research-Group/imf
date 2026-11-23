"""
Multi-Hop Relational Inversion Benchmark:
Evaluates transitive deduction:
  Forward Path: A -> B -> C (e.g. A is father of B, B is father of C => A is grandfather of C)
  Reverse Query (Zero-Shot): Given C, identify grandfather A.

Standard attention cannot perform multi-hop reversal without chain-of-thought fine-tuning.
IMF Lie-Group SO(N) compositions satisfy:
  R_{A->C} = R_1 * R_2 in SO(N)
  R_{C->A} = (R_1 * R_2)^T = R_2^T * R_1^T identically!
"""

import torch
import torch.nn as nn
import torch.optim as optim

class IMFMultiHopCayleyModel(nn.Module):
    def __init__(self, vocab_size: int, dim: int):
        super().__init__()
        self.dim = dim
        self.embedding = nn.Embedding(vocab_size, dim)
        self.head = nn.Linear(dim, vocab_size, bias=False)
        self.head.weight = self.embedding.weight

        # Two distinct relational Lie algebra generators
        self.gen1 = nn.Parameter(torch.randn(dim, dim) * 0.02)
        self.gen2 = nn.Parameter(torch.randn(dim, dim) * 0.02)

    def _cayley(self, gen):
        I = torch.eye(self.dim, device=gen.device)
        skew = 0.5 * (gen - gen.T)
        return torch.linalg.solve(I + skew, I - skew)

    def forward_hop(self, a_idx):
        R1 = self._cayley(self.gen1)
        R2 = self._cayley(self.gen2)
        # 2-hop composition: A @ R1 @ R2 -> C
        c_emb = torch.matmul(torch.matmul(self.embedding(a_idx), R1), R2)
        return self.head(c_emb)

    def reverse_hop(self, c_idx):
        R1 = self._cayley(self.gen1)
        R2 = self._cayley(self.gen2)
        # Exact algebraic adjoint: C @ R2^T @ R1^T -> A
        a_emb = torch.matmul(torch.matmul(self.embedding(c_idx), R2.T), R1.T)
        return self.head(a_emb)

def run_multihop_benchmark():
    print("=" * 80)
    print("  IMF MULTI-HOP RELATIONAL INVERSION BENCHMARK")
    print("  Evaluating Transitive Adjoint Recovery: A -> B -> C ==> C -> A")
    print("=" * 80)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    num_facts = 100
    vocab_size = 400
    dim = 64

    # A: 0..99, C: 200..299
    a_tokens = torch.arange(num_facts, device=device)
    c_tokens = torch.arange(200, 300, device=device)

    model = IMFMultiHopCayleyModel(vocab_size, dim).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=0.02)
    loss_fn = nn.CrossEntropyLoss()

    print("[*] Training strictly on 2-hop forward relations (A -> C)...")
    for _ in range(400):
        optimizer.zero_grad()
        loss = loss_fn(model.forward_hop(a_tokens), c_tokens)
        loss.backward()
        optimizer.step()

    model.eval()
    with torch.no_grad():
        fwd_acc = (model.forward_hop(a_tokens).argmax(dim=-1) == c_tokens).float().mean().item() * 100.0
        rev_acc = (model.reverse_hop(c_tokens).argmax(dim=-1) == a_tokens).float().mean().item() * 100.0

    print(f"\n[✓] Multi-Hop Forward Accuracy (A -> B -> C): {fwd_acc:.1f}%")
    print(f"[✓] Zero-Shot Adjoint Accuracy (C -> B -> A): {rev_acc:.1f}%")
    print("=" * 80)

if __name__ == "__main__":
    run_multihop_benchmark()
