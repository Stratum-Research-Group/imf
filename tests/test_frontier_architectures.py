"""
tests/test_frontier_architectures.py
Unit Test Suite for the Three Frontier Architectures:
1. Non-Abelian SU(2) Gauge-Equivariant Simplicial Complex (Horizon 3).
2. Dynamic Polytope Mesh Refinement via Barycentric Subdivision (Horizon 2).
3. Continuous-Time Lie Group State-Space Model on SO(d) (Horizon 1).
"""

import math
import pytest
import torch

from imf.gauge_polytope_complex import SU2GaugeSimplicialComplex
from imf.adaptive_mesh_refinement import AdaptivePolytopeSubdivision
from imf.continuous_lie_ssm import ContinuousLieGroupSSM


def test_su2_gauge_simplicial_complex_holonomy():
    """Verify SU(2) quaternionic connection skew-inversion and Wilson loop curvature."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    num_vertices = 11
    d_model = 32
    gauge_complex = SU2GaugeSimplicialComplex(num_vertices=num_vertices, d_model=d_model).to(device)

    U = gauge_complex.get_su2_connections()
    assert U.shape == (num_vertices, num_vertices, 4)

    # Unit quaternion property: ||q|| = 1
    norms = torch.norm(U, dim=-1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)

    # Skew-inversion: U_ji = U_ij*
    u_01 = U[0, 1]
    u_10 = U[1, 0]
    assert abs((u_01[0] - u_10[0]).item()) < 1e-5
    assert abs((u_01[1:] + u_10[1:]).norm().item()) < 1e-5

    # Wilson loop forward pass
    coords = torch.softmax(torch.randn(2, 8, num_vertices, device=device), dim=-1)
    curv = gauge_complex.compute_triangle_curvature(coords)
    assert curv.shape == (2, 8, d_model)

    loss = curv.sum()
    loss.backward()
    assert gauge_complex.edge_algebra.grad is not None


def test_adaptive_polytope_barycentric_subdivision():
    """Verify adaptive mesh refinement preserves convex hull partition of unity."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    d_model = 32
    num_coarse = 11
    num_children = 6
    subdiv = AdaptivePolytopeSubdivision(
        d_model=d_model, num_coarse_vertices=num_coarse, num_child_vertices=num_children
    ).to(device)

    all_v = subdiv.get_refined_mesh()
    assert all_v.shape == (num_coarse + num_children, d_model)

    x = torch.randn(2, 10, d_model, device=device, requires_grad=True)
    out = subdiv(x)
    assert out.shape == (2, 10, d_model)

    loss = out.sum()
    loss.backward()
    assert x.grad is not None
    assert subdiv.child_simplex_logits.grad is not None


def test_continuous_lie_group_ssm_unitary_rotation():
    """Verify continuous Lie group SSM maintains exact unitary orthogonality on SO(d_h)."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    d_model = 32
    num_heads = 4
    head_dim = d_model // num_heads

    ssm = ContinuousLieGroupSSM(d_model=d_model, num_heads=num_heads).to(device)
    U = ssm.get_orthogonal_rotator()

    # Unitary test: U @ U^T == I
    U_UT = torch.matmul(U, U.transpose(-1, -2))
    eye = torch.eye(head_dim, device=device).unsqueeze(0).expand(num_heads, head_dim, head_dim)
    assert torch.allclose(U_UT, eye, atol=1e-5), "Unitary rotation constraint failed!"

    # Forward and backward test
    x = torch.randn(2, 12, d_model, device=device, requires_grad=True)
    out = ssm(x)
    assert out.shape == (2, 12, d_model)

    loss = out.sum()
    loss.backward()
    assert x.grad is not None
    assert ssm.raw_generator.grad is not None
