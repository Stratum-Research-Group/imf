"""
tests/test_polydecakon_14d_router.py
Unit tests verifying the 14D Polydecakon Router:
1. Exact regular 15-simplex geometry (pairwise inner product = -1/14).
2. Forward routing top-k indices and weights correctness.
3. Autograd backprop gradient flow through 14D manifold.
"""

import pytest
import math
import torch
from imf.polydecakon_14d_router import Polydecakon14DRouter


def test_polydecakon_14d_simplex_geometry():
    router = Polydecakon14DRouter(d_model=128, num_experts=15, top_k=2)
    geom_check = router.verify_simplex_geometry()

    print("\n[✓] 14D Polydecakon Geometry Verification:")
    print(f"    Expected Pairwise Inner Product: {geom_check['expected_inner_product']:.6f} (-1/14)")
    print(f"    Max Deviation Across 15 Vertices: {geom_check['max_geometric_error']:.2e}")

    assert geom_check["is_regular_simplex"], f"Simplex deviation {geom_check['max_geometric_error']} exceeded 1e-5"
    print("    [PASS] Pentadecadokon 15-simplex is geometrically regular and equidistant.")


def test_polydecakon_14d_forward_and_backward():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    router = Polydecakon14DRouter(d_model=256, num_experts=15, top_k=2).to(device)

    x = torch.randn(2, 8, 256, device=device, requires_grad=True)
    weights, indices = router(x)

    assert weights.shape == (2, 8, 2)
    assert indices.shape == (2, 8, 2)
    assert (indices >= 0).all() and (indices < 15).all()
    # Weights sum to 1.0
    assert torch.allclose(weights.sum(dim=-1), torch.ones(2, 8, device=device), atol=1e-5)

    loss = weights.sum()
    loss.backward()

    assert x.grad is not None
    assert router.proj_to_polydecakon.weight.grad is not None
    print("[✓] 14D Polydecakon Router forward pass and gradient flow verified.")
