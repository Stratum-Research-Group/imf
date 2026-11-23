"""
Benchmark Evaluation for Multi-Step Planning and Modern UI Design Flare.
Measures perplexity on:
1. Complex Multi-Step Linguistic Goal Planning (<plan>)
2. Modern UI & CSS Palette Commitment (<design>)
3. Full Single-Page App Web Code with Procedural SVG Assets (<code>)
"""

import os
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["MKL_NUM_THREADS"] = "2"
import time
import math
import torch
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.imf_model_loader import load_imf_state_dict

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 80)
    print("  IMF 1.14B: MULTI-STEP PLANNING & UI DESIGN FLARE EVALUATION")
    print(f"  Device: {torch.cuda.get_device_name(0)} | VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    print("=" * 80)

    tok = CodeBPETokenizer.load("checkpoints/hybrid_bpe_tokenizer_4k.json")
    vocab_size = len(tok.vocab)

    model = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=576,
        num_layers=16,
        num_heads=8,
        polytope_dim=8,
        num_experts=16,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.2,
    ).to(device)

    print("[*] Loading updated container from checkpoints/imf_foundation_1b.imf...")
    sd = load_imf_state_dict("checkpoints/imf_foundation_1b.imf", device=device)
    model.load_state_dict(sd, strict=False)
    del sd
    model.eval()

    eval_splits = {
        "Goal Planning & Ambiguity Resolution (<plan>)": (
            "<plan>\n"
            "1. User Goal: Modern dark-mode SaaS landing page for AI financial analytics.\n"
            "2. Architecture: Responsive single-page application using modern CSS and semantic HTML5.\n"
            "3. Core Components:\n"
            "   - Hero section with gradient typography and live call-to-action.\n"
            "   - Procedural SVG financial growth chart vector illustration.\n"
            "   - Interactive 3-tier pricing grid with hover effects.\n"
            "</plan>\n"
        ),
        "UI Aesthetic & Palette Formulation (<design>)": (
            "<design>\n"
            "- Palette: Deep obsidian (#0b0f19), Electric Cyan (#00f2fe), Neon Indigo (#6366f1).\n"
            "- Typography: Clean sans-serif, -apple-system / Inter hierarchy.\n"
            "- Visual Flare: Subtle glassmorphism (backdrop-filter: blur), 1px gradient borders.\n"
            "</design>\n"
        ),
        "Full SPA Code & SVG Artwork (<code>)": (
            "<code>\n"
            "<!DOCTYPE html>\n"
            "<html lang=\"en\">\n"
            "<head>\n"
            "  <style>\n"
            "    body { background: #0b0f19; color: #fff; font-family: system-ui; }\n"
            "    .btn { background: linear-gradient(135deg, #00f2fe, #6366f1); border-radius: 20px; }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <svg width=\"100\" height=\"100\"><circle cx=\"50\" cy=\"50\" r=\"40\" fill=\"#00f2fe\"/></svg>\n"
            "</body>\n"
            "</html>\n"
            "</code>\n"
        )
    }

    print("\n" + "=" * 80)
    print(f"{'Planning / Design Phase':<45} | {'Tokens':<8} | {'Loss':<10} | {'Perplexity':<10}")
    print("-" * 80)

    total_loss = 0.0
    total_tokens = 0
    scores = {}

    for phase_name, text in eval_splits.items():
        tokens = tok.encode(text)[:128]
        if len(tokens) < 2:
            continue
        x = torch.tensor([tokens[:-1]], dtype=torch.long, device=device)
        y = torch.tensor([tokens[1:]], dtype=torch.long, device=device)

        with torch.no_grad():
            with torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16):
                _, _, metrics = model(x, targets=y)
                loss = metrics["loss_pred"].item()
                ppl = math.exp(min(loss, 20.0))
                scores[phase_name] = (loss, ppl, len(tokens))
                total_loss += loss * len(tokens)
                total_tokens += len(tokens)

        print(f"{phase_name:<45} | {len(tokens):<8} | {loss:<10.4f} | {ppl:<10.2f}")

    print("-" * 80)
    avg_loss = total_loss / max(1, total_tokens)
    avg_ppl = math.exp(min(avg_loss, 20.0))
    print(f"{'MACRO-AVERAGE (Planning & Design)':<45} | {total_tokens:<8} | {avg_loss:<10.4f} | {avg_ppl:<10.2f}")
    print("=" * 80)

if __name__ == "__main__":
    main()
