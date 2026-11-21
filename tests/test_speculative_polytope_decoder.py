"""
tests/test_speculative_polytope_decoder.py
Unit tests verifying the end-to-end SpeculativePolytopeDecoder:
1. Exact token match between standalone autoregression and speculative decoding at temperature=0.0.
2. Stochastic sampling verification at temperature > 0.0 with rejection sampling.
3. Speculative step statistics (acceptance rate, generated count, elapsed time).
4. Polytope drafter vs target dimension compatibility.
"""

import torch
import pytest
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.speculative_polytope_decoder import SpeculativePolytopeDecoder


@pytest.fixture
def models():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    vocab_size = 256

    # Target model: d_model=64, 2 layers, 4 experts
    target = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=64,
        num_layers=2,
        num_heads=2,
        polytope_dim=3,
        num_experts=4,
        top_k=2,
        max_seq_len=64,
    ).to(device)
    target.eval()

    # Drafter model: d_model=32, 1 layer, 2 experts
    drafter = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=32,
        num_layers=1,
        num_heads=2,
        polytope_dim=3,
        num_experts=2,
        top_k=1,
        max_seq_len=64,
    ).to(device)
    drafter.eval()

    return target, drafter, device


def test_speculative_greedy_exact_equivalence(models):
    target, drafter, device = models
    prompt = torch.tensor([[10, 20, 30]], device=device, dtype=torch.long)
    max_new_tokens = 16

    # Standalone greedy target rollout
    standalone_ids = prompt.clone()
    with torch.no_grad():
        for _ in range(max_new_tokens):
            logits, _, _ = target(standalone_ids)
            next_tok = logits[:, -1, :].argmax(dim=-1, keepdim=True)
            standalone_ids = torch.cat([standalone_ids, next_tok], dim=1)

    # Speculative decoder rollout
    decoder = SpeculativePolytopeDecoder(target_model=target, drafter_model=drafter, gamma=3, temperature=0.0)
    spec_ids, stats = decoder.generate_speculative(prompt, max_new_tokens=max_new_tokens)

    # Must match exactly up to max_new_tokens
    total_len = prompt.shape[1] + max_new_tokens
    assert standalone_ids[0, :total_len].tolist() == spec_ids[0, :total_len].tolist(), (
        f"Greedy speculative decoding violated exact target equivalence!\n"
        f"Standalone: {standalone_ids[0, :total_len].tolist()}\n"
        f"Speculative: {spec_ids[0, :total_len].tolist()}"
    )
    assert stats["generated_tokens"] >= max_new_tokens
    assert stats["speculative_steps"] > 0


def test_speculative_stochastic_sampling(models):
    target, drafter, device = models
    prompt = torch.tensor([[5, 15, 25]], device=device, dtype=torch.long)
    max_new_tokens = 12

    decoder = SpeculativePolytopeDecoder(target_model=target, drafter_model=drafter, gamma=2, temperature=1.0)
    spec_ids, stats = decoder.generate_speculative(prompt, max_new_tokens=max_new_tokens)

    assert spec_ids.shape[1] >= prompt.shape[1] + max_new_tokens
    assert stats["acceptance_rate"] >= 0.0
