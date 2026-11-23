"""
stress_spo_multihop.py
Stress-tests Multi-Hop Relational Knowledge Retrieval:
- 3-hop composition: e1 -> r1 -> e2 -> r2 -> e3 -> r3 -> e4
- No target leakage: target e4 is evaluated contrastively from query (S, P).
- Evaluation on held-out test chains.
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
from benchmark_spo_multihop import PairwiseChainedBaseline, Arity3SimplexQueryModel

torch.manual_seed(1337)
random.seed(1337)


def run_stress_test():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 96)
    print(f"STRESS TEST: 3-Hop Knowledge Traversal (NO Target Leakage, Held-out Test) on {device}")
    print("=" * 96)

    d_model = 64
    num_entities = 256
    num_relations = 32
    num_train = 64
    num_test = 256
    num_steps = 60

    entity_embeds = F.normalize(torch.randn(num_entities, d_model, device=device), dim=-1)
    relation_embeds = F.normalize(torch.randn(num_relations, d_model, device=device), dim=-1)

    def transition(e, r):
        return (e * (r + 1) + (r + 3)) % num_entities

    def sample_deterministic_3hop_chains(n, existing_keys=None):
        chains = []
        keys = set() if existing_keys is None else set(existing_keys)
        attempts = 0
        while len(chains) < n and attempts < n * 100:
            attempts += 1
            e1 = random.randint(0, num_entities - 1)
            r1 = random.randint(0, num_relations - 1)
            r2 = random.randint(0, num_relations - 1)
            r3 = random.randint(0, num_relations - 1)
            key = (e1, r1, r2, r3)
            if key in keys:
                continue
            keys.add(key)
            e2 = transition(e1, r1)
            e3 = transition(e2, r2)
            e4 = transition(e3, r3)
            chains.append((e1, r1, e2, r2, e3, r3, e4))
        return chains, keys

    train_chains, train_keys = sample_deterministic_3hop_chains(num_train)
    test_chains, _ = sample_deterministic_3hop_chains(num_test, existing_keys=train_keys)

    def to_tensors(ch):
        S = torch.stack([entity_embeds[c[0]] for c in ch]).unsqueeze(1)
        # Ordered composition (r1 + 0.5*r2 + 0.25*r3)
        P = torch.stack([relation_embeds[c[1]] + 0.5 * relation_embeds[c[3]] + 0.25 * relation_embeds[c[5]] for c in ch]).unsqueeze(1)
        targets = torch.tensor([c[6] for c in ch], device=device, dtype=torch.long)
        return S, P, targets

    S_train, P_train, y_train = to_tensors(train_chains)
    S_test, P_test, y_test = to_tensors(test_chains)

    models = {
        "Pairwise Attention (Arity-2)": PairwiseChainedBaseline(d_model).to(device),
        "Simplex Hyperface (Arity-3)": Arity3SimplexQueryModel(d_model, rank=32).to(device)
    }

    print(f"{'Model Architecture':<32} | {'Train Loss':<12} | {'Train Acc %':<12} | {'Held-Out Acc %':<15} | {'Latency':<9}")
    print("-" * 96)

    for name, model in models.items():
        optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
        final_loss = 0.0

        t0 = time.perf_counter()
        for step in range(num_steps):
            optimizer.zero_grad()
            out = model(S_train, P_train).squeeze(1)
            scores = torch.matmul(out, entity_embeds.T)
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

            test_out = model(S_test, P_test).squeeze(1)
            test_scores = torch.matmul(test_out, entity_embeds.T)
            test_preds = torch.argmax(test_scores, dim=-1)
            test_acc = (test_preds == y_test).float().mean().item() * 100.0

        print(f"{name:<32} | {final_loss:<12.4f} | {train_acc:<12.1f} | {test_acc:<15.1f} | {elapsed:<6.2f} ms")

    print("=" * 96)


if __name__ == "__main__":
    run_stress_test()
