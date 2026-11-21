"""
tests/test_matryoshka_cross_polytope_router.py
Unit tests verifying the Russian-Doll (Matryoshka) Nested Cross-Polytope Router.
"""

import pytest
import torch
import torch.nn.functional as F
from imf.matryoshka_cross_polytope_router import MatryoshkaCrossPolytopeRouter


def test_matryoshka_cross_polytope_geometry():
    """Verify polar vertex orthogonality and dual pair properties in each doll layer."""
    torch.manual_seed(42)
    d_model = 64
    dim_polytope = 4  # 4D 16-cell (cross-polytope)
    nesting_depth = 3
    
    router = MatryoshkaCrossPolytopeRouter(
        d_model=d_model,
        dim_polytope=dim_polytope,
        nesting_depth=nesting_depth,
    )
    
    # Check virtual capacity: (2^4)^3 = 16^3 = 4,096 chambers
    assert router.virtual_chamber_capacity == 4096
    assert router.total_polar_vertices == 3 * (2 * 4) == 24
    
    # Check level 0 basis geometry: pairs (2*i, 2*i+1) must be exact antipodal vectors (-1 dot product)
    proj = router.level_projections[0]
    norm_proj = F.normalize(proj, p=2, dim=-1)
    
    for i in range(dim_polytope):
        v_pos = norm_proj[2 * i]
        v_neg = norm_proj[2 * i + 1]
        dot_antipodal = torch.dot(v_pos, v_neg).item()
        assert abs(dot_antipodal - (-1.0)) < 1e-5, f"Antipodal pair failed: {dot_antipodal}"
        
        # Check orthogonality with other axes: i != j
        for j in range(i + 1, dim_polytope):
            v_other = norm_proj[2 * j]
            dot_ortho = torch.dot(v_pos, v_other).item()
            assert abs(dot_ortho) < 1e-5, f"Orthogonality between axes failed: {dot_ortho}"


def test_matryoshka_continual_hierarchical_routing():
    """Verify recursive forward pass down the nested Russian doll chambers."""
    torch.manual_seed(42)
    B, S, D = 2, 8, 128
    dim_polytope = 6  # 6D Hexacross (12 vertices, 64 hypercube orthant facets)
    depth = 4        # 4 nesting layers -> (2^6)^4 = 16,777,216 virtual chambers!
    
    router = MatryoshkaCrossPolytopeRouter(
        d_model=D,
        dim_polytope=dim_polytope,
        nesting_depth=depth,
    )
    
    # 64^4 = 16,777,216 virtual chambers
    assert router.virtual_chamber_capacity == 16777216
    # Only 4 * 12 = 48 polar vertices stored physically
    assert router.total_polar_vertices == 48
    
    x = torch.randn(B, S, D)
    weights, indices, affinities = router(x)
    
    assert weights.shape == (B, S)
    assert indices.shape == (B, S)
    assert len(affinities) == depth
    
    # All weights must be in valid probability interval (0, 1]
    assert (weights > 0.0).all()
    assert (weights <= 1.0).all()
    
    # Check that indices span across the hierarchical coordinate tree
    # Max possible index: (2*D)^K - 1 = 12^4 - 1 = 20,735
    max_idx = (2 * dim_polytope) ** depth - 1
    assert (indices >= 0).all()
    assert (indices <= max_idx).all()


def test_matryoshka_gradient_propagation():
    """Verify backpropagation through all nested Russian-doll shells."""
    torch.manual_seed(42)
    router = MatryoshkaCrossPolytopeRouter(
        d_model=32,
        dim_polytope=3,  # 3D Octahedron (6 vertices, 8 facets)
        nesting_depth=3, # 3 layers -> 8^3 = 512 virtual chambers
    )
    
    x = torch.randn(4, 32, requires_grad=True)
    weights, indices, _ = router(x)
    
    loss = weights.sum()
    loss.backward()
    
    assert x.grad is not None
    assert torch.isfinite(x.grad).all()
    
    # Shell scales should receive gradient
    assert router.shell_scales.grad is not None
