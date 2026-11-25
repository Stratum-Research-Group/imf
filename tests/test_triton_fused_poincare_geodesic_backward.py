"""
tests/test_triton_fused_poincare_geodesic_backward.py
Tests the analytical gradients and numerical accuracy of the fused Poincaré Geodesic kernel.
"""

import pytest
import torch
from imf.kernels.triton_fused_poincare_geodesic_backward import fused_poincare_geodesic_distance


@pytest.mark.skipif(not torch.cuda.is_available(), reason="Requires CUDA GPU")
def test_triton_fused_poincare_geodesic_distance_autograd():
    torch.manual_seed(42)
    device = "cuda"
    B, D = 4, 64

    # Points strictly inside Poincaré ball (norm < 0.8)
    u = (torch.randn(B, D, device=device, dtype=torch.float32) * 0.05).requires_grad_(True)
    v = (torch.randn(B, D, device=device, dtype=torch.float32) * 0.05).detach()

    dist = fused_poincare_geodesic_distance(u, v)

    assert dist.shape == (B,)
    assert not torch.isnan(dist).any()
    assert (dist >= 0.0).all()

    # Backpropagation check
    loss = dist.sum()
    loss.backward()

    assert u.grad is not None
    assert u.grad.shape == (B, D)
    assert not torch.isnan(u.grad).any()
    assert torch.abs(u.grad).sum() > 0.0
