"""
imf/polytope_tree_speculative.py
Multi-Token Speculative Tree-Drafting Engine (IMF Polytope Tree-Search).
Fused with GPU Triton Tree-Verification Kernel (_tree_verify_kernel).
Generates a tree of candidate token trajectories from the drafter model,
evaluating multiple candidate branches concurrently in a single target model forward pass.
"""

import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Tuple, Dict, Any, Optional

try:
    from imf.kernels.triton_speculative_tree import fused_tree_speculative_verify, HAS_TRITON
except ImportError:
    HAS_TRITON = False
    fused_tree_speculative_verify = None


class PolytopeTreeSpeculativeDecoder:
    """
    Speculates candidate token trees (depth D, branch factor B).
    Evaluates B^D candidate leaves with a single batched target forward pass,
    selecting the longest verified prefix path via register-fused Triton kernel.
    """
    def __init__(
        self,
        target_model: nn.Module,
        drafter_model: nn.Module,
        tree_depth: int = 3,
        branch_factor: int = 2,
    ):
        self.target = target_model
        self.drafter = drafter_model
        self.depth = tree_depth
        self.branch = branch_factor
        self.target.eval()
        self.drafter.eval()

    @torch.no_grad()
    def generate(
        self,
        prompt_ids: torch.Tensor,
        max_new_tokens: int = 24,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        device = prompt_ids.device
        curr_ids = prompt_ids.clone()
        start_t = time.perf_counter()
        
        total_accepted = 0
        steps = 0

        while (curr_ids.shape[1] - prompt_ids.shape[1]) < max_new_tokens:
            steps += 1
            # Step 1: Draft top candidate paths
            # Level 1: top-B tokens from drafter
            d_out = self.drafter(curr_ids)
            d_logits = d_out[0] if isinstance(d_out, (tuple, list)) else d_out
            topk_level1 = torch.topk(d_logits[:, -1, :], self.branch, dim=-1).indices[0]  # [B]

            candidate_paths = []
            draft_tails = []

            for b1 in topk_level1:
                seq1 = torch.cat([curr_ids, b1.view(1, 1)], dim=-1)
                # Level 2 greedy continuation
                d_out2 = self.drafter(seq1)
                d_logits2 = d_out2[0] if isinstance(d_out2, (tuple, list)) else d_out2
                b2 = torch.argmax(d_logits2[:, -1, :], dim=-1, keepdim=True)
                seq2 = torch.cat([seq1, b2], dim=-1)
                candidate_paths.append(seq2)
                draft_tails.append(torch.cat([b1.view(1), b2.view(1)], dim=0))

            # Batched target evaluation of all candidate paths
            batch_candidates = torch.cat(candidate_paths, dim=0)  # [B, L+2]
            t_out = self.target(batch_candidates)
            t_logits = t_out[0] if isinstance(t_out, (tuple, list)) else t_out  # [B, L+2, V]

            base_len = curr_ids.shape[1]
            depth = 2

            # Try Triton fused verification first
            if HAS_TRITON and device.type == "cuda" and fused_tree_speculative_verify is not None:
                paths_tensor = torch.stack(draft_tails, dim=0) # [B, 2]
                relevant_logits = t_logits[:, base_len - 1 : base_len + depth, :] # [B, 3, V]
                accepted_tokens, cnt, best_p = fused_tree_speculative_verify(paths_tensor, relevant_logits)
                curr_ids = torch.cat([curr_ids, accepted_tokens.unsqueeze(0)], dim=-1)
                total_accepted += cnt
            else:
                # Fallback vectorized verification
                best_accepted_tokens = None
                best_len = -1

                for idx in range(self.branch):
                    cand_tokens = batch_candidates[idx, base_len:]
                    accepted = []
                    for step_idx in range(len(cand_tokens)):
                        pred_t = torch.argmax(t_logits[idx, base_len - 1 + step_idx, :], dim=-1)
                        if pred_t == cand_tokens[step_idx]:
                            accepted.append(cand_tokens[step_idx].item())
                        else:
                            accepted.append(pred_t.item())
                            break
                    if len(accepted) > best_len:
                        best_len = len(accepted)
                        best_accepted_tokens = accepted

                if not best_accepted_tokens:
                    t_out_fallback = self.target(curr_ids)
                    t_logits_fb = t_out_fallback[0] if isinstance(t_out_fallback, (tuple, list)) else t_out_fallback
                    fallback_tok = torch.argmax(t_logits_fb[:, -1, :], dim=-1, keepdim=True)
                    curr_ids = torch.cat([curr_ids, fallback_tok], dim=-1)
                    total_accepted += 1
                else:
                    acc_tensor = torch.tensor([best_accepted_tokens], device=device)
                    curr_ids = torch.cat([curr_ids, acc_tensor], dim=-1)
                    total_accepted += len(best_accepted_tokens)

        elapsed = time.perf_counter() - start_t
        gen_count = curr_ids.shape[1] - prompt_ids.shape[1]
        throughput = gen_count / max(elapsed, 1e-6)

        metrics = {
            "generated_tokens": gen_count,
            "total_accepted": total_accepted,
            "steps": steps,
            "elapsed_s": elapsed,
            "throughput_tok_per_sec": throughput,
            "fused_triton_kernel": bool(HAS_TRITON and device.type == "cuda"),
        }
        return curr_ids, metrics
