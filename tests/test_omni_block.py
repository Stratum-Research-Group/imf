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
from imf.omni_block import IMFOmniBlock, LieAlgebraicRollingKVCache


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


def test_omni_block_lie_algebraic_rolling_kv_cache():
    torch.manual_seed(42)
    B, D = 2, 64
    num_heads = 4
    head_dim = D // num_heads

    block = IMFOmniBlock(
        d_model=D,
        num_heads=num_heads,
        polytope_dim=4,
        conv_rank=16,
        conv_window=4,
        use_triton_ssm=False,
    )
    block.eval()

    cache = block.create_rolling_cache(batch_size=B)
    mem_initial = cache.get_memory_bytes()
    expected_mem = B * num_heads * (head_dim ** 2) * 4 # float32 = 4 bytes
    assert mem_initial == expected_mem

    # Step through 50 autoregressive steps
    for step in range(50):
        x_t = torch.randn(B, 1, D)
        out_t = block.step_autoregressive(x_t, cache)
        assert out_t.shape == (B, 1, D)
        assert not torch.isnan(out_t).any()
        # Verify strictly O(1) constant memory (bytes do not grow)
        assert cache.get_memory_bytes() == mem_initial

    assert cache.step_count == 50

