"""
benchmark_polytopes.py
Compares the performance of different polytope connector configurations:
- 3D Tetrahedron (Baseline 4 corners)
- 9D Enneazetton Simplex (10 corners) vs Enneazetton Orthoplex (18 corners)
- 10D Decayotton Simplex (11 corners) vs Decayotton Orthoplex (20 corners)
- 11D Hendecaxennon Simplex (12 corners) vs Hendecaxennon Orthoplex (22 corners)
On Multi-Query Associative Recall (MQAR) task on CUDA.
"""

import sys
import os
import time
import torch
import torch.nn as nn
import torch.nn.functional as F

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TENSORSAT_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "TensorSAT"))
if os.path.exists(TENSORSAT_PATH) and TENSORSAT_PATH not in sys.path:
    sys.path.insert(0, TENSORSAT_PATH)

try:
    from tensorsat.hybrid import HybridSingletAttention
    HAS_TENSORSAT = True
except ImportError:
    HAS_TENSORSAT = False

from polytope_connector import ConfigurablePolytopeConnector
from benchmark_mqar import generate_mqar_batch, MQARModelWrapper

class PolytopeAugmentedHybrid(nn.Module):
    def __init__(self, embed_dim: int, num_heads: int, preset: str):
        super().__init__()
        self.base_hybrid = HybridSingletAttention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            window_size=64,
            num_singlets=16,
            use_triton=False,
            chunk_size=128
        )
        self.connector = ConfigurablePolytopeConnector(d_model=embed_dim, preset=preset)
        self.out_gate = nn.Parameter(torch.zeros(1))

    def forward(self, x: torch.Tensor):
        B, N, D = x.shape
        out_hybrid, _ = self.base_hybrid(x)

        grid_mod = self.connector.compute_grid_modulation(x)

        U = self.base_hybrid.q_proj(x)
        V = self.base_hybrid.k_proj(x)

        outer = torch.matmul(U.unsqueeze(-1), V.unsqueeze(-2))
        A_inc = 0.5 * (outer - outer.transpose(-1, -2)) * grid_mod
        A_state = torch.cumsum(A_inc, dim=1)

        readout_A = torch.matmul(A_state, U.unsqueeze(-1)).squeeze(-1)
        return out_hybrid + torch.tanh(self.out_gate) * readout_A


def run_polytope_comparison():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 90)
    print(f"HIGHER-DIMENSIONAL POLYTOPE CONNECTOR BENCHMARK on {device}")
    print("=" * 90)

    vocab_size = 256
    embed_dim = 64
    num_heads = 4
    batch_size = 16
    seq_len = 512
    num_queries = 4
    num_pairs = 16
    train_steps = 100

    x_emb, targets, q_indices = generate_mqar_batch(
        batch_size=batch_size,
        seq_len=seq_len,
        num_pairs=num_pairs,
        num_queries=num_queries,
        vocab_size=vocab_size,
        embed_dim=embed_dim,
        device=device
    )

    presets_to_test = [
        ("Tetrahedron (3D)", "tetrahedron"),
        ("Enneazetton Simplex (9D)", "enneazetton_simplex"),
        ("Enneazetton Orthoplex (9D)", "enneazetton_orthoplex"),
        ("Decayotton Simplex (10D)", "decayotton_simplex"),
        ("Decayotton Orthoplex (10D)", "decayotton_orthoplex"),
        ("Hendecaxennon Simplex (11D)", "hendecaxennon_simplex"),
        ("Hendecaxennon Orthoplex (11D)", "hendecaxennon_orthoplex"),
    ]

    print(f"{'Polytope Configuration':<32} | {'Vertices':<9} | {'Grid Slots':<11} | {'Final Loss':<11} | {'Accuracy %':<10} | {'Latency':<9}")
    print("-" * 90)

    for label, preset in presets_to_test:
        model = MQARModelWrapper(
            PolytopeAugmentedHybrid(embed_dim, num_heads, preset),
            embed_dim,
            vocab_size
        ).to(device)

        connector_info = model.attn.connector
        verts = connector_info.num_vertices
        grid_slots = f"{verts}x{verts}"

        optimizer = torch.optim.Adam(model.parameters(), lr=0.008)

        # Warmup
        _ = model(x_emb)
        if device.type == "cuda":
            torch.cuda.synchronize()

        t0 = time.perf_counter()
        final_loss = 0.0
        for step in range(train_steps):
            optimizer.zero_grad()
            logits = model(x_emb)
            query_logits = logits[:, q_indices, :]
            loss = F.cross_entropy(query_logits.reshape(-1, vocab_size), targets.reshape(-1))
            loss.backward()
            optimizer.step()
            final_loss = loss.item()

        if device.type == "cuda":
            torch.cuda.synchronize()
        elapsed = (time.perf_counter() - t0) * 1000.0 / train_steps

        with torch.no_grad():
            pred = torch.argmax(query_logits, dim=-1)
            acc = (pred == targets).float().mean().item() * 100.0

        print(f"{label:<32} | {verts:<9} | {grid_slots:<11} | {final_loss:<11.4f} | {acc:<10.1f} | {elapsed:<6.1f} ms")


if __name__ == "__main__":
    run_polytope_comparison()
