"""
tests/test_polytope_tree_speculative.py
Unit tests verifying Polytope Tree-Search speculative decoding functionality and token production.
"""

import pytest
import torch
import torch.nn as nn
from imf.polytope_tree_speculative import PolytopeTreeSpeculativeDecoder


class DummyLM(nn.Module):
    def __init__(self, vocab_size=32, d_model=16):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, d_model)
        self.head = nn.Linear(d_model, vocab_size)

    def forward(self, x):
        h = self.embed(x)
        logits = self.head(h)
        return logits, None, {}


def test_tree_speculative_generation():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    target = DummyLM().to(device)
    drafter = DummyLM().to(device)

    decoder = PolytopeTreeSpeculativeDecoder(target, drafter, tree_depth=2, branch_factor=2)
    prompt = torch.tensor([[1, 2, 3]], device=device)

    out_ids, metrics = decoder.generate(prompt, max_new_tokens=8)

    assert out_ids.shape[0] == 1
    assert out_ids.shape[1] >= prompt.shape[1] + 8
    assert metrics["total_accepted"] >= 8
    print(f"[✓] Polytope Tree Speculative decoding generated {metrics['generated_tokens']} tokens in {metrics['steps']} steps.")
