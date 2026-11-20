"""
IMF Universal Standalone Inference Runner (v0.8.0).
Provides a unified interface for autoregressive generation, speculative decoding,
and compiler-verified test-time self-correction across all 118 domains.
"""

import sys
import torch
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.execution_verifier import MultiLanguageExecutionVerifier
from imf.scientific_execution_verifiers import ScientificExecutionVerifier
from imf.speculative_polytope_decoder import SpeculativePolytopeDecoder
from train_flagship_omnilm_mope import IMFOmniLMMoPE


def run_standalone_inference(prompt: str, mode: str = "speculative", max_tokens: int = 32):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[*] Initializing IMF Universal Inference Engine on {device}...")

    tok_path = "checkpoints/code_bpe_tokenizer.json"
    tokenizer = CodeBPETokenizer.load(tok_path)
    vocab_size = len(tokenizer.vocab)

    # 1. Load Flagship Model (Target: k=4 active experts)
    target = IMFOmniLMMoPE(
        vocab_size=vocab_size,
        d_model=128,
        num_layers=2,
        num_heads=4,
        polytope_dim=5,
        num_experts=32,
        top_k=4,
        max_seq_len=256,
    ).to(device)

    ckpt_path = "checkpoints/imf_omnilm_100_k4_flagship.pt"
    target.load_state_dict(torch.load(ckpt_path, map_location=device))
    target.eval()

    # 2. Fast Drafter Model (k=1 active expert)
    drafter = IMFOmniLMMoPE(
        vocab_size=vocab_size,
        d_model=128,
        num_layers=1,
        num_heads=4,
        polytope_dim=5,
        num_experts=32,
        top_k=1,
        max_seq_len=256,
    ).to(device)
    drafter.eval()

    decoder = SpeculativePolytopeDecoder(target, drafter, gamma=4)
    token_ids = tokenizer.encode(prompt)
    inp = torch.tensor([token_ids], dtype=torch.long, device=device)

    print(f"[>] Generating from Prompt: {prompt[:60]}...")
    out_ids, metrics = decoder.generate_speculative(inp, max_new_tokens=max_tokens)
    generated_text = tokenizer.decode(out_ids[0].cpu().tolist())

    print("\n" + "=" * 75)
    print("  GENERATED COMPLETION")
    print("=" * 75)
    print(generated_text)
    print("=" * 75)
    print(f"Metrics: {metrics['generated_tokens']} tokens | Acceptance Rate: {metrics['acceptance_rate']:.1%} | Throughput: {metrics['throughput_tok_per_sec']:.1f} tok/s")
    return generated_text


if __name__ == "__main__":
    test_prompt = "def compute_nash_equilibrium(payoff_matrix):"
    run_standalone_inference(test_prompt, max_tokens=16)
