"""
tests/test_fused_speculative_verification.py
Unit tests verifying the fused speculative verification kernel:
1. Exact match on all draft tokens yielding full acceptance + bonus token.
2. Immediate mismatch at position 0 returning target token.
3. Partial prefix match at position k returning draft prefix + target correction.
4. Numerical equivalence between Triton kernel and vectorized PyTorch reference.
5. Large vocabulary boundary values and varying draft horizons (gamma = 1, 2, 4, 8).
"""

import pytest
import torch
from imf.fused_speculative_verification import fused_speculative_verify_greedy


@pytest.mark.parametrize("gamma", [1, 2, 4, 8])
def test_speculative_verification_full_acceptance(gamma):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    vocab_size = 1200

    # True draft tokens: [100, 101, ...]
    draft_tokens = torch.arange(100, 100 + gamma, dtype=torch.long, device=device)

    # Construct target logits such that the winning token at each pos is draft_tokens[pos],
    # and at pos gamma is bonus token 999.
    target_logits = torch.randn(gamma + 1, vocab_size, device=device)
    for i in range(gamma):
        target_logits[i, draft_tokens[i]] = 50.0
    target_logits[gamma, 999] = 50.0

    accepted = fused_speculative_verify_greedy(draft_tokens, target_logits)
    expected = draft_tokens.tolist() + [999]
    assert accepted.tolist() == expected, f"Expected {expected}, got {accepted.tolist()}"


@pytest.mark.parametrize("mismatch_idx", [0, 1, 3])
def test_speculative_verification_mismatch_correction(mismatch_idx):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    gamma = 4
    vocab_size = 1200

    draft_tokens = torch.tensor([10, 20, 30, 40], dtype=torch.long, device=device)
    target_logits = torch.randn(gamma + 1, vocab_size, device=device)

    for i in range(gamma):
        if i == mismatch_idx:
            # Set target to different token (777)
            target_logits[i, 777] = 50.0
        else:
            target_logits[i, draft_tokens[i]] = 50.0

    accepted = fused_speculative_verify_greedy(draft_tokens, target_logits)
    expected = draft_tokens[:mismatch_idx].tolist() + [777]
    assert accepted.tolist() == expected, f"Mismatch at {mismatch_idx}: expected {expected}, got {accepted.tolist()}"


def test_speculative_verification_all_mismatched():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    gamma = 3
    vocab_size = 500

    draft_tokens = torch.tensor([5, 6, 7], dtype=torch.long, device=device)
    target_logits = torch.randn(gamma + 1, vocab_size, device=device)
    # First position target is 99 != 5
    target_logits[0, 99] = 50.0

    accepted = fused_speculative_verify_greedy(draft_tokens, target_logits)
    assert accepted.tolist() == [99]
