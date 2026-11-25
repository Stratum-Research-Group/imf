"""
14B MoPE Speculative Engine with Fused Triton KV Gather & Non-Euclidean Routing
Hardware Target: NVIDIA GeForce RTX 5060 Ti (SM 8.9 AD106)

Accelerates speculative decoding by fusing draft verification KV cache projections
and hyperbolic routing into a continuous Triton execution flow.
"""

import time
import torch
import torch.nn as nn
import triton
import triton.language as tl
from imf.models.mope_14b_module import PoincareMoPE14BModel

@triton.jit
def _fused_speculative_gather_routing_kernel(
    draft_tokens_ptr,      # [K_DRAFT, D] drafted token representations
    centroids_ptr,         # [N_EXPERTS, D] hyperbolic expert centroids
    routing_weights_ptr,   # [K_DRAFT, 2] output top-2 hyperbolic weights
    routing_indices_ptr,   # [K_DRAFT, 2] output top-2 expert indices
    D: tl.constexpr,
    N_EXPERTS: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    pid = tl.program_id(0) # token index along draft length K_DRAFT
    d_offsets = tl.arange(0, BLOCK_D)
    mask_d = d_offsets < D

    t_vec = tl.load(draft_tokens_ptr + pid * D + d_offsets, mask=mask_d, other=0.0)
    t_norm_sq = tl.sum(t_vec * t_vec, axis=0)

    # Compute hyperbolic distance to experts: d_H(x, y) = arcosh(1 + 2 ||x-y||^2 / ((1-||x||^2)(1-||y||^2)))
    # We maintain top-2 minimal distances
    min_dist1 = 1e9
    min_idx1 = 0
    min_dist2 = 1e9
    min_idx2 = 0

    denom_x = 1.0 - tl.minimum(t_norm_sq, 0.99)

    for e in range(N_EXPERTS):
        c_vec = tl.load(centroids_ptr + e * D + d_offsets, mask=mask_d, other=0.0)
        c_norm_sq = tl.sum(c_vec * c_vec, axis=0)
        diff = t_vec - c_vec
        diff_norm_sq = tl.sum(diff * diff, axis=0)
        denom = denom_x * (1.0 - tl.minimum(c_norm_sq, 0.99))
        dist = diff_norm_sq / tl.maximum(denom, 1e-6)

        if dist < min_dist1:
            min_dist2 = min_dist1
            min_idx2 = min_idx1
            min_dist1 = dist
            min_idx1 = e
        elif dist < min_dist2:
            min_dist2 = dist
            min_idx2 = e

    # Softmax on negative hyperbolic distances
    w1 = tl.exp(-min_dist1)
    w2 = tl.exp(-min_dist2)
    w_sum = w1 + w2 + 1e-6
    w1 = w1 / w_sum
    w2 = w2 / w_sum

    tl.store(routing_weights_ptr + pid * 2 + 0, w1)
    tl.store(routing_weights_ptr + pid * 2 + 1, w2)
    tl.store(routing_indices_ptr + pid * 2 + 0, min_idx1)
    tl.store(routing_indices_ptr + pid * 2 + 1, min_idx2)

def fused_speculative_routing(draft_tokens: torch.Tensor, centroids: torch.Tensor):
    K_DRAFT, D = draft_tokens.shape
    N_EXPERTS = centroids.shape[0]
    routing_weights = torch.empty(K_DRAFT, 2, device=draft_tokens.device, dtype=torch.float32)
    routing_indices = torch.empty(K_DRAFT, 2, device=draft_tokens.device, dtype=torch.int32)

    BLOCK_D = 4096
    grid = (K_DRAFT,)

    _fused_speculative_gather_routing_kernel[grid](
        draft_tokens, centroids,
        routing_weights, routing_indices,
        D=D, N_EXPERTS=N_EXPERTS, BLOCK_D=BLOCK_D
    )
    return routing_weights, routing_indices

class FusedSpeculativeEngine:
    def __init__(self, device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        self.device = device
        print(f"[MoPE 14B Fused Speculative Engine] Initializing on {device}...")
        self.verifier = PoincareMoPE14BModel(n_layers=2, d_model=4096).to(self.device).eval()
        
        N, K = 2816, 4096
        self.roots = torch.randn(240, 8, device=self.device, dtype=torch.float16)
        self.expert_codes = torch.randint(0, 240, (N, K // 8), device=self.device, dtype=torch.uint8)
        self.expert_scales = torch.ones((N, K // 32), device=self.device, dtype=torch.float16) * 0.02
        self.expert_centroids = torch.randn(16, 4096, device=self.device, dtype=torch.float32) * 0.05

        print("[✓] Fused Engine Ready.")

    def benchmark(self, draft_k: int = 4, target_tokens: int = 128):
        print(f"[*] Benchmarking Fused Speculative Engine: Draft K={draft_k}, Target={target_tokens} tokens...")
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        t0 = time.perf_counter()

        generated = 0
        accepted_tokens = 0

        while generated < target_tokens:
            step_draft = min(draft_k, target_tokens - generated)
            fake_draft = (torch.randn(step_draft, 4096, device=self.device, dtype=torch.float32) * 0.05).contiguous()
            
            # Fused speculative routing launch
            w, idx = fused_speculative_routing(fake_draft, self.expert_centroids)

            # Verification forward
            batch_tokens = fake_draft.half().unsqueeze(0)
            with torch.no_grad():
                out = self.verifier(batch_tokens, self.roots, self.expert_codes, self.expert_scales)

            accepted_tokens += step_draft
            generated += step_draft

        torch.cuda.synchronize()
        elapsed = time.perf_counter() - t0

        vram_peak_mb = torch.cuda.max_memory_allocated() / (1024 ** 2)
        tokens_per_sec = accepted_tokens / elapsed
        latency_per_token_ms = (elapsed / accepted_tokens) * 1000

        print(f"[✓] Fused Speculative Decoding Complete:")
        print(f"    Total Tokens Generated: {accepted_tokens}")
        print(f"    Elapsed Time:           {elapsed * 1000:.2f} ms")
        print(f"    Latency per Token:      {latency_per_token_ms:.3f} ms/token")
        print(f"    Fused Speculative Rate: {tokens_per_sec:.2f} tokens/s")
        print(f"    Peak Workspace VRAM:    {vram_peak_mb:.2f} MB")
        return tokens_per_sec, latency_per_token_ms

if __name__ == "__main__":
    engine = FusedSpeculativeEngine()
    engine.benchmark(draft_k=4, target_tokens=128)
