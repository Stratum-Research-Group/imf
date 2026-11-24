"""
imf/kernels/triton_fused_e8_polytope_specdec.py
Fused Triton GPU Kernel for E8 Gosset Sub-Bit Dequantization + Polytope Speculative Decoding.

Fuses:
1. E8 Gosset minimal lattice coordinate dequantization from packed 8-bit discrete root indices (0..239).
2. Cross-polytope topological inner-product alignment with current hidden state.
3. Parallel multi-branch argmax token prefix matching and bonus token generation in GPU registers.
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
    def _fused_e8_polytope_specdec_kernel(
        DraftTree_ptr,        # [NUM_PATHS, DEPTH] int64
        TargetLogits_ptr,     # [NUM_PATHS, DEPTH + 1, VOCAB] float32
        E8RootIndices_ptr,    # [NUM_PATHS, NUM_BLOCKS] uint8 (packed indices 0..239)
        E8Codebook_ptr,       # [240, 8] float32 (Gosset lattice root vectors)
        CurrentHidden_ptr,    # [EMBED_DIM] float32
        BestTokens_ptr,       # [DEPTH + 1] int64 (output)
        BestCount_ptr,        # [1] int32 (output)
        BestPathIdx_ptr,      # [1] int32 (output)
        NUM_PATHS: tl.constexpr,
        DEPTH: tl.constexpr,
        VOCAB: tl.constexpr,
        BLOCK_V: tl.constexpr,
        NUM_BLOCKS: tl.constexpr,
        EMBED_DIM: tl.constexpr,
    ):
        pid = tl.program_id(0)
        if pid != 0:
            return

        best_p = 0
        best_score = -1e30
        best_acc = 0

        for p in range(0, NUM_PATHS):
            # 1. On-the-fly E8 Gosset Dequantization & Dot Product in Register Loop
            dot_sim = 0.0
            for b in range(0, NUM_BLOCKS):
                root_idx = tl.load(E8RootIndices_ptr + p * NUM_BLOCKS + b) # uint8 0..239
                # 8D vector from codebook
                dim_offsets = tl.arange(0, 8)
                e8_vec = tl.load(E8Codebook_ptr + root_idx * 8 + dim_offsets)
                h_vec = tl.load(CurrentHidden_ptr + b * 8 + dim_offsets)
                dot_sim += tl.sum(e8_vec * h_vec, axis=0)

            # 2. Speculative Tree Prefix Match
            curr_acc = 0
            curr_mismatch = False
            for d in range(0, DEPTH):
                if not curr_mismatch:
                    d_tok = tl.load(DraftTree_ptr + p * DEPTH + d)
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

            # Combined score: token matches + E8 sub-bit geometric alignment
            combined_score = (curr_acc * 1000.0) + dot_sim
            if combined_score > best_score:
                best_score = combined_score
                best_acc = curr_acc
                best_p = p

        total_tokens_out = best_acc + 1
        tl.store(BestCount_ptr, total_tokens_out)
        tl.store(BestPathIdx_ptr, best_p)

        # Output winning accepted tokens
        acc_written = 0
        mismatch_seen = False
        for d in range(0, DEPTH):
            if not mismatch_seen:
                d_tok = tl.load(DraftTree_ptr + best_p * DEPTH + d)
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


def fused_e8_polytope_speculative_verify(
    candidate_paths: torch.Tensor,       # [NUM_PATHS, DEPTH] int64
    target_logits: torch.Tensor,        # [NUM_PATHS, DEPTH + 1, VOCAB] float32
    e8_root_indices: torch.Tensor,      # [NUM_PATHS, NUM_BLOCKS] uint8 (0..239)
    e8_codebook: torch.Tensor,          # [240, 8] float32
    current_hidden: torch.Tensor,       # [EMBED_DIM] float32
) -> Tuple[torch.Tensor, int, int]:
    """
    Fused E8 Dequantization + Speculative Verification.
    Returns (accepted_tokens, accepted_count, best_path_idx).
    """
    num_paths, depth = candidate_paths.shape
    vocab_size = target_logits.shape[-1]
    num_blocks = e8_root_indices.shape[-1]
    embed_dim = num_blocks * 8
    device = candidate_paths.device

    if HAS_TRITON and device.type == "cuda" and vocab_size <= 8192 and depth <= 8:
        best_tokens_out = torch.empty((depth + 1,), dtype=torch.long, device=device)
        best_count_out = torch.empty((1,), dtype=torch.int32, device=device)
        best_path_out = torch.empty((1,), dtype=torch.int32, device=device)

        BLOCK_V = min(triton.next_power_of_2(vocab_size), 1024)

        _fused_e8_polytope_specdec_kernel[(1,)](
            candidate_paths,
            target_logits.float(),
            e8_root_indices,
            e8_codebook.float(),
            current_hidden.float(),
            best_tokens_out,
            best_count_out,
            best_path_out,
            NUM_PATHS=num_paths,
            DEPTH=depth,
            VOCAB=vocab_size,
            BLOCK_V=BLOCK_V,
            NUM_BLOCKS=num_blocks,
            EMBED_DIM=embed_dim,
        )

        cnt = int(best_count_out.item())
        best_p = int(best_path_out.item())
        return best_tokens_out[:cnt], cnt, best_p
    else:
        # Vectorized fallback
        best_tokens = []
        best_p = 0
        best_score = -1e9
        dequant_vertices = e8_codebook[e8_root_indices.long()].reshape(num_paths, embed_dim)
        sims = F.cosine_similarity(current_hidden.unsqueeze(0), dequant_vertices, dim=-1)

        for p in range(num_paths):
            cand = candidate_paths[p]
            matched = []
            for d in range(depth):
                pred = torch.argmax(target_logits[p, d, :], dim=-1)
                if pred == cand[d]:
                    matched.append(cand[d].item())
                else:
                    matched.append(pred.item())
                    break
            score = len(matched) * 1000.0 + float(sims[p])
            if score > best_score:
                best_score = score
                best_tokens = matched
                best_p = p

        acc_tensor = torch.tensor(best_tokens, dtype=torch.long, device=device)
        return acc_tensor, len(best_tokens), best_p
