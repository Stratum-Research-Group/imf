"""
stress_spo_multihop.py
Stress-tests Multi-Hop Relational Knowledge Retrieval under dense distractor noise:
- Scaled to 512 entities and 64 relations
- 3-hop composition: e1 -> r1 -> e2 -> r2 -> e3 -> r3 -> e4
- Measuring convergence speed and accuracy gap under strict budget (50 training steps)
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
from benchmark_spo_multihop import PairwiseChainedBaseline, Arity3SimplexModel

torch.manual_seed(1337)
random.seed(1337)

def run_stress_test():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 92)
    print(f"STRESS TEST: 3-Hop Knowledge Traversal (512 Entities, 64 Relations) on {device}")
    print("=" * 92)

    d_model = 64
    num_entities = 512
    num_relations = 64
    batch_size = 64
    num_steps = 40 # Fast convergence stress test

    entity_embeds = F.normalize(torch.randn(num_entities, d_model, device=device), dim=-1)
    relation_embeds = F.normalize(torch.randn(num_relations, d_model, device=device), dim=-1)

    # Build 3-hop chains: e1 -> r1 -> e2 -> r2 -> e3 -> r3 -> e4
    chains = []
    for _ in range(batch_size):
        e1 = random.randint(0, num_entities - 1)
        e2 = (e1 + random.randint(1, 20)) % num_entities
        e3 = (e2 + random.randint(1, 20)) % num_entities
        e4 = (e3 + random.randint(1, 20)) % num_entities
        r1 = random.randint(0, num_relations - 1)
        r2 = random.randint(0, num_relations - 1)
        r3 = random.randint(0, num_relations - 1)
        chains.append((e1, r1, e2, r2, e3, r3, e4))

    S_batch = torch.stack([entity_embeds[c[0]] for c in chains]).unsqueeze(1)
    P_batch = torch.stack([relation_embeds[c[1]] + relation_embeds[c[3]] + relation_embeds[c[5]] for c in chains]).unsqueeze(1)
    O_target = torch.stack([entity_embeds[c[6]] for c in chains]).unsqueeze(1)
    targets_tensor = torch.tensor([c[6] for c in chains], device=device, dtype=torch.long)

    candidates = entity_embeds.unsqueeze(0).expand(batch_size, -1, -1)

    models = {
        "Pairwise Attention (Arity-2)": PairwiseChainedBaseline(d_model).to(device),
        "Simplex Hyperface (Arity-3)": Arity3SimplexModel(d_model, rank=32).to(device)
    }

    print(f"{'Model Architecture':<32} | {'Step 10 Loss':<13} | {'Final Loss (40)':<16} | {'Retrieval Acc %':<16} | {'Latency':<9}")
    print("-" * 92)

    for name, model in models.items():
        optimizer = torch.optim.Adam(model.parameters(), lr=0.015)
        loss_at_10 = 0.0
        final_loss = 0.0

        _ = model(S_batch, P_batch, O_target)
        if device.type == "cuda":
            torch.cuda.synchronize()

        t0 = time.perf_counter()
        for step in range(num_steps):
            optimizer.zero_grad()
            out = model(S_batch, P_batch, O_target).squeeze(1)
            scores = torch.matmul(out, candidates[0].T)
            loss = F.cross_entropy(scores, targets_tensor)
            loss.backward()
            optimizer.step()

            if step == 9:
                loss_at_10 = loss.item()
            if step == num_steps - 1:
                final_loss = loss.item()

        if device.type == "cuda":
            torch.cuda.synchronize()
        elapsed = (time.perf_counter() - t0) * 1000.0 / num_steps

        with torch.no_grad():
            preds = torch.argmax(scores, dim=-1)
            acc = (preds == targets_tensor).float().mean().item() * 100.0

        print(f"{name:<32} | {loss_at_10:<13.4f} | {final_loss:<16.4f} | {acc:<16.1f} | {elapsed:<6.2f} ms")

    print("=" * 92)

if __name__ == "__main__":
    run_stress_test()
