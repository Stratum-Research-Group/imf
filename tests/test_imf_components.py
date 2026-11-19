"""
Unit and integration tests for IMF (Interaction Model Foundations).
Validates:
  1. Polytope Connector coordinate extraction & simplex properties.
  2. Multi-token interaction over higher-arity simplex hyperfaces (Arity-3 and Arity-4).
  3. FusedSAVGLayer forward, backward autograd gradient flow, and shape contracts.
"""

import pytest
import torch
from polytope_connector import ConfigurablePolytopeConnector
from higher_arity_simplex import HigherAritySimplexBinding
from triton_savg_kernel import FusedSAVGLayer, pytorch_reference_savg_scan


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
    assert torch.allclose(coords.sum(dim=-1), torch.ones(4, 16), atol=1e-5)


@pytest.mark.parametrize("preset", ["tetrahedron", "decayotton_orthoplex"])
def test_polytope_grid_modulation(preset):
    d_model = 32
    connector = ConfigurablePolytopeConnector(d_model=d_model, preset=preset)
    x = torch.randn(2, 8, d_model)
    grid_mod = connector.compute_grid_modulation(x)
    assert grid_mod.shape == (2, 8, 1, 1)
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


def test_fused_savg_layer_autograd_and_shapes():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    d_model = 32
    layer = FusedSAVGLayer(d_model=d_model, preset="decayotton_orthoplex").to(device)
    x = torch.randn(2, 16, d_model, device=device, requires_grad=True)

    out = layer(x)
    assert out.shape == (2, 16, d_model)
    assert not torch.isnan(out).any()

    # Test backward gradient flow
    loss = out.sum()
    loss.backward()
    assert x.grad is not None
    for name, p in layer.named_parameters():
        assert p.grad is not None, f"Parameter {name} has no gradient!"


@pytest.mark.parametrize("dtype", [torch.float16, torch.bfloat16, torch.float32])
def test_fused_savg_layer_dtypes(dtype):
    device = torch.device("cpu")
    d_model = 16
    layer = FusedSAVGLayer(d_model=d_model, preset="tetrahedron").to(device=device, dtype=dtype)
    x = torch.randn(2, 4, d_model, device=device, dtype=dtype, requires_grad=True)

    out = layer(x, use_triton=False)
    assert out.shape == (2, 4, d_model)
    assert out.dtype == dtype
    assert not torch.isnan(out).any()

    loss = out.sum()
    loss.backward()
    assert x.grad is not None
    assert x.grad.dtype == dtype

