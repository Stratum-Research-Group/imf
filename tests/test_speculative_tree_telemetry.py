"""
tests/test_speculative_tree_telemetry.py
Tests the speculative tree decoding diagnostics and depth metrics.
"""

import pytest
import torch
from imf.diagnostics.speculative_tree_telemetry import SpeculativeTreeTelemetry


@pytest.mark.skipif(not torch.cuda.is_available(), reason="Requires CUDA GPU")
def test_speculative_tree_telemetry_metrics():
    device = "cuda"
    telemetry = SpeculativeTreeTelemetry(num_nodes=7, vocab_size=2048, device=device)

    logits = torch.randn(2, 7, 2048, device=device)
    stats = telemetry.evaluate_entropy_slice(logits)

    assert stats["num_nodes"] == 7
    assert stats["dispatch_time_ms"] > 0.0
    assert "depth_confidence" in stats
    assert stats["tree_efficiency_ratio"] > 0.0
