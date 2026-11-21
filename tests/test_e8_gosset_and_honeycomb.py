"""
tests/test_e8_gosset_and_honeycomb.py
Unit tests verifying:
1. Gosset 4_21 / E8 Polytope Router (240 roots, optimal kissing geometry).
2. Hypercubic Honeycomb Tiler (Z^D infinite discrete tiling, 2*D facet neighbors).
"""

import pytest
import torch
from imf.e8_gosset_router import E8GossetRouter, generate_e8_roots
from imf.hypercubic_honeycomb_tiler import HypercubicHoneycombTiler


def test_e8_roots_geometry():
    """Verify exact 240 root vectors and kissing number geometry of Gosset 4_21 polytope."""
    roots = generate_e8_roots()
    assert roots.shape == (240, 8)
    
    # Check that all vectors are on the unit sphere S^7
    norms = torch.linalg.norm(roots, dim=-1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)
    
    # Check mutual inner products between E8 roots:
    # In E8, distinct roots have dot products in {1.0, 0.5, 0.0, -0.5, -1.0}
    gram = torch.matmul(roots, roots.t())
    for val in gram.view(-1).unique():
        item = val.item()
        closest_allowed = min([1.0, 0.5, 0.0, -0.5, -1.0], key=lambda x: abs(x - item))
        assert abs(item - closest_allowed) < 1e-4, f"Invalid E8 dot product: {item}"


def test_e8_gosset_router_forward():
    """Verify E8 Gosset router forward routing and expert clustering."""
    torch.manual_seed(42)
    B, S, D = 2, 4, 64
    num_experts = 16
    top_k = 2
    
    router = E8GossetRouter(d_model=D, num_experts=num_experts, top_k=top_k)
    x = torch.randn(B, S, D)
    weights, indices, logits = router(x)
    
    assert weights.shape == (B, S, top_k)
    assert indices.shape == (B, S, top_k)
    assert logits.shape == (B, S, 240)
    
    # Weights must sum to 1 across top_k
    sum_w = weights.sum(dim=-1)
    assert torch.allclose(sum_w, torch.ones_like(sum_w), atol=1e-5)
    assert (indices >= 0).all() and (indices < num_experts).all()


def test_hypercubic_honeycomb_tiling():
    """Verify Z^D infinite honeycomb tiling and facet neighbor offsets."""
    torch.manual_seed(42)
    B, S, D = 2, 4, 32
    dim_space = 6
    cell_size = 2.0
    
    tiler = HypercubicHoneycombTiler(
        d_model=D,
        dim_space=dim_space,
        cell_size=cell_size,
        hash_table_size=1024,
    )
    
    x = torch.randn(B, S, D)
    coords, hashes, offsets = tiler(x)
    
    assert coords.shape == (B, S, dim_space)
    assert hashes.shape == (B, S)
    assert offsets.shape == (B, S, dim_space)
    
    # Fractional offsets must lie strictly in [0, 1)
    assert (offsets >= 0.0).all() and (offsets < 1.0).all()
    assert (hashes >= 0).all() and (hashes < 1024).all()
    
    # Verify 2*D facet neighbors
    neighbors = tiler.get_facet_neighbors(coords)
    assert neighbors.shape == (B, S, 2 * dim_space, dim_space)
    
    # Each neighbor must differ from center by exactly 1 in one coordinate
    diff = (neighbors - coords.unsqueeze(-2)).abs()
    # Exactly one coordinate differs by 1, others 0 -> sum of diff along D is 1
    assert (diff.sum(dim=-1) == 1).all()
