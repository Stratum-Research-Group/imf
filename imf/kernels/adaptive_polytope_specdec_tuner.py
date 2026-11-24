"""
imf/kernels/adaptive_polytope_specdec_tuner.py
Empirical Adaptive Speculative Polytope Auto-Tuner.
Dynamically sweeps draft paths and depth K in [2, 8] to optimize speculative verification
throughput on NVIDIA RTX 5060 Ti GPU.
"""

import time
import torch
from pathlib import Path
from imf.kernels.triton_fused_e8_polytope_specdec import fused_e8_polytope_speculative_verify

def run_specdec_autotuner():
    print("=" * 80)
    print("  IMF EMPIRICAL ADAPTIVE SPECULATIVE POLYTOPE AUTO-TUNER")
    print("  Evaluating GPU Register Latency and Verification Throughput (NVIDIA RTX 5060 Ti)")
    print("=" * 80)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    vocab_size = 4096
    embed_dim = 512
    e8_codebook = torch.randn(240, 8, device=device, dtype=torch.float32)

    configs = [
        {"num_paths": 4, "depth": 2},
        {"num_paths": 4, "depth": 4},
        {"num_paths": 8, "depth": 4},
        {"num_paths": 8, "depth": 6},
        {"num_paths": 16, "depth": 4},
        {"num_paths": 16, "depth": 8},
    ]

    results = []

    for cfg in configs:
        P = cfg["num_paths"]
        K = cfg["depth"]
        num_blocks = embed_dim // 8

        candidate_paths = torch.randint(0, vocab_size, (P, K), device=device, dtype=torch.int64)
        target_logits = torch.randn(P, K + 1, vocab_size, device=device, dtype=torch.float32)
        # bias target logits towards candidate path to simulate realistic speculative acceptance
        for p in range(P):
            for k in range(K):
                target_logits[p, k, candidate_paths[p, k]] += 5.0

        e8_root_indices = torch.randint(0, 240, (P, num_blocks), device=device, dtype=torch.uint8)
        current_hidden = torch.randn(embed_dim, device=device, dtype=torch.float32)

        # Warmup
        for _ in range(5):
            _ = fused_e8_polytope_speculative_verify(candidate_paths, target_logits, e8_root_indices, e8_codebook, current_hidden)
        torch.cuda.synchronize()

        trials = 50
        t0 = time.perf_counter()
        for _ in range(trials):
            accepted_tokens, accepted_count, best_path = fused_e8_polytope_speculative_verify(
                candidate_paths, target_logits, e8_root_indices, e8_codebook, current_hidden
            )
        torch.cuda.synchronize()
        latency_us = ((time.perf_counter() - t0) / trials) * 1e6

        accept_rate = accepted_count / float(K)
        # Speculative effective speedup factor
        effective_speedup = (1.0 + accepted_count) / (1.0 + (latency_us / 400.0))

        results.append({
            "num_paths": P,
            "depth": K,
            "latency_us": round(latency_us, 2),
            "accepted_count": accepted_count,
            "accept_rate": round(accept_rate, 2),
            "effective_speedup": round(effective_speedup, 2)
        })

    best = max(results, key=lambda x: x["effective_speedup"])

    print(f"\n[✓] Autotuning Complete across {len(results)} speculative configurations.")
    print(f"    Optimal Config: {best['num_paths']} Tree Paths | Depth K = {best['depth']}")
    print(f"    Kernel Latency: {best['latency_us']} us | Accepted Tokens: {best['accepted_count']}/{best['depth']} ({best['accept_rate']*100:.1f}%)")
    print(f"    Effective Speculative Speedup: {best['effective_speedup']:.2f}x")
    print("=" * 80)

    print(f"  {'Paths':<6} | {'Depth (K)':<10} | {'Latency (us)':<14} | {'Accepted Tokens':<18} | {'Effective Speedup':<16}")
    print("  " + "-" * 72)
    for r in results:
        print(f"  {r['num_paths']:<6} | {r['depth']:<10} | {r['latency_us']:<14} | {r['accepted_count']}/{r['depth']} ({r['accept_rate']*100:4.1f}%)         | {r['effective_speedup']:5.2f}x")

    return best

if __name__ == "__main__":
    run_specdec_autotuner()
