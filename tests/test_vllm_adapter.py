"""
Unit tests for imf/vllm_adapter.py
Verifies:
1. Instantiation of IMFModelConfig, IMFForCausalLM_vLLM, and IMFVLLMWorkerAdapter.
2. Sequence allocation, state tracking, and memory deallocation.
3. Multi-sequence step batching and causal output validity.
"""

import pytest
import torch
from imf.vllm_adapter import (
    IMFModelConfig,
    IMFForCausalLM_vLLM,
    IMFVLLMWorkerAdapter,
)


def test_vllm_model_forward():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    config = IMFModelConfig(
        vocab_size=1000,
        d_model=64,
        num_layers=2,
        polytope_dim=4,
        num_experts=4,
        top_k=2,
        state_dim=4,
    )
    model = IMFForCausalLM_vLLM(config).to(device)
    model.eval()

    input_ids = torch.randint(0, 1000, (2, 8), device=device)
    with torch.no_grad():
        logits = model(input_ids)

    assert logits.shape == (2, 8, 1000)
    assert not torch.isnan(logits).any()


def test_vllm_worker_adapter_lifecycle():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    config = IMFModelConfig(
        vocab_size=500,
        d_model=64,
        num_layers=2,
        polytope_dim=4,
        num_experts=4,
        top_k=2,
        state_dim=4,
    )
    adapter = IMFVLLMWorkerAdapter(config, device=device)

    # Allocate sequences
    adapter.allocate_sequence(seq_id=101)
    adapter.allocate_sequence(seq_id=102)
    assert 101 in adapter.active_sequences
    assert 102 in adapter.active_sequences

    # Run step
    next_tokens = adapter.step(batch_seq_ids=[101, 102], input_token_ids=[42, 99])
    assert len(next_tokens) == 2
    for tok in next_tokens:
        assert 0 <= tok < 500

    # Free sequences
    adapter.free_sequence(101)
    assert 101 not in adapter.active_sequences
    assert 102 in adapter.active_sequences
    adapter.free_sequence(102)
    assert len(adapter.active_sequences) == 0
