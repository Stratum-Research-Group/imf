"""
fused_speculative_verification.py
Triton JIT kernel and PyTorch interface for Fused Speculative Verification.

Fuses:
1. Parallel target greedy prediction extraction across all gamma draft positions.
2. Draft candidate comparison: matches draft[i] vs target_argmax[i].
3. Prefix acceptance count and bonus/correction token selection.

Eliminates Python loop overhead and repeated CPU-GPU tensor synchronizations
during speculative decoding verification steps.
"""

import torch
import torch.nn.functional as F

try:
    import triton
    import triton.language as tl
    HAS_TRITON = True
except ImportError:
    HAS_TRITON = False


if HAS_TRITON:
    @triton.jit
    def _fused_greedy_verify_kernel(
        Draft_ptr,          # [GAMMA] int64
        TargetLogits_ptr,   # [GAMMA + 1, VOCAB] float32 / float16 / bfloat16
        AcceptedOut_ptr,    # [GAMMA + 1] int64
        CountOut_ptr,       # [1] int32
        VOCAB: tl.constexpr,
        GAMMA: tl.constexpr,
        BLOCK_V: tl.constexpr,
    ):
        """
        Fused kernel executing speculative greedy verification:
        For position i in 0..GAMMA-1:
            target_tok = argmax(TargetLogits[i, :])
            if target_tok == Draft[i] and not rejected:
                AcceptedOut[accepted_count] = target_tok
                accepted_count += 1
            elif not rejected:
                AcceptedOut[accepted_count] = target_tok
                accepted_count += 1
                rejected = True
        If accepted_count == GAMMA:
            bonus_tok = argmax(TargetLogits[GAMMA, :])
            AcceptedOut[GAMMA] = bonus_tok
            accepted_count += 1
        """
        # Single block performs sequential prefix check after parallel reductions
        pid = tl.program_id(0)
        if pid != 0:
            return

        # 1. Compute argmax for each position 0..GAMMA
        # We store winning indices and values
        # Since GAMMA is small (e.g. 2..8), unroll positions
        accepted = 0
        mismatch_found = False

        for pos in range(GAMMA):
            if not mismatch_found:
                # Find argmax across VOCAB
                max_val = -1e30
                max_idx = 0
                for v_offset in range(0, VOCAB, BLOCK_V):
                    v_idx = v_offset + tl.arange(0, BLOCK_V)
                    v_mask = v_idx < VOCAB
                    logits = tl.load(
                        TargetLogits_ptr + pos * VOCAB + v_idx,
                        mask=v_mask,
                        other=-1e30
                    )
                    local_max = tl.max(logits, axis=0)
                    if local_max > max_val:
                        # Find exact index of maximum in this block
                        # Simple reduction within block
                        is_max = logits == local_max
                        # First match
                        indices = tl.where(is_max & v_mask, v_idx, 999999)
                        best_idx = tl.min(indices, axis=0)
                        max_val = local_max
                        max_idx = best_idx

                draft_tok = tl.load(Draft_ptr + pos)
                if draft_tok == max_idx:
                    tl.store(AcceptedOut_ptr + accepted, draft_tok)
                    accepted += 1
                else:
                    tl.store(AcceptedOut_ptr + accepted, max_idx)
                    accepted += 1
                    mismatch_found = True

        # Check bonus token if all GAMMA were accepted
        if accepted == GAMMA:
            max_val = -1e30
            max_idx = 0
            pos = GAMMA
            for v_offset in range(0, VOCAB, BLOCK_V):
                v_idx = v_offset + tl.arange(0, BLOCK_V)
                v_mask = v_idx < VOCAB
                logits = tl.load(
                    TargetLogits_ptr + pos * VOCAB + v_idx,
                    mask=v_mask,
                    other=-1e30
                )
                local_max = tl.max(logits, axis=0)
                if local_max > max_val:
                    is_max = logits == local_max
                    indices = tl.where(is_max & v_mask, v_idx, 999999)
                    best_idx = tl.min(indices, axis=0)
                    max_val = local_max
                    max_idx = best_idx
            tl.store(AcceptedOut_ptr + accepted, max_idx)
            accepted += 1

        tl.store(CountOut_ptr, accepted)


def fused_speculative_verify_greedy(
    draft_tokens: torch.Tensor,       # [gamma] int64
    target_logits: torch.Tensor,      # [gamma + 1, vocab] float32/fp16/bf16
) -> torch.Tensor:
    """
    Verifies draft tokens against target logits in a single fused GPU operation.
    Returns tensor of accepted tokens to append: [num_accepted] int64.
    """
    gamma = draft_tokens.shape[0]
    vocab_size = target_logits.shape[-1]
    device = draft_tokens.device

    if HAS_TRITON and device.type == "cuda" and vocab_size <= 8192 and gamma <= 8:
        # Use fused Triton kernel
        accepted_out = torch.empty((gamma + 1,), dtype=torch.long, device=device)
        count_out = torch.empty((1,), dtype=torch.int32, device=device)
        
        # Power-of-2 block size for vocab reduction
        block_v = 1024 if vocab_size >= 1024 else 256
        _fused_greedy_verify_kernel[(1,)](
            draft_tokens.contiguous(),
            target_logits.contiguous().to(torch.float32),
            accepted_out,
            count_out,
            VOCAB=vocab_size,
            GAMMA=gamma,
            BLOCK_V=block_v,
        )
        cnt = count_out.item()
        return accepted_out[:cnt]
    else:
        # Vectorized PyTorch verification (no Python loops over tokens)
        target_greedy = torch.argmax(target_logits, dim=-1)  # [gamma + 1]
        matches = (draft_tokens == target_greedy[:gamma])     # [gamma] bool
        
        # Cumulative product gives prefix acceptance mask
        prefix_valid = torch.cumprod(matches.long(), dim=0).bool()
        num_accepted_draft = prefix_valid.sum().item()

        if num_accepted_draft == gamma:
            # All gamma accepted, include bonus token from position gamma
            return target_greedy[:gamma + 1]
        else:
            # Prefix draft accepted + correction token from target at failure position
            accepted_prefix = draft_tokens[:num_accepted_draft]
            correction = target_greedy[num_accepted_draft:num_accepted_draft + 1]
            return torch.cat([accepted_prefix, correction], dim=0)
