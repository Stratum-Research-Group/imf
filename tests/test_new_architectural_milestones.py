"""
tests/test_new_architectural_milestones.py
Tests covering Item 2 (Triton Fused MLA Backward), Item 3 (Rust AVX2 Polytope Projection),
Item 4 (RSI Priority Replay Buffer), and Item 5 (Mmap Parquet Streamer).
Author: Nicholas Charles Mynhardt (Stratum Research Group)
"""

import os
from pathlib import Path
import numpy as np
import pytest
import torch


def test_triton_fused_poincare_mla_backward():
    """Validates Triton MLA backward kernel execution and shape parity."""
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")

    from imf.kernels.triton_fused_poincare_mla_backward import poincare_mla_backward_triton

    B, S, D, D_latent = 2, 8, 32, 16
    grad_out = torch.randn(B, S, D, device="cuda", dtype=torch.float32)
    q = torch.randn(B, S, D, device="cuda", dtype=torch.float32) * 0.1
    c_kv = torch.randn(B, S, D_latent, device="cuda", dtype=torch.float32) * 0.1
    w_uk = torch.randn(D_latent, D, device="cuda", dtype=torch.float32) * 0.1
    w_uv = torch.randn(D_latent, D, device="cuda", dtype=torch.float32) * 0.1

    grad_c_kv, grad_q = poincare_mla_backward_triton(grad_out, q, c_kv, w_uk, w_uv)

    assert grad_c_kv.shape == (B, S, D_latent)
    assert grad_q.shape == (B, S, D)
    assert torch.isfinite(grad_c_kv).all()
    assert torch.isfinite(grad_q).all()


def test_rust_polytope_projection_avx2_parity():
    """Validates Rust AVX2 polytope projection exact numerical equivalence with NumPy argmax."""
    from imf.native_rust_bridge import rust_polytope_projection_avx2

    N = 8
    V = 64
    D = 8
    np.random.seed(123)
    vecs = np.random.randn(N, D).astype(np.float32)
    verts = np.random.randn(V, D).astype(np.float32)

    proj, idxs = rust_polytope_projection_avx2(vecs, verts)

    for i in range(N):
        dots = verts @ vecs[i]
        best_expected = np.argmax(dots)
        assert idxs[i] == best_expected
        np.testing.assert_allclose(proj[i], verts[best_expected], rtol=1e-5)


def test_rsi_priority_replay_sampling_distribution():
    """Verifies that high-priority experiences are sampled with higher empirical frequency."""
    from imf.rsi_priority_replay import RSIPriorityReplayBuffer

    buf = RSIPriorityReplayBuffer(capacity=500, alpha=1.0, beta=0.5)
    # Add one item with 10x higher priority
    for i in range(10):
        buf.add({"id": i}, initial_priority=1.0 if i < 9 else 20.0)

    samples, idxs, weights = buf.sample(100)
    high_count = sum(1 for s in samples if s["id"] == 9)
    # Item 9 has weight 20 / 29 ~ 69% of the distribution mass
    assert high_count > 30, f"Expected high priority item to dominate, got count {high_count}"
    assert len(weights) == 100
    assert (weights > 0).all()


def test_mmap_parquet_streamer_iteration():
    """Validates streaming iteration and tensor generation from partitioned Parquet files."""
    from imf.mmap_parquet_streamer import MmapParquetTheoremDataset

    lake_dir = Path("dist/parquet_lake")
    files = sorted(lake_dir.glob("*.parquet"))
    if not files:
        pytest.skip("No parquet lake files available")

    ds = MmapParquetTheoremDataset(parquet_paths=files[:1], batch_size=16, max_seq_len=64)
    batches = []
    for i, b in enumerate(ds):
        batches.append(b)
        if i >= 3:
            break

    assert len(batches) > 0
    assert "input_ids" in batches[0]
    assert "attention_mask" in batches[0]
    assert batches[0]["input_ids"].shape[-1] == 64
    assert batches[0]["input_ids"].dtype == torch.long
