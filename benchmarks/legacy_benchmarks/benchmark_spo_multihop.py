"""
benchmark_spo_multihop.py
Multi-Hop Subject-Predicate-Object (SPO) Relational Knowledge Retrieval.

Correct formulation:
- We formulate a multi-hop knowledge query: Given Head Entity (S) and Chained Relations (P),
  retrieve the target Tail Entity (O_target).
- The target O_target is NOT passed as input to the model.
- The model takes query (S, P) and predicts the entity representation in R^d.
- Evaluation is performed on HELD-OUT test chains unseen during training.
"""

import sys
import os
import time
import random
import torch
import torch.nn as nn
import torch.nn.functional as F

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TENSORSAT_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "TensorSAT"))
if os.path.exists(TENSORSAT_PATH) and TENSORSAT_PATH not in sys.path:
    sys.path.insert(0, TENSORSAT_PATH)

from higher_arity_simplex import HigherAritySimplexBinding

torch.manual_seed(42)
random.seed(42)


class PairwiseChainedBaseline(nn.Module):
    """
    Standard pairwise baseline (Arity m = 2):
    Composes Subject and Predicate relations sequentially via MLP and self-attention.
    Does NOT receive the target object as input.
    """
    def __init__(self, d_model: int):
        super().__init__()
        self.d = d_model
        self.W_sp = nn.Linear(d_model * 2, d_model)
        self.attn = nn.MultiheadAttention(d_model, num_heads=4, batch_first=True)
        self.head = nn.Linear(d_model, d_model)

    def forward(self, subjects: torch.Tensor, predicates: torch.Tensor):
        # inputs: [B, 1, d]
        sp = F.relu(self.W_sp(torch.cat([subjects, predicates], dim=-1)))
        attn_out, _ = self.attn(sp, sp, sp)
        return self.head(attn_out)


class Arity3SimplexQueryModel(nn.Module):
    """
    Higher-Arity Simplex Query Model:
    Binds (Subject, Predicate, QueryProbe) on a 2-simplex hyperface to retrieve tail.
    Query probe is a learned canonical query anchor (NOT the target object).
    """
    def __init__(self, d_model: int, rank: int = 32):
        super().__init__()
        self.binding = HigherAritySimplexBinding(d_model=d_model, arity=3, rank=rank, num_corners=10)
        self.query_anchor = nn.Parameter(torch.randn(1, 1, d_model) / (d_model ** 0.5))
        self.head = nn.Linear(d_model, d_model)

    def forward(self, subjects: torch.Tensor, predicates: torch.Tensor):
        batch_size = subjects.shape[0]
        anchor = self.query_anchor.expand(batch_size, 1, -1)
        # Binds (S, P, QueryAnchor) without leaking the target entity
        triplet_state = self.binding([subjects, predicates, anchor])
        return self.head(triplet_state)


def generate_multihop_graph_dataset(num_train=64, num_test=256, num_entities=128, num_relations=16, d_model=64, device="cpu", seed=42):
    """
    Generates deterministic knowledge graph chains over a fixed relation transition rule:
    e_{next} = T(e, r) = (e * (r + 1) + (r + 3)) % num_entities
    
    Chains: e1 -> r1 -> e2 -> r2 -> e3 (Target: e3 = T(T(e1, r1), r2))
    The model receives the subject e1 and relation embeddings (r1, r2) and must predict e3.
    """
    torch.manual_seed(seed)
    random.seed(seed)

    entity_embeds = F.normalize(torch.randn(num_entities, d_model, device=device), dim=-1)
    relation_embeds = F.normalize(torch.randn(num_relations, d_model, device=device), dim=-1)

    def transition(e, r):
        return (e * (r + 1) + (r + 3)) % num_entities

    def sample_deterministic_chains(n, existing_keys=None):
        chains = []
        keys = set() if existing_keys is None else set(existing_keys)
        attempts = 0
        while len(chains) < n and attempts < n * 100:
            attempts += 1
            e1 = random.randint(0, num_entities - 1)
            r1 = random.randint(0, num_relations - 1)
            r2 = random.randint(0, num_relations - 1)
            key = (e1, r1, r2)
            if key in keys:
                continue
            keys.add(key)
            e2 = transition(e1, r1)
            e3 = transition(e2, r2)
            chains.append((e1, r1, e2, r2, e3))
        return chains, keys

    train_chains, train_keys = sample_deterministic_chains(num_train)
    test_chains, _ = sample_deterministic_chains(num_test, existing_keys=train_keys)

    def to_tensors(ch):
        S = torch.stack([entity_embeds[c[0]] for c in ch]).unsqueeze(1)
        # Ordered relation projection / composition
        P = torch.stack([relation_embeds[c[1]] + 0.5 * relation_embeds[c[3]] for c in ch]).unsqueeze(1)
        targets = torch.tensor([c[4] for c in ch], device=device, dtype=torch.long)
        return S, P, targets

    train_data = to_tensors(train_chains)
    test_data = to_tensors(test_chains)
    return train_data, test_data, entity_embeds


def run_spo_multihop_benchmark():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 90)
    print(f"BENCHMARK: Multi-Hop Subject-Predicate Query Retrieval (NO Target Leakage) on {device}")
    print("=" * 90)

    d_model = 64
    num_entities = 128
    num_relations = 16
    num_train = 64
    num_test = 256
    num_steps = 150

    train_data, test_data, entity_embeds = generate_multihop_graph_dataset(
        num_train=num_train, num_test=num_test, num_entities=num_entities, num_relations=num_relations,
        d_model=d_model, device=device
    )
    S_train, P_train, y_train = train_data
    S_test, P_test, y_test = test_data

    models = {
        "Pairwise Attention (Arity-2)": PairwiseChainedBaseline(d_model).to(device),
        "Simplex Hyperface (Arity-3)": Arity3SimplexQueryModel(d_model, rank=32).to(device)
    }

    print(f"{'Model Architecture':<32} | {'Train Loss':<12} | {'Train Acc %':<12} | {'Held-Out Acc %':<15} | {'Step Time':<9}")
    print("-" * 90)

    for name, model in models.items():
        optimizer = torch.optim.Adam(model.parameters(), lr=0.008)
        final_loss = 0.0

        t0 = time.perf_counter()
        for step in range(num_steps):
            optimizer.zero_grad()
            out = model(S_train, P_train).squeeze(1) # [B, d]
            scores = torch.matmul(out, entity_embeds.T) # [B, num_entities]
            loss = F.cross_entropy(scores, y_train)
            loss.backward()
            optimizer.step()
            final_loss = loss.item()

        if device.type == "cuda":
            torch.cuda.synchronize()
        elapsed = (time.perf_counter() - t0) * 1000.0 / num_steps

        with torch.no_grad():
            train_preds = torch.argmax(scores, dim=-1)
            train_acc = (train_preds == y_train).float().mean().item() * 100.0

            # Evaluate on unseen held-out test chains
            test_out = model(S_test, P_test).squeeze(1)
            test_scores = torch.matmul(test_out, entity_embeds.T)
            test_preds = torch.argmax(test_scores, dim=-1)
            test_acc = (test_preds == y_test).float().mean().item() * 100.0

        print(f"{name:<32} | {final_loss:<12.4f} | {train_acc:<12.1f} | {test_acc:<15.1f} | {elapsed:<6.2f} ms")

    print("=" * 90)


if __name__ == "__main__":
    run_spo_multihop_benchmark()
