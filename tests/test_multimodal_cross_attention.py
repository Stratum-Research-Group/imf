"""
tests/test_multimodal_cross_attention.py
Tests the continuous multimodal cross-attention and continuous Lie group state propagation.
"""

import pytest
import torch
from imf.multimodal_cross_attention import ContinuousMultimodalCrossAttention


def test_continuous_multimodal_cross_attention_forward_and_backward():
    B = 2
    T_text = 8
    T_sensory = 12
    d_model = 64
    d_sensory = 128
    d_state = 32

    model = ContinuousMultimodalCrossAttention(
        d_model=d_model,
        d_sensory=d_sensory,
        d_state=d_state,
        num_heads=2
    )

    text_tokens = torch.randn(B, T_text, d_model, requires_grad=True)
    sensory_frames = torch.randn(B, T_sensory, d_sensory, requires_grad=True)
    timestamps = torch.linspace(0.0, 1.2, T_sensory).unsqueeze(0).expand(B, -1)

    fused_text, final_state = model(text_tokens, sensory_frames, timestamps=timestamps)

    assert fused_text.shape == (B, T_text, d_model)
    assert final_state.shape == (B, d_state)
    assert not torch.isnan(fused_text).any()
    assert not torch.isnan(final_state).any()

    # Test backward pass gradient propagation
    loss = fused_text.sum() + final_state.sum()
    loss.backward()

    assert text_tokens.grad is not None
    assert sensory_frames.grad is not None
    assert not torch.isnan(text_tokens.grad).any()
    assert not torch.isnan(sensory_frames.grad).any()
