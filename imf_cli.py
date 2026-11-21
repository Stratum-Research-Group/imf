"""
IMF Live Interactive Inspection & Manifold Chat Terminal.
Runs interactive chat or single-prompt inspection against IMF-107.7M Flagship
and IMF-4.35M Distilled Drafter with live Polytope vertex activation display.
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import sys
import time
import argparse
import torch
import torch.nn.functional as F

from imf.code_bpe_tokenizer import CodeBPETokenizer
from train_flagship_omnilm_mope import IMFOmniLMMoPE
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.speculative_polytope_decoder import SpeculativePolytopeDecoder


def load_imf_fluency_system(device: str = "cuda"):
    tok = CodeBPETokenizer.load("checkpoints/hybrid_bpe_tokenizer_4k.json")
    vocab_size = len(tok.vocab)
    model = IMFJointReconPredictorLM(
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
    state_dict = torch.load("checkpoints/imf_fluency_lm_4k.pt", map_location=device)
    model.load_state_dict(state_dict)
    model.eval()
    return tok, model


def load_imf_system(device: str = "cuda"):
    tok = CodeBPETokenizer.load("checkpoints/code_bpe_tokenizer.json")
    vocab_size = len(tok.vocab)

    # 1. Target Model
    target = IMFOmniLMMoPE(
        vocab_size=vocab_size,
        d_model=256,
        num_layers=4,
        num_heads=8,
        polytope_dim=5,
        num_experts=32,
        top_k=4,
        max_seq_len=128,
        alpha_recon=0.3,
    ).to(device)
    target.load_state_dict(torch.load("checkpoints/imf_scaled_125m_omni118.pt", map_location=device))
    target.eval()

    # 2. Distilled Drafter
    drafter = IMFOmniLMMoPE(
        vocab_size=vocab_size,
        d_model=128,
        num_layers=2,
        num_heads=4,
        polytope_dim=5,
        num_experts=8,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.1,
    ).to(device)
    drafter.load_state_dict(torch.load("checkpoints/imf_drafter_distilled_15m.pt", map_location=device))
    drafter.eval()

    return tok, target, drafter


def inspect_fluency_generation(prompt: str, max_tokens: int = 48, temperature: float = 0.7):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok, model = load_imf_fluency_system(device)

    p_ids = tok.encode(prompt)
    curr = torch.tensor([p_ids], device=device, dtype=torch.long)

    print("\n" + "=" * 76)
    print(f"IMF Fluency Inspection (4K BPE, 129.8M Joint-Recon): {prompt}")
    print("=" * 76)

    t0 = time.perf_counter()
    with torch.no_grad():
        for _ in range(max_tokens):
            logits, _, metrics = model(curr)
            next_logits = logits[:, -1, :].clone()
            
            # Simple repetition penalty
            for tid in set(curr[0].tolist()):
                if next_logits[0, tid] > 0:
                    next_logits[0, tid] /= 1.2
                else:
                    next_logits[0, tid] *= 1.2

            if temperature > 0.0:
                # Top-k sampling
                val, idx = torch.topk(next_logits, min(40, next_logits.size(-1)))
                probs = F.softmax(val / temperature, dim=-1)
                choice = torch.multinomial(probs, num_samples=1)
                nxt = torch.gather(idx, -1, choice)
            else:
                nxt = next_logits.argmax(dim=-1, keepdim=True)

            curr = torch.cat([curr, nxt], dim=1)

    dt = time.perf_counter() - t0
    gen_text = tok.decode(curr[0].tolist())

    print(f"Metrics: Latent Variance = {metrics.get('latent_var', 0.0):.4f} | Eff Rank = {metrics.get('eff_rank', 0.0)}")
    print(f"Throughput: {max_tokens / dt:.1f} tok/s ({max_tokens} tokens in {dt*1000:.1f}ms)")
    print("\nGenerated Output:")
    print("-" * 50)
    print(gen_text)
    print("-" * 50)


def inspect_generation(prompt: str, max_tokens: int = 32, use_speculative: bool = True):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok, target, drafter = load_imf_system(device)

    p_ids = tok.encode(prompt)
    x = torch.tensor([p_ids], device=device, dtype=torch.long)

    print("\n" + "=" * 76)
    print(f"IMF Manifold Inspection: {prompt}")
    print("=" * 76)

    # Forward pass to inspect latent polytope geometry
    with torch.no_grad():
        with torch.amp.autocast("cuda", dtype=torch.bfloat16):
            logits, _, metrics = target(x)
            recon_loss = metrics.get("loss_recon", torch.tensor(0.0)).item()
            balance_loss = metrics.get("balance_loss", torch.tensor(0.0)).item()

    print(f"Latent Manifold Metrics:")
    print(f"  • Simplex Reconstruction Loss: {recon_loss:.4f}")
    print(f"  • Expert Balance Penalty:      {balance_loss:.4f}")

    if use_speculative:
        decoder = SpeculativePolytopeDecoder(target_model=target, drafter_model=drafter, gamma=4, temperature=0.0)
        t0 = time.perf_counter()
        out_ids, stats = decoder.generate_speculative(x, max_new_tokens=max_tokens)
        dt = time.perf_counter() - t0
        text = tok.decode(out_ids[0].tolist())
        print(f"\nSpeculative Decoding (gamma=4):")
        print(f"  • Throughput:      {stats['throughput_tok_per_sec']:.1f} tok/s ({stats['generated_tokens']} tokens in {dt*1000:.1f}ms)")
        print(f"  • Acceptance Rate: {stats['acceptance_rate']*100:.1f}%")
        print(f"  • Steps Taken:     {stats['speculative_steps']}")
    else:
        curr = x.clone()
        t0 = time.perf_counter()
        with torch.no_grad():
            for _ in range(max_tokens):
                l, _, _ = target(curr)
                nxt = l[:, -1, :].argmax(dim=-1, keepdim=True)
                curr = torch.cat([curr, nxt], dim=1)
        dt = time.perf_counter() - t0
        text = tok.decode(curr[0].tolist())
        print(f"\nStandalone Autoregressive Decoding:")
        print(f"  • Throughput:      {max_tokens / dt:.1f} tok/s ({max_tokens} tokens in {dt*1000:.1f}ms)")

    print("\nGenerated Output:")
    print("-" * 50)
    print(text)
    print("-" * 50)


def interactive_chat():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[*] Initializing IMF Terminal Shell on {device}...")
    tok, target, drafter = load_imf_system(device)
    decoder = SpeculativePolytopeDecoder(target_model=target, drafter_model=drafter, gamma=4, temperature=0.0)

    print("\n[✓] IMF Terminal Shell Ready! (Type 'exit' or 'quit' to leave)\n")
    while True:
        try:
            prompt = input("imf> ")
            if prompt.strip().lower() in ("exit", "quit", "q"):
                break
            if not prompt.strip():
                continue

            p_ids = tok.encode(prompt)
            x = torch.tensor([p_ids], device=device, dtype=torch.long)
            out_ids, stats = decoder.generate_speculative(x, max_new_tokens=32)
            gen_text = tok.decode(out_ids[0, len(p_ids):].tolist())
            print(f"response> {gen_text.strip()}  [{stats['throughput_tok_per_sec']:.1f} tok/s, accept={stats['acceptance_rate']*100:.1f}%]\n")
        except (KeyboardInterrupt, EOFError):
            break
    print("\nExiting IMF Terminal Shell.")


def main():
    parser = argparse.ArgumentParser(description="IMF Live Terminal & Inspection CLI")
    subparsers = parser.add_subparsers(dest="subcommand", help="Sub-commands")

    # 'chat' / default inspection options
    parser.add_argument("--prompt", type=str, default=None, help="Single prompt to inspect")
    parser.add_argument("--tokens", type=int, default=32, help="Tokens to generate")
    parser.add_argument("--speculative", action="store_true", default=True, help="Use speculative decoding")
    parser.add_argument("--fluency", action="store_true", default=False, help="Use the 4K BPE hybrid fluency model")
    parser.add_argument("--temp", type=float, default=0.7, help="Temperature for fluency sampling")

    # 'convert' sub-command
    convert_parser = subparsers.add_parser("convert", help="Convert external container formats (.weft <-> .imf)")
    convert_parser.add_argument("input", type=str, help="Input file path (e.g. model.weft or model.imf)")
    convert_parser.add_argument("-o", "--output", type=str, default=None, help="Output file path")
    convert_parser.add_argument(
        "--direction",
        choices=["auto", "weft2imf", "imf2weft"],
        default="auto",
        help="Conversion direction (auto detects from file extensions)",
    )
    convert_parser.add_argument(
        "--mode",
        choices=["factorized", "reconstructed"],
        default="factorized",
        help="Conversion mode for weft2imf: 'factorized' (sub-bit bitboards) or 'reconstructed' (dense FP16/FP32 weights)",
    )
    convert_parser.add_argument(
        "--rank",
        type=int,
        default=32,
        help="Binarization rank for imf2weft when binarizing dense weights",
    )

    args = parser.parse_args()

    if args.subcommand == "convert":
        in_p = Path(args.input)
        direction = args.direction
        if direction == "auto":
            if in_p.suffix.lower() == ".weft":
                direction = "weft2imf"
            elif in_p.suffix.lower() == ".imf":
                direction = "imf2weft"
            else:
                raise ValueError("Could not auto-detect conversion direction. Specify --direction weft2imf or imf2weft.")

        if direction == "weft2imf":
            from imf.weft_to_imf_converter import convert_weft_to_imf
            out_path = args.output or str(in_p.with_suffix(".imf"))
            convert_weft_to_imf(str(in_p), out_path, mode=args.mode)
        elif direction == "imf2weft":
            from imf.imf_to_weft_converter import convert_imf_to_weft
            out_path = args.output or str(in_p.with_suffix(".weft"))
            convert_imf_to_weft(str(in_p), out_path, rank=args.rank)
        return

    if args.prompt:
        if args.fluency:
            inspect_fluency_generation(args.prompt, max_tokens=args.tokens, temperature=args.temp)
        else:
            inspect_generation(args.prompt, max_tokens=args.tokens, use_speculative=args.speculative)
    else:
        interactive_chat()


if __name__ == "__main__":
    main()
