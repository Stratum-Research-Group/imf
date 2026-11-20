"""
IMF Interactive Developer REPL with Live Compiler Verification.

Usage:
    uv run python repl_imf.py
"""

import os
import sys
import torch

from train_flagship_omnilm_mope import IMFOmniLMMoPE
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.execution_verifier import MultiLanguageExecutionVerifier


def run_repl():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 70)
    print("   IMF (Interaction Model Foundations) Developer REPL v0.5.0")
    print("   Polytope Mixture-of-Experts with Live Compiler Verification")
    print(f"   Hardware Accelerator: {device}")
    print("=" * 70)

    tok_path = "checkpoints/code_bpe_tokenizer.json"
    ckpt_path = "checkpoints/imf_omnilm_mope_flagship.pt"

    tokenizer = CodeBPETokenizer.load(tok_path)
    model = IMFOmniLMMoPE(
        vocab_size=len(tokenizer.vocab),
        d_model=128,
        num_layers=2,
        num_heads=4,
        polytope_dim=3,
        num_experts=4,
        top_k=2,
        max_seq_len=256,
        alpha_recon=0.3,
    ).to(device)
    model.load_state_dict(torch.load(ckpt_path, map_location=device, weights_only=True))
    model.eval()

    verifier = MultiLanguageExecutionVerifier()

    print("\nSupported Modes:")
    print("  :py <prompt>    - Generate and compile Python code")
    print("  :rs <prompt>    - Generate and verify Rust systems code")
    print("  :lean <prompt>  - Generate and check formal Lean 4 tactic proofs")
    print("  :exit or :q     - Terminate REPL\n")

    while True:
        try:
            line = input("IMF> ").strip()
            if not line:
                continue
            if line in [":q", ":exit", "exit", "quit"]:
                print("Exiting IMF REPL.")
                break

            domain = "python"
            prompt = line
            if line.startswith(":py "):
                domain = "python"
                prompt = line[4:].strip()
            elif line.startswith(":rs "):
                domain = "rust"
                prompt = line[4:].strip()
            elif line.startswith(":lean "):
                domain = "lean4"
                prompt = line[6:].strip()

            tokens = tokenizer.encode(prompt)
            x = torch.tensor([tokens], dtype=torch.long, device=device)

            with torch.no_grad():
                pred_l, _, _ = model(x)
                pred_toks = pred_l.squeeze(0).argmax(dim=-1).tolist()

            # Autoregressively combine prompt with greedy completion
            output_tokens = tokens + pred_toks[len(tokens) - 1:]
            code_out = tokenizer.decode(output_tokens)

            print("\n[Generated Output]:")
            print(code_out)

            # Live Verification
            ok, msg = verifier.verify_sample(code_out, domain=domain)
            status = "✓ PASSED" if ok else "✗ COMPILATION FAILED"
            print(f"\n[Verification]: {status} - {msg}\n" + "-" * 70)

        except KeyboardInterrupt:
            print("\nExiting.")
            break


if __name__ == "__main__":
    run_repl()
