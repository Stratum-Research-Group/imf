"""
benchmark_1b_tree_speculative.py
Direct comparison of Linear Speculative Decoding (gamma=4) vs
Multi-Token Speculative Tree-Drafting (B=2, D=2) on the 1.14B Foundation Model.
"""

import sys
import time
from pathlib import Path
import torch

from imf.imf_model_loader import load_imf_state_dict
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.speculative_polytope_decoder import SpeculativePolytopeDecoder
from imf.polytope_tree_speculative import PolytopeTreeSpeculativeDecoder

def run_tree_vs_linear_1b():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[*] Benchmarking Linear vs Tree Speculative Decoding on 1.14B Model ({device})")

    drafter_imf = Path("checkpoints/imf_drafter_fluency_4k.imf")
    target_imf = Path("checkpoints/imf_foundation_1b.imf")

    # Load from zero-copy container
    drafter_sd = load_imf_state_dict(str(drafter_imf), device="cpu")
    target_sd = load_imf_state_dict(str(target_imf), device="cpu")

    drafter = IMFJointReconPredictorLM(
        vocab_size=4096, d_model=128, num_layers=2, num_heads=4,
        polytope_dim=4, num_experts=8, top_k=2, max_seq_len=128, alpha_recon=0.1
    ).to(device)
    drafter.load_state_dict(drafter_sd, strict=False)
    drafter.eval()

    target = IMFJointReconPredictorLM(
        vocab_size=4096, d_model=576, num_layers=16, num_heads=8,
        polytope_dim=8, num_experts=16, top_k=2, max_seq_len=128, alpha_recon=0.2
    ).to(device)
    target.load_state_dict(target_sd, strict=False)
    target.eval()

    prompt_ids = torch.randint(10, 4000, (1, 16), device=device)
    max_new_tokens = 16

    # 1. Linear Speculative Decoding (gamma=4)
    print("\n[1] Running Linear Speculative Decoder (gamma=4)...")
    linear_decoder = SpeculativePolytopeDecoder(target, drafter, gamma=4, temperature=0.0)
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    t0 = time.perf_counter()
    linear_ids, lin_metrics = linear_decoder.generate_speculative(prompt_ids, max_new_tokens=max_new_tokens)
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    t_lin = time.perf_counter() - t0
    lin_tok_sec = max_new_tokens / t_lin
    print(f"    Linear Speculative: {t_lin*1000:.2f} ms ({lin_tok_sec:.2f} tokens/sec, {lin_metrics['speculative_steps']} steps)")

    # 2. Tree Speculative Decoding (B=2, D=2)
    print("\n[2] Running Polytope Tree Speculative Decoder (B=2, D=2)...")
    tree_decoder = PolytopeTreeSpeculativeDecoder(target, drafter, tree_depth=2, branch_factor=2)
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    t1 = time.perf_counter()
    tree_ids, tree_metrics = tree_decoder.generate(prompt_ids, max_new_tokens=max_new_tokens)
    torch.cuda.synchronize() if torch.cuda.is_available() else None
    t_tree = time.perf_counter() - t1
    tree_tok_sec = max_new_tokens / t_tree
    print(f"    Tree Speculative:   {t_tree*1000:.2f} ms ({tree_tok_sec:.2f} tokens/sec, {tree_metrics['steps']} steps)")

    print(f"\n[✓] Comparison Complete:")
    print(f"    Linear Throughput: {lin_tok_sec:.2f} tok/s")
    print(f"    Tree Throughput:   {tree_tok_sec:.2f} tok/s")

if __name__ == "__main__":
    run_tree_vs_linear_1b()
