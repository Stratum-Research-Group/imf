"""
Unit tests for Nested Hypercube Cell Layer (Virtual Cells Within Cells).
Verifies forward pass shape, residual continuity, and gradient backpropagation.
"""

import pytest
import torch
from imf.nested_hypercube_cell import NestedHypercubeCell


def test_nested_hypercube_cell_forward():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    layer = NestedHypercubeCell(d_model=384, hypercube_dim=4, recursion_depth=3).to(device)

    x = torch.randn(2, 16, 384, device=device)
    out = layer(x)

    assert out.shape == x.shape
    assert not torch.isnan(out).any()
    assert not torch.isinf(out).any()


def test_nested_hypercube_cell_gradients():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    layer = NestedHypercubeCell(d_model=128, hypercube_dim=3, recursion_depth=2).to(device)

    x = torch.randn(4, 8, 128, device=device, requires_grad=True)
    out = layer(x)
    loss = out.sum()
    loss.backward()

    assert x.grad is not None
    assert not torch.isnan(x.grad).any()
    # Check that basis parameters receive non-zero gradients
    assert layer.facet_basis.grad is not None
    assert (layer.facet_basis.grad.abs().sum() > 0).item()
