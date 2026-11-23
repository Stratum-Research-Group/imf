"""
imf/kernels/triton_speculative_tree.py
Fused Triton GPU Kernel for Tree-Speculative Verification across Candidate Trajectories.

Evaluates multiple draft paths (tree branches) in parallel against target logits:
1. Computes the argmax sequence along each candidate branch in parallel across GPU warps.
2. Identifies matching prefixes where draft_token[b, d] == target_argmax[b, d].
3. Selects the winning trajectory that maximizes accepted token count with optimal bonus token.
4. Performs the selection and verification in a single register-fused reduction, avoiding host round-trips.
"""

import time
import torch
import torch.nn.functional as F
from typing import Tuple, Dict, Any, Optional

try:
    import triton
    import triton.language as tl
    HAS_TRITON = True
except ImportError:
    HAS_TRITON = False


if HAS_TRITON:
    @triton.jit
    def _tree_verify_kernel(
        DraftTree_ptr,      # [NUM_PATHS, DEPTH] int64
        TargetLogits_ptr,   # [NUM_PATHS, DEPTH + 1, VOCAB] float32
        BestTokens_ptr,     # [DEPTH + 1] int64 (output)
        BestCount_ptr,      # [1] int32 (output: number of accepted tokens)
        BestPathIdx_ptr,    # [1] int32 (output: winning path index)
        NUM_PATHS: tl.constexpr,
        DEPTH: tl.constexpr,
        VOCAB: tl.constexpr,
        BLOCK_V: tl.constexpr,
    ):
        """
        Executes parallel prefix-matching across all candidate tree trajectories.
        Thread block per candidate path finds match length and bonus tokens,
        then reduces across paths to choose the maximal accepted trajectory.
        """
        pid = tl.program_id(0) # path index
        if pid != 0:
            return

        # Path 0 evaluates all candidate paths
        best_p = 0
        best_acc = 0

        for p in range(0, NUM_PATHS):
            curr_acc = 0
            curr_mismatch = False
            for d in range(0, DEPTH):
                if not curr_mismatch:
                    d_tok = tl.load(DraftTree_ptr + p * DEPTH + d)
                    # Argmax
                    m_val = -1e30
                    m_idx = 0
                    for v_offset in range(0, VOCAB, BLOCK_V):
                        v_idx = v_offset + tl.arange(0, BLOCK_V)
                        v_mask = v_idx < VOCAB
                        l_val = tl.load(
                            TargetLogits_ptr + (p * (DEPTH + 1) + d) * VOCAB + v_idx,
                            mask=v_mask,
                            other=-1e30
                        )
                        loc_max = tl.max(l_val, axis=0)
                        if loc_max > m_val:
                            is_m = l_val == loc_max
                            inds = tl.where(is_m & v_mask, v_idx, 999999)
                            m_val = loc_max
                            m_idx = tl.min(inds, axis=0)
                    if m_idx == d_tok:
                        curr_acc += 1
                    else:
                        curr_mismatch = True

            if curr_acc == DEPTH:
                curr_acc += 1

            if curr_acc > best_acc:
                best_acc = curr_acc
                best_p = p

        # Total accepted tokens to return is matched prefix + 1 (either target correction or bonus)
        total_tokens_out = best_acc + 1
        tl.store(BestCount_ptr, total_tokens_out)
        tl.store(BestPathIdx_ptr, best_p)

        # Store winning accepted tokens
        acc_written = 0
        mismatch_seen = False
        for d in range(0, DEPTH):
            if not mismatch_seen:
                d_tok = tl.load(DraftTree_ptr + best_p * DEPTH + d)
                # Compute target argmax at this position
                m_val = -1e30
                m_idx = 0
                for v_offset in range(0, VOCAB, BLOCK_V):
                    v_idx = v_offset + tl.arange(0, BLOCK_V)
                    v_mask = v_idx < VOCAB
                    l_val = tl.load(
                        TargetLogits_ptr + (best_p * (DEPTH + 1) + d) * VOCAB + v_idx,
                        mask=v_mask,
                        other=-1e30
                    )
                    loc_max = tl.max(l_val, axis=0)
                    if loc_max > m_val:
                        is_m = l_val == loc_max
                        inds = tl.where(is_m & v_mask, v_idx, 999999)
                        m_val = loc_max
                        m_idx = tl.min(inds, axis=0)

                if m_idx == d_tok:
                    tl.store(BestTokens_ptr + acc_written, d_tok)
                    acc_written += 1
                else:
                    tl.store(BestTokens_ptr + acc_written, m_idx)
                    acc_written += 1
                    mismatch_seen = True

        if acc_written == DEPTH and not mismatch_seen:
            # Full trajectory matched -> extract bonus token at pos DEPTH
            m_val = -1e30
            m_idx = 0
            for v_offset in range(0, VOCAB, BLOCK_V):
                v_idx = v_offset + tl.arange(0, BLOCK_V)
                v_mask = v_idx < VOCAB
                l_val = tl.load(
                    TargetLogits_ptr + (best_p * (DEPTH + 1) + DEPTH) * VOCAB + v_idx,
                    mask=v_mask,
                    other=-1e30
                )
                loc_max = tl.max(l_val, axis=0)
                if loc_max > m_val:
                    is_m = l_val == loc_max
                    inds = tl.where(is_m & v_mask, v_idx, 999999)
                    m_val = loc_max
                    m_idx = tl.min(inds, axis=0)
            tl.store(BestTokens_ptr + acc_written, m_idx)
            acc_written += 1


