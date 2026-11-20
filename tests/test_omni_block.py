"""
test_omni_block.py
Unit tests for IMF-OmniBlock unified architecture.
Verifies:
1. Full autograd backward pass and gradient flow through all components (SSM, Simplex Conv, SU(2) Gauge).
2. Forward shapes under batching and sequence length variations.
3. GPU execution with Triton unitary associative scan inference mode.
"""

import pytest
import torch
from imf.omni_block import IMFOmniBlock


def test_omni_block_autograd_and_shapes():
    torch.manual_seed(42)
    B, T, D = 2, 16, 64
    num_heads = 4
    polytope_dim = 6  # 6-simplex -> 7 vertices
    conv_rank = 32
    conv_window = 4

    block = IMFOmniBlock(
        d_model=D,
        num_heads=num_heads,
        polytope_dim=polytope_dim,
        conv_rank=conv_rank,
        conv_window=conv_window,
        use_triton_ssm=False,
    )

    x = torch.randn(B, T, D, requires_grad=True)
    out = block(x)

    assert out.shape == (B, T, D), f"Expected shape {(B, T, D)}, got {out.shape}"
    assert not torch.isnan(out).any(), "Output contains NaN"

    loss = out.sum()
    loss.backward()

    assert x.grad is not None, "Gradient did not flow back to input x"
    assert not torch.isnan(x.grad).any(), "Input gradient contains NaN"
    assert block.ssm.raw_generator.grad is not None, "SSM raw generator did not receive gradient"
    assert block.simplex_conv.core_weight.grad is not None, "Simplex convolution did not receive gradient"
    assert block.gauge_complex.edge_algebra.grad is not None, "Gauge complex did not receive gradient"


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA required for Triton kernel test")
def test_omni_block_triton_cuda_inference():
    torch.manual_seed(42)
    B, T, D = 2, 32, 128
    num_heads = 4
    polytope_dim = 10  # 10-simplex -> 11 vertices

    block = IMFOmniBlock(
        d_model=D,
        num_heads=num_heads,
        polytope_dim=polytope_dim,
        conv_rank=64,
        conv_window=8,
        use_triton_ssm=True,
    ).cuda()

    x = torch.randn(B, T, D, device="cuda")
    with torch.no_grad():
        out = block(x)

    assert out.shape == (B, T, D)
    assert not torch.isnan(out).any()
