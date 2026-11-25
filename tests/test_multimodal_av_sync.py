"""
tests/test_multimodal_av_sync.py
Continuous Multimodal Cross-Attention Audio-Visual Synchronization Test Suite.
Validates multimodal cross-attention stability across asynchronous, non-uniform
video frame rates (~30 FPS) and high-frequency audio packets (~100 Hz) with temporal jitter.
Author: Nicholas Charles Mynhardt (Stratum Research Group)
"""

import math
import pytest
import torch
from imf.multimodal_cross_attention import ContinuousMultimodalCrossAttention


def test_continuous_cross_attention_forward_backward():
    """Verifies that gradients flow cleanly through both text tokens and sensory frames."""
    B, T_text, T_sensory = 2, 8, 12
    d_model, d_sensory, d_state = 64, 128, 32

    model = ContinuousMultimodalCrossAttention(
        d_model=d_model,
        d_sensory=d_sensory,
        d_state=d_state,
        num_heads=2
    )

    text_tokens = torch.randn(B, T_text, d_model, requires_grad=True)
    sensory_frames = torch.randn(B, T_sensory, d_sensory, requires_grad=True)
    timestamps = torch.linspace(0.0, 1.0, T_sensory).unsqueeze(0).expand(B, -1)

    text_fused, h_final = model(text_tokens, sensory_frames, timestamps=timestamps)

    assert text_fused.shape == (B, T_text, d_model)
    assert h_final.shape == (B, d_state)
    assert torch.isfinite(text_fused).all()
    assert torch.isfinite(h_final).all()

    # Backward pass
    loss = text_fused.sum() + h_final.sum()
    loss.backward()

    assert text_tokens.grad is not None
    assert sensory_frames.grad is not None
    assert torch.isfinite(text_tokens.grad).all()
    assert torch.isfinite(sensory_frames.grad).all()


def test_asynchronous_av_jitter_stability():
    """
    Simulates high-jitter variable-rate video (~33ms delta +/- 15ms)
    and verifies unitary Lie algebra rotation stability without numerical blowup.
    """
    B, T_sensory = 2, 30
    d_model, d_sensory, d_state = 64, 128, 32

    model = ContinuousMultimodalCrossAttention(
        d_model=d_model,
        d_sensory=d_sensory,
        d_state=d_state
    )

    text = torch.randn(B, 4, d_model)
    sensory = torch.randn(B, T_sensory, d_sensory)

    # Generate synthetic timestamps with non-uniform jitter (nominal 33.3ms intervals +/- 15ms)
    torch.manual_seed(42)
    deltas = 0.0333 + (torch.rand(B, T_sensory) - 0.5) * 0.030
    deltas[:, 0] = 0.0
    timestamps = torch.cumsum(deltas.clamp(min=0.005), dim=-1)

    text_out, h_out = model(text, sensory, timestamps=timestamps)

    assert torch.isfinite(text_out).all()
    assert torch.isfinite(h_out).all()
    # Norm of h_out should remain bounded
    norm_h = torch.norm(h_out, dim=-1)
    assert (norm_h < 100.0).all(), f"State norm diverged: {norm_h}"


def test_missing_frames_and_variable_packet_rate():
    """
    Tests robustness when 50% of intermediate frames are dropped
    (simulating packet loss or network stutter).
    """
    B = 2
    d_model, d_sensory, d_state = 64, 128, 32
    model = ContinuousMultimodalCrossAttention(d_model=d_model, d_sensory=d_sensory, d_state=d_state)

    text = torch.randn(B, 4, d_model)
    # Dropped stream (only 5 frames over 1.0 second duration)
    sparse_sensory = torch.randn(B, 5, d_sensory)
    sparse_timestamps = torch.tensor([[0.0, 0.15, 0.45, 0.80, 1.0],
                                      [0.0, 0.20, 0.50, 0.75, 1.0]])

    text_out, h_sparse = model(text, sparse_sensory, timestamps=sparse_timestamps)
    assert torch.isfinite(text_out).all()
    assert torch.isfinite(h_sparse).all()
