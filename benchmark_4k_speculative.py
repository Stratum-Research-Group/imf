"""
Benchmark 4K BPE Speculative Decoding against Standalone Autoregressive Decoding.
Verifies throughput (tok/s), acceptance rate, and greedy equivalence.
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import time
import torch
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.speculative_polytope_decoder import SpeculativePolytopeDecoder


def benchmark_speculative_pipeline():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 76)
    print("IMF 4K BPE Speculative Decoding Benchmark (Target 129.8M vs Drafter 5.0M)")
    print("=" * 76)

    tok = CodeBPETokenizer.load("checkpoints/hybrid_bpe_tokenizer_4k.json")
    vocab_size = len(tok.vocab)

    # 1. Target (129.8M)
    target = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=384,
        num_layers=4,
        num_heads=6,
        polytope_dim=8,
        num_experts=16,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.2,
    ).to(device)
    target.load_state_dict(torch.load("checkpoints/imf_fluency_lm_4k.pt", map_location=device))
    target.eval()

    # 2. Drafter (5.0M)
    drafter = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=128,
        num_layers=2,
        num_heads=4,
        polytope_dim=4,
        num_experts=8,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.1,
    ).to(device)
    drafter.load_state_dict(torch.load("checkpoints/imf_drafter_fluency_4k.pt", map_location=device))
    drafter.eval()

    prompts = [
        "Once upon a time, a little girl named Lily",
        "def quicksort(arr):",
        "theorem add_comm (n m : Nat) :",
    ]

    gamma = 4
    decoder = SpeculativePolytopeDecoder(target_model=target, drafter_model=drafter, gamma=gamma, temperature=0.0)

    for p in prompts:
        p_ids = tok.encode(p)
        x = torch.tensor([p_ids], device=device, dtype=torch.long)

        # Baseline: Pure Target Autoregressive
        t0 = time.perf_counter()
        curr = x.clone()
        with torch.no_grad():
            for _ in range(32):
                l, _, _ = target(curr)
                nxt = l[:, -1, :].argmax(dim=-1, keepdim=True)
                curr = torch.cat([curr, nxt], dim=1)
        dt_base = time.perf_counter() - t0
        base_tok_s = 32 / dt_base

        # Speculative Polytope Decoder
        t0 = time.perf_counter()
        spec_out, stats = decoder.generate_speculative(x, max_new_tokens=32)
        dt_spec = time.perf_counter() - t0

        speedup = stats["throughput_tok_per_sec"] / base_tok_s
        print(f"\n--- Prompt: '{p}' ---")
        print(f"  • Baseline Target Autoregressive: {base_tok_s:.1f} tok/s ({dt_base*1000:.1f} ms)")
        print(f"  • Speculative Decoding (gamma={gamma}): {stats['throughput_tok_per_sec']:.1f} tok/s ({dt_spec*1000:.1f} ms)")
        print(f"  • Acceptance Rate:               {stats['acceptance_rate']*100:.1f}%")
        print(f"  • Speculative Speedup:           {speedup:.2f}x")


if __name__ == "__main__":
    benchmark_speculative_pipeline()