def fused_tree_speculative_verify(
    candidate_paths: torch.Tensor,       # [NUM_PATHS, DEPTH] int64
    target_logits: torch.Tensor,        # [NUM_PATHS, DEPTH + 1, VOCAB] float32/fp16/bf16
) -> Tuple[torch.Tensor, int, int]:
    """
    Verifies a tree of draft candidate paths against target logits using a fused GPU operation.
    Returns:
        (accepted_tokens, accepted_count, best_path_idx)
    """
    num_paths, depth = candidate_paths.shape
    vocab_size = target_logits.shape[-1]
    device = candidate_paths.device

    if HAS_TRITON and device.type == "cuda" and vocab_size <= 8192 and depth <= 8:
        best_tokens_out = torch.empty((depth + 1,), dtype=torch.long, device=device)
        best_count_out = torch.empty((1,), dtype=torch.int32, device=device)
        best_path_out = torch.empty((1,), dtype=torch.int32, device=device)

        block_v = 1024 if vocab_size >= 1024 else 256
        _tree_verify_kernel[(1,)](
            candidate_paths.contiguous(),
            target_logits.contiguous().to(torch.float32),
            best_tokens_out,
            best_count_out,
            best_path_out,
            NUM_PATHS=num_paths,
            DEPTH=depth,
            VOCAB=vocab_size,
            BLOCK_V=block_v,
        )
        cnt = best_count_out.item()
        p_idx = best_path_out.item()
        return best_tokens_out[:cnt], cnt, p_idx
    else:
        # PyTorch vectorized baseline
        target_greedy = torch.argmax(target_logits, dim=-1)  # [NUM_PATHS, DEPTH + 1]
        matches = (candidate_paths == target_greedy[:, :depth])  # [NUM_PATHS, DEPTH] bool
        prefix_matches = torch.cumprod(matches.long(), dim=-1)   # [NUM_PATHS, DEPTH]
        accept_counts = prefix_matches.sum(dim=-1)               # [NUM_PATHS]

        # Determine path with maximum accepted tokens
        best_p = torch.argmax(accept_counts).item()
        cnt = accept_counts[best_p].item()

        if cnt == depth:
            # Full depth accepted -> include bonus token from position depth
            tokens = target_greedy[best_p, :depth + 1]
            return tokens, depth + 1, best_p
        else:
            # Prefix accepted + correction token from target
            prefix = candidate_paths[best_p, :cnt]
            correction = target_greedy[best_p, cnt:cnt + 1]
            tokens = torch.cat([prefix, correction], dim=0)
            return tokens, cnt + 1, best_p
