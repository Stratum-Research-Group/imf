"""
Inspect Polytope Mixture-of-Experts (MoPE) Routing Dynamics.

Given any user prompt (Python, Rust, Lean 4, or Math), visualizes which
domain expert is selected by the Poincaré hyperbolic router and displays
the geodesic gating probability mass.
"""

import argparse
import torch
import torch.nn.functional as F

from train_flagship_omnilm_mope import IMFOmniLMMoPE
from imf.code_bpe_tokenizer import CodeBPETokenizer


def inspect_routing(prompt: str, ckpt_path: str = "checkpoints/imf_omnilm_mope_flagship.pt"):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok_path = "checkpoints/code_bpe_tokenizer.json"
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

    tokens = tokenizer.encode(prompt)
    x = torch.tensor([tokens], dtype=torch.long, device=device)

    # Hook intermediate MoE layers to extract routing weights
    with torch.no_grad():
        B, T = x.shape
        h = model.tok_embed(x) + model.pos_embed[:, :T, :]
        for l_idx, (omni, moe) in enumerate(zip(model.layers, model.moe_layers)):
            h = omni(h)
            _, aux = moe(h)
            probs = aux["routing_probs"].squeeze(0) # [T, num_experts]
            domains = aux["expert_domains"]

            print(f"\n{'='*75}")
            print(f" MoPE Layer {l_idx} Routing Weights across {len(domains)} Domain Centroids")
            print(f"{'='*75}")
            print(f"{'Token':<18} | " + " | ".join([f"{d[:12]:<12}" for d in domains]))
            print("-" * 75)

            for t_idx in range(min(T, 15)):
                tok_str = repr(tokenizer.inverse_vocab.get(tokens[t_idx], "<unk>"))[:16]
                p_vals = probs[t_idx].tolist()
                row = f"{tok_str:<18} | " + " | ".join([f"{p*100:>10.1f}%" for p in p_vals])
                print(row)
            if T > 15:
                print(f"... ({T - 15} more tokens omitted)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=str, default="def binary_search(arr: list[int]):")
    args = parser.parse_args()
    inspect_routing(args.prompt)
