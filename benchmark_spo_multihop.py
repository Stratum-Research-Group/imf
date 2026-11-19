"""
benchmark_spo_multihop.py
Multi-Hop Relational Knowledge Graph Benchmark:
Compares:
  1. Standard Pairwise Attention (Arity m = 2) - relies on two chained pairwise steps (S -> P, P -> O).
  2. Higher-Arity Simplex Binding (Arity m = 3) - atomically couples (Subject, Predicate, Object)
     across triangular 2-simplex hyperfaces.

Task: Multi-Hop Knowledge Graph Traversal
Facts stored:
  (Alice, bornIn, CityX)
  (CityX, locatedIn, CountryY)
  (CountryY, capitalCity, CapitalZ)
Query:
  (Alice, bornIn.locatedIn.capitalCity, ?) -> Target: CapitalZ
Distractor noise:
  (Bob, bornIn, CityW)
  (CityW, locatedIn, CountryQ)
  ...
Evaluated on CUDA.
"""

import sys
import os
import time
import random
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.abspath("../TensorSAT"))
from higher_arity_simplex import HigherAritySimplexBinding

torch.manual_seed(42)
random.seed(42)


class PairwiseChainedBaseline(nn.Module):
    """
    Standard pairwise baseline (Arity m = 2):
    Must compose Subject -> Predicate and then result -> Object sequentially.
    """
    def __init__(self, d_model: int):
        super().__init__()
        self.d = d_model
        self.W_sp = nn.Linear(d_model * 2, d_model)
        self.W_po = nn.Linear(d_model * 2, d_model)
        self.attn = nn.MultiheadAttention(d_model, num_heads=4, batch_first=True)
        self.head = nn.Linear(d_model, d_model)

    def forward(self, subjects: torch.Tensor, predicates: torch.Tensor, objects: torch.Tensor):
        # Step 1: Pairwise combine Subject and Predicate
        sp = F.relu(self.W_sp(torch.cat([subjects, predicates], dim=-1)))
        # Step 2: Cross-attend to objects
        attn_out, _ = self.attn(sp, objects, objects)
        return self.head(attn_out)


class Arity3SimplexModel(nn.Module):
    """
    Higher-Arity Simplex Model (Arity m = 3):
    Atomically couples (Subject, Predicate, Object) on a 2-simplex hyperface.
    """
    def __init__(self, d_model: int, rank: int = 32):
        super().__init__()
        self.binding = HigherAritySimplexBinding(d_model=d_model, arity=3, rank=rank, num_corners=10)
        self.head = nn.Linear(d_model, d_model)

    def forward(self, subjects: torch.Tensor, predicates: torch.Tensor, objects: torch.Tensor):
        # Atomic 3-way simplex face binding
        triplet_state = self.binding([subjects, predicates, objects])
        return self.head(triplet_state)


def generate_multihop_graph_batch(batch_size: int, num_entities: int, num_relations: int, d_model: int, device: torch.device):
    """
    Generates synthetic Subject-Predicate-Object graphs with multi-hop chain targets.
    """
    entity_embeds = F.normalize(torch.randn(num_entities, d_model, device=device), dim=-1)
    relation_embeds = F.normalize(torch.randn(num_relations, d_model, device=device), dim=-1)

    # Generate facts: (S, P, O)
    # We create chains: e1 -> r1 -> e2 -> r2 -> e3
    chains = []
    for _ in range(batch_size):
        e1 = random.randint(0, num_entities - 1)
        e2 = (e1 + random.randint(1, 10)) % num_entities
        e3 = (e2 + random.randint(1, 10)) % num_entities
        r1 = random.randint(0, num_relations - 1)
        r2 = random.randint(0, num_relations - 1)
        chains.append((e1, r1, e2, r2, e3))

    # Construct input tensors
    # S, P, O represent the 2-hop sequence
    S_batch = torch.stack([entity_embeds[c[0]] for c in chains]) # e1
    P_batch = torch.stack([relation_embeds[c[1]] + relation_embeds[c[3]] for c in chains]) # r1 + r2 composed relation
    O_target = torch.stack([entity_embeds[c[4]] for c in chains]) # e3 (target)
    # Candidate object pool for contrastive retrieval
    candidates = entity_embeds.unsqueeze(0).expand(batch_size, -1, -1) # [B, num_entities, d]

    return S_batch, P_batch, O_target, candidates, [c[4] for c in chains]


def run_spo_multihop_benchmark():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 88)
    print(f"BENCHMARK: Multi-Hop Subject-Predicate-Object (SPO) Simplex Binding on {device}")
    print("=" * 88)

    d_model = 64
    num_entities = 128
    num_relations = 16
    batch_size = 32
    num_steps = 150

    S, P, O_target, candidates, target_indices = generate_multihop_graph_batch(
        batch_size=batch_size, num_entities=num_entities, num_relations=num_relations, d_model=d_model, device=device
    )
    targets_tensor = torch.tensor(target_indices, device=device, dtype=torch.long)

    # For training sequence shape [B, 1, d]
    S_in = S.unsqueeze(1)
    P_in = P.unsqueeze(1)
    O_in = O_target.unsqueeze(1)

    models = {
        "Pairwise Attention (Arity-2)": PairwiseChainedBaseline(d_model).to(device),
        "Simplex Hyperface (Arity-3)": Arity3SimplexModel(d_model, rank=32).to(device)
    }

    print(f"{'Model Architecture':<32} | {'Initial Loss':<13} | {'Final Loss':<13} | {'Retrieval Acc %':<16} | {'Step Time':<9}")
    print("-" * 88)

    for name, model in models.items():
        optimizer = torch.optim.Adam(model.parameters(), lr=0.008)
        init_loss = 0.0
        final_loss = 0.0

        # Warmup
        _ = model(S_in, P_in, O_in)
        if device.type == "cuda":
            torch.cuda.synchronize()

        t0 = time.perf_counter()
        for step in range(num_steps):
            optimizer.zero_grad()
            out = model(S_in, P_in, O_in).squeeze(1) # [B, d]

            # Contrastive cosine similarity across all candidate entities
            scores = torch.matmul(out, candidates[0].T) # [B, num_entities]
            loss = F.cross_entropy(scores, targets_tensor)
            loss.backward()
            optimizer.step()

            if step == 0:
                init_loss = loss.item()
            if step == num_steps - 1:
                final_loss = loss.item()

        if device.type == "cuda":
            torch.cuda.synchronize()
        elapsed = (time.perf_counter() - t0) * 1000.0 / num_steps

        # Accuracy evaluation
        with torch.no_grad():
            preds = torch.argmax(scores, dim=-1)
            acc = (preds == targets_tensor).float().mean().item() * 100.0

        print(f"{name:<32} | {init_loss:<13.4f} | {final_loss:<13.4f} | {acc:<16.1f} | {elapsed:<6.2f} ms")

    print("=" * 88)


if __name__ == "__main__":
    run_spo_multihop_benchmark()
