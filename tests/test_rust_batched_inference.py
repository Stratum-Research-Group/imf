"""
tests/test_rust_batched_inference.py
Tests the zero-copy batched native Rust inference engine and parity.
"""

import pytest
import numpy as np
from imf.native_rust_bridge import is_rust_accelerator_available, rust_infer_batch


@pytest.mark.skipif(not is_rust_accelerator_available(), reason="libimf_rs.so not available")
def test_rust_batched_inference():
    B = 4
    D = 32
    V = 100

    np.random.seed(42)
    states = np.random.randn(B, D).astype(np.float32) * 0.1
    orig_states = states.copy()
    # Create skew-symmetric A matrices
    a_mats = np.zeros((B, D, D), dtype=np.float32)
    for b in range(B):
        m = np.random.randn(D, D).astype(np.float32) * 0.01
        a_mats[b] = m - m.T

    head_weights = np.random.randn(V, D).astype(np.float32) * 0.1

    # Run native Rust batched inference
    next_states, tokens, drifts = rust_infer_batch(states, a_mats, head_weights)

    assert next_states.shape == (B, D)
    assert tokens.shape == (B,)
    assert drifts.shape == (B,)

    # Verify predictions against NumPy manual calculation
    for b in range(B):
        # Expected step: x + x @ A
        expected_next = orig_states[b] + orig_states[b] @ a_mats[b]
        np.testing.assert_allclose(next_states[b], expected_next, rtol=1e-5, atol=1e-5)

        # Expected argmax: head_weights @ expected_next
        logits = head_weights @ expected_next
        expected_token = int(np.argmax(logits))
        assert tokens[b] == expected_token, f"Token mismatch at batch {b}: {tokens[b]} vs {expected_token}"
        assert drifts[b] > 0.0
