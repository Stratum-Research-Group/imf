"""
tests/test_polydokon_router.py
Unit tests verifying the 13D Polydokon Router:
1. Exact regular 14-simplex geometry (pairwise inner product = -1/13).
2. Forward routing top-k indices and weights correctness.
3. Full autograd backprop gradient flow.
"""

import pytest
import math
import torch
from imf.polydokon_router import Polydokon13DRouter


def test_polydokon_simplex_geometry():
    router = Polydokon13DRouter(d_model=128, num_experts=14, top_k=2)
    geom_check = router.verify_simplex_geometry()

    print("\n[✓] 13D Polydokon Geometry Verification:")
    print(f"    Expected Pairwise Inner Product: {geom_check['expected_inner_product']:.6f} (-1/13)")
    print(f"    Max Deviation Across 14 Vertices: {geom_check['max_geometric_error']:.2e}")

    assert geom_check["is_regular_simplex"], f"Simplex deviation {geom_check['max_geometric_error']} exceeded 1e-5"
    print("    [PASS] Tetradecadokon 14-simplex is geometrically regular and equidistant.")


def test_polydokon_forward_and_backward():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    router = Polydokon13DRouter(d_model=256, num_experts=14, top_k=2).to(device)

    x = torch.randn(2, 8, 256, device=device, requires_grad=True)
    weights, indices = router(x)

    assert weights.shape == (2, 8, 2)
    assert indices.shape == (2, 8, 2)
    assert (indices >= 0).all() and (indices < 14).all()
    # Weights should sum to 1.0 across top-k
    assert torch.allclose(weights.sum(dim=-1), torch.ones(2, 8, device=device), atol=1e-5)

    loss = weights.sum()
    loss.backward()

    assert x.grad is not None
    assert router.proj_to_polydokon.weight.grad is not None
    print("[✓] 13D Polydokon Router forward pass and gradient flow verified.")
