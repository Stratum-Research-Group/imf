"""
tests/test_pipelined_multimodal_streamer.py
Tests the asynchronous double-buffered streaming queue functionality and numerical stability.
"""

import pytest
import torch
from imf.omni_block import IMFOmniBlock
from imf.pipelined_multimodal_streamer import PipelinedMultimodalStreamer


def test_pipelined_multimodal_streamer():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    d_model = 64
    num_heads = 2
    tokens_per_frame = 32
    num_frames = 20
    
    block = IMFOmniBlock(d_model=d_model, num_heads=num_heads, use_triton_ssm=False)
    streamer = PipelinedMultimodalStreamer(
        block=block,
        d_model=d_model,
        tokens_per_frame=tokens_per_frame,
        device=device
    )
    
    frames = [torch.randn(1, tokens_per_frame, d_model) for _ in range(num_frames)]
    fps, tokens_per_sec, latencies = streamer.stream_frames(frames, num_frames=num_frames)
    
    assert len(latencies) == num_frames
    assert fps > 0.0
    assert tokens_per_sec > 0.0
    assert streamer.state is not None
    assert not torch.isnan(streamer.state).any()
