"""
tests/test_triton_tree_speculative_draft.py
Tests the fused Triton speculative tree-draft kernel against PyTorch reference.
"""

import pytest
import torch
from imf.triton_fused_tree_speculative_draft import fused_tree_speculative_draft


@pytest.mark.skipif(not torch.cuda.is_available(), reason="Requires CUDA GPU")
def test_triton_tree_speculative_draft():
    device = "cuda"
    B = 2
    num_nodes = 7 # 1 root, 2 children, 4 grandchildren
    vocab_size = 2048
    
    # Tree topology:
    # Node 0 (root, parent -1)
    # Node 1 (child of 0), Node 2 (child of 0)
    # Node 3,4 (children of 1), Node 5,6 (children of 2)
    tree_parents = torch.tensor([-1, 0, 0, 1, 1, 2, 2], dtype=torch.int32, device=device)
    
    logits = torch.randn(B, num_nodes, vocab_size, device=device)
    
    candidate_tokens, path_scores, tree_mask = fused_tree_speculative_draft(logits, tree_parents)
    
    # 1. Parity check on candidate tokens
    expected_tokens = torch.argmax(logits, dim=-1)
    assert torch.all(candidate_tokens == expected_tokens), "Candidate tokens mismatch"
    
    # 2. Check tree visibility mask
    # Node 3 is child of 1, child of 0. It should see 0, 1, 3 and not 2, 4, 5, 6
    assert tree_mask[3, 0].item() == 1.0
    assert tree_mask[3, 1].item() == 1.0
    assert tree_mask[3, 3].item() == 1.0
    assert tree_mask[3, 2].item() == 0.0
    assert tree_mask[3, 4].item() == 0.0
    
    # Node 0 only sees itself
    assert tree_mask[0, 0].item() == 1.0
    assert torch.sum(tree_mask[0]).item() == 1.0
