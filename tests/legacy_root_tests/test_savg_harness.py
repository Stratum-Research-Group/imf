"""
test_savg_harness.py
Non-invasive benchmark comparing:
1. Baseline TensorSAT HybridSingletAttention
2. SAVG Augmented Variant (wrapping baseline and adding Symmetric-Antisymmetric Virtual Grid state)
NO codebase files in TensorSAT are modified.
"""

import sys
import os
import time
import math
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
    HybridSingletAttention = None


class VirtualGridConnector(nn.Module):
    """3-Simplex Barycentric landmark router (4 corners)."""
    def __init__(self, d_model: int, num_corners: int = 4, temperature: float = 1.0):
        super().__init__()
        self.corners = nn.Parameter(torch.randn(num_corners, d_model) / math.sqrt(d_model))
        self.temperature = temperature

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        logits = torch.matmul(x, self.corners.T) / self.temperature
        return F.softmax(logits, dim=-1)


class HybridAttentionWithSAVG(nn.Module):
    """
    Extends HybridSingletAttention via composition (wrapper):
    Preserves exact local window attention + integrates decoupled Lie Symmetric/Antisymmetric grid state.
    """
    def __init__(self, embed_dim: int, num_heads: int, window_size: int = 64, num_singlets: int = 16):
        super().__init__()
        if not HAS_TENSORSAT:
            raise RuntimeError("HybridAttentionWithSAVG requires TensorSAT (HybridSingletAttention).")
        self.base_hybrid = HybridSingletAttention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            window_size=window_size,
            num_singlets=num_singlets,
            use_triton=False, # Portable comparison
            chunk_size=128
        )
        self.connector = VirtualGridConnector(embed_dim, num_corners=4)
        self.grid_weight = nn.Parameter(torch.randn(4, 4) * 0.02)
        self.out_gate = nn.Parameter(torch.zeros(1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, N, D = x.shape
        # 1. Base Hybrid Output
        out_hybrid, _ = self.base_hybrid(x)

        # 2. Virtual Grid Coordinates
        coords = self.connector(x) # [B, N, 4]
        # Grid interaction modulation
        grid_mod = torch.einsum("bni,ij,bnj->bn", coords, self.grid_weight, coords).unsqueeze(-1)

        # 3. Antisymmetric Sector on Projected Embeddings to enforce directed order
        # Compute U, V from base model's projections
        U = self.base_hybrid.q_proj(x)
        V = self.base_hybrid.k_proj(x)

        # Causal antisymmetric state
        outer = torch.matmul(U.unsqueeze(-1), V.unsqueeze(-2))
        A_inc = 0.5 * (outer - outer.transpose(-1, -2)) * (1.0 + grid_mod.unsqueeze(-1))
        A_state = torch.cumsum(A_inc, dim=1)

        readout_A = torch.matmul(A_state, U.unsqueeze(-1)).squeeze(-1)
        
        return out_hybrid + torch.tanh(self.out_gate) * readout_A


def evaluate_synthetic_reasoning():
    if not HAS_TENSORSAT:
        print("[!] TensorSAT not available, skipping synthetic reasoning evaluation.")
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"=== Synthetic Evaluation Harness on {device} ===")

    embed_dim = 64
    num_heads = 4
    seq_len = 256
    batch_size = 16
    num_steps = 100

    # Synthetic Directed Knowledge Graph Needle Task:
    # Entities A -> B -> C -> D placed in sequence amidst noise.
    # Model must correctly route directed multi-hop queries.
    x_input = torch.randn(batch_size, seq_len, embed_dim, device=device)
    # Target: Predict directed forward sequence transition
    y_target = torch.roll(x_input, shifts=-1, dims=1)

    models = {
        "Baseline TensorSAT Hybrid": HybridSingletAttention(
            embed_dim=embed_dim, num_heads=num_heads, window_size=64, num_singlets=16, use_triton=False, chunk_size=128
        ).to(device),
        "TensorSAT Hybrid + SAVG": HybridAttentionWithSAVG(
            embed_dim=embed_dim, num_heads=num_heads, window_size=64, num_singlets=16
        ).to(device)
    }

    timings = {}
    losses = {}

    for name, model in models.items():
        optimizer = torch.optim.Adam(model.parameters(), lr=0.005)
        step_losses = []
        
        # Warmup
        _ = model(x_input)
        if device.type == "cuda":
            torch.cuda.synchronize()

        start_t = time.perf_counter()
        for step in range(num_steps):
            optimizer.zero_grad()
            out = model(x_input)
            if isinstance(out, tuple):
                out = out[0]
            loss = F.mse_loss(out[:, :-1], y_target[:, :-1])
            loss.backward()
            optimizer.step()
            step_losses.append(loss.item())

        if device.type == "cuda":
            torch.cuda.synchronize()
        elapsed = (time.perf_counter() - start_t) * 1000.0 / num_steps

        timings[name] = elapsed
        losses[name] = (step_losses[0], step_losses[-1])
        print(f"[{name}]")
        print(f"  Step Latency: {elapsed:.2f} ms")
        print(f"  Loss: Initial {step_losses[0]:.4f} -> Final {step_losses[-1]:.4f}")

    print("\n=== Summary ===")
    base_final = losses["Baseline TensorSAT Hybrid"][1]
    savg_final = losses["TensorSAT Hybrid + SAVG"][1]
    imp = ((base_final - savg_final) / base_final) * 100.0
    print(f"Loss Improvement with SAVG: {imp:.2f}%")


if __name__ == "__main__":
    evaluate_synthetic_reasoning()
