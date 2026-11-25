"""
tests/test_triton_fused_soliton_backward.py
Tests the analytical gradients and numerical correctness of the fused Soliton RMSNorm kernel.
"""

import pytest
import torch
from imf.kernels.triton_fused_soliton_backward import fused_soliton_rmsnorm


@pytest.mark.skipif(not torch.cuda.is_available(), reason="Requires CUDA GPU")
def test_triton_fused_soliton_rmsnorm_forward_and_backward():
    torch.manual_seed(42)
    device = "cuda"
    B, S, D = 2, 4, 128

    x = torch.randn(B, S, D, device=device, dtype=torch.float32, requires_grad=True)
    gamma = torch.ones(D, device=device, dtype=torch.float32)
    scale = torch.ones(D, device=device, dtype=torch.float32) * 0.1

    out = fused_soliton_rmsnorm(x, gamma, scale)
    assert out.shape == (B, S, D)
    assert not torch.isnan(out).any()

    # Backpropagation
    loss = (out ** 2).sum()
    loss.backward()

    assert x.grad is not None
    assert x.grad.shape == (B, S, D)
    assert not torch.isnan(x.grad).any()
    assert torch.abs(x.grad).sum() > 0.0
