"""
scripts/imf_flagship_resume_infer.py
Unified bridge for running inference with the internal IMF Flagship Model (125M MoPE + 15M Drafter).
Takes a prompt (or conversation history extracted from Antigravity) and continues reasoning/coding.
"""

import sys
import os
import json
import argparse
import torch

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(project_root, "scripts/training"))
sys.path.insert(0, project_root)

from imf.code_bpe_tokenizer import CodeBPETokenizer
from train_flagship_omnilm_mope import IMFOmniLMMoPE
from imf.speculative_polytope_decoder import SpeculativePolytopeDecoder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=str, required=True)
    parser.add_argument("--max_tokens", type=int, default=48)
    parser.add_argument("--model", choices=["imf_125m_grpo", "imf_125m_omni"], default="imf_125m_grpo")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok_path = os.path.join(project_root, "dist/hf_flagship_bundle/code_bpe_tokenizer.json")
    target_path = os.path.join(
        project_root,
        "dist/hf_flagship_bundle",
        "imf_scaled_125m_grpo_rl.pt" if args.model == "imf_125m_grpo" else "imf_scaled_125m_omni118.pt"
    )
    drafter_path = os.path.join(project_root, "dist/hf_flagship_bundle/imf_drafter_distilled_15m.pt")

    tok = CodeBPETokenizer.load(tok_path)
    v_size = len(tok.vocab)

    target = IMFOmniLMMoPE(
        vocab_size=v_size, d_model=256, num_layers=4, num_heads=8,
        polytope_dim=5, num_experts=32, top_k=4, max_seq_len=128, alpha_recon=0.3
    ).to(device)
    target.load_state_dict(torch.load(target_path, map_location=device, weights_only=False), strict=False)
    target.eval()

    drafter = IMFOmniLMMoPE(
        vocab_size=v_size, d_model=128, num_layers=2, num_heads=4,
        polytope_dim=5, num_experts=8, top_k=2, max_seq_len=128, alpha_recon=0.1
    ).to(device)
    drafter.load_state_dict(torch.load(drafter_path, map_location=device, weights_only=False), strict=False)
    drafter.eval()

    p_ids = tok.encode(args.prompt)
    if not p_ids:
        p_ids = [0]
    # Keep last 64 tokens to fit context
    if len(p_ids) > 64:
        p_ids = p_ids[-64:]

    x = torch.tensor([p_ids], device=device, dtype=torch.long)
    decoder = SpeculativePolytopeDecoder(target_model=target, drafter_model=drafter, gamma=4, temperature=0.7)
    out_ids, stats = decoder.generate_speculative(x, max_new_tokens=args.max_tokens)
    new_tokens = out_ids[0][len(p_ids):].tolist()
    text = tok.decode(new_tokens)

    output = {
        "success": True,
        "model": f"IMF Flagship 125M ({args.model})",
        "response": text,
        "stats": stats
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
