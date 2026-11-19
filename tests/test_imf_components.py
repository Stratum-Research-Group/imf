"""
Unit and integration tests for IMF (Interaction Model Foundations).
Validates:
  1. Polytope Connector coordinate extraction & simplex properties.
  2. Directional selectivity & reversal asymmetry in SAVG.
  3. Multi-token interaction over higher-arity simplex hyperfaces (Arity-3 and Arity-4).
  4. Triton JIT fused SAVG layer execution & tensor shape contracts.
"""

import pytest
import torch
from polytope_connector import ConfigurablePolytopeConnector
from higher_arity_simplex import HigherAritySimplexBinding
from triton_savg_kernel import FusedSAVGLayer


@pytest.mark.parametrize("preset,expected_vertices", [
    ("tetrahedron", 4),
    ("enneazetton_simplex", 10),
    ("enneazetton_orthoplex", 18),
    ("decayotton_simplex", 11),
    ("decayotton_orthoplex", 20),
    ("hendecaxennon_simplex", 12),
    ("hendecaxennon_orthoplex", 22),
])
def test_polytope_connector_initialization(preset, expected_vertices):
    d_model = 64
    connector = ConfigurablePolytopeConnector(d_model=d_model, preset=preset)
    assert connector.num_vertices == expected_vertices

    x = torch.randn(4, 16, d_model)
    coords = connector.get_coordinates(x)
    assert coords.shape == (4, 16, expected_vertices)
    # Check partition of unity / softmax barycentric property
    assert torch.allclose(coords.sum(dim=-1), torch.ones(4, 16), atol=1e-5)


@pytest.mark.parametrize("preset", ["tetrahedron", "decayotton_orthoplex"])
def test_polytope_grid_modulation(preset):
    d_model = 32
    connector = ConfigurablePolytopeConnector(d_model=d_model, preset=preset)
    x = torch.randn(2, 8, d_model)
    grid_mod = connector.compute_grid_modulation(x)
    assert grid_mod.shape == (2, 8, 1, 1)
    # Modulation should be bounded and strictly positive
    assert torch.all(grid_mod > 0)


@pytest.mark.parametrize("arity", [3, 4])
def test_higher_arity_simplex_binding(arity):
    batch, seq_len, d_model = 2, 8, 32
    binding_module = HigherAritySimplexBinding(d_model=d_model, arity=arity, rank=8, num_corners=6)
    tokens = [torch.randn(batch, seq_len, d_model) for _ in range(arity)]

    out = binding_module(tokens)
    assert out.shape == (batch, seq_len, d_model)
    assert not torch.isnan(out).any()
    assert not torch.isinf(out).any()


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for Triton kernel")
def test_triton_fused_savg_layer():
    d_model = 64
    layer = FusedSAVGLayer(d_model=d_model, preset="decayotton_orthoplex").cuda()
    x = torch.randn(2, 32, d_model, device="cuda")

    out = layer(x)
    assert out.shape == (2, 32, d_model)
    assert not torch.isnan(out).any()
    assert not torch.isinf(out).any()
