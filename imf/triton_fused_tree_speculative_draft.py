"""
imf/triton_fused_tree_speculative_draft.py
Fused Triton Speculative Tree-Draft Decoding Kernel.
Evaluates tree branching speculative candidate paths on GPU in parallel.
Generates candidate tokens, tree attention masks, and probability paths.
"""

import torch
import triton
import triton.language as tl
from typing import Tuple


@triton.jit
def _tree_speculative_draft_kernel(
    logits_ptr,          # [B, Num_Nodes, Vocab_Size]
    tree_parent_ptr,     # [Num_Nodes] parent indices (-1 for root)
    tree_mask_out_ptr,   # [Num_Nodes, Num_Nodes] attention visibility matrix
    candidate_toks_ptr,  # [B, Num_Nodes] argmax/top tokens
    path_scores_ptr,     # [B, Num_Nodes] cumulative log-probability
    num_nodes: tl.constexpr,
    vocab_size: tl.constexpr,
    BLOCK_V: tl.constexpr,
):
    pid_b = tl.program_id(0)
    pid_node = tl.program_id(1)

    # 1. Identify best token at this tree node (Argmax reduction over vocab)
    base_logits = logits_ptr + pid_b * (num_nodes * vocab_size) + pid_node * vocab_size
    max_val = -1e9
    best_idx = 0

    for v_start in range(0, vocab_size, BLOCK_V):
        v_offsets = v_start + tl.arange(0, BLOCK_V)
        mask = v_offsets < vocab_size
        vals = tl.load(base_logits + v_offsets, mask=mask, other=-1e9)
        local_max = tl.max(vals, axis=0)
        if local_max > max_val:
            max_val = local_max
            idx_in_block = tl.argmax(vals, axis=0)
            best_idx = v_start + idx_in_block

    tl.store(candidate_toks_ptr + pid_b * num_nodes + pid_node, best_idx)
    tl.store(path_scores_ptr + pid_b * num_nodes + pid_node, max_val)

    # 2. Build tree attention mask: bounded unroll over tree depth (max depth 16)
    if pid_b == 0:
        for j in range(num_nodes):
            is_visible = 0
            if j == pid_node:
                is_visible = 1
            else:
                curr = tl.load(tree_parent_ptr + pid_node)
                for _step in range(16):
                    if curr >= 0:
                        if curr == j:
                            is_visible = 1
                        curr = tl.load(tree_parent_ptr + curr)
            tl.store(tree_mask_out_ptr + pid_node * num_nodes + j, is_visible)



def fused_tree_speculative_draft(
    logits: torch.Tensor,
    tree_parents: torch.Tensor,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Args:
        logits: [B, Num_Nodes, Vocab_Size] float32/float16
        tree_parents: [Num_Nodes] int32 with parent node indices (-1 for root)
    Returns:
        candidate_tokens: [B, Num_Nodes] int64
        path_scores: [B, Num_Nodes] float32
        tree_mask: [Num_Nodes, Num_Nodes] float32 (1.0 if attended, 0.0 otherwise)
    """
    B, num_nodes, vocab_size = logits.shape
    device = logits.device
    
    candidate_tokens = torch.empty((B, num_nodes), dtype=torch.int64, device=device)
    path_scores = torch.empty((B, num_nodes), dtype=torch.float32, device=device)
    tree_mask = torch.zeros((num_nodes, num_nodes), dtype=torch.float32, device=device)
    
    tree_parents_i32 = tree_parents.to(device=device, dtype=torch.int32).contiguous()
    
    BLOCK_V = 1024
    grid = (B, num_nodes)
    
    _tree_speculative_draft_kernel[grid](
        logits.float().contiguous(),
        tree_parents_i32,
        tree_mask,
        candidate_tokens,
        path_scores,
        num_nodes=num_nodes,
        vocab_size=vocab_size,
        BLOCK_V=BLOCK_V,
    )
    
    return candidate_tokens, path_scores, tree_mask
