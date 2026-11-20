"""
chat_imf.py
Interactive Streaming Chat CLI powered by IMF (Interaction Model Foundations)
Multi-Head SAVG recurrent state with O(1) step inference.

Usage:
    uv run python chat_imf.py [--checkpoint checkpoints/imf_bpe.pt] [--temp 0.8]
"""

import argparse
import sys
import time
from pathlib import Path
import torch
import torch.nn.functional as F

from imf.bpe_tokenizer import BPETokenizer
from train_imf_corpus import IMFMultiHeadLM, CharTokenizer


def stream_generate(
    model: IMFMultiHeadLM,
    tokenizer,
    prompt: str,
    max_new_tokens: int = 150,
    temperature: float = 0.7,
    top_k: int = 40,
    device: torch.device = torch.device("cpu"),
):
    """
    Stream tokens to stdout in real time using O(1) recurrent step inference.
    """
    model.eval()
    if hasattr(tokenizer, "encode"):
        input_ids = tokenizer.encode(prompt)
    else:
        input_ids = [tokenizer.char2idx.get(c, 0) for c in prompt]

    if not input_ids:
        input_ids = [0]

    # Initialize recurrent states for all layers: O(B * H * d_h^2)
    states = model.init_streaming_states(batch_size=1, device=device)

    # Prime the recurrent states with the prompt tokens
    with torch.no_grad():
        for tok_id in input_ids[:-1]:
            tok_tensor = torch.tensor([tok_id], device=device)
            _, states = model.generate_step(tok_tensor, states)

        last_tok = torch.tensor([input_ids[-1]], device=device)

        sys.stdout.write(prompt)
        sys.stdout.flush()

        curr_tok = last_tok
        generated_count = 0
        t_start = time.perf_counter()

        for _ in range(max_new_tokens):
            logits, states = model.generate_step(curr_tok, states)
            logits = logits[0] / max(temperature, 1e-5)

            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[-1]] = -float("Inf")

            probs = F.softmax(logits, dim=-1)
            next_tok_id = torch.multinomial(probs, num_samples=1).item()

            if hasattr(tokenizer, "decode"):
                token_str = tokenizer.decode([next_tok_id])
            else:
                token_str = tokenizer.idx2char.get(next_tok_id, "")

            sys.stdout.write(token_str)
            sys.stdout.flush()

            curr_tok = torch.tensor([next_tok_id], device=device)
            generated_count += 1

            if hasattr(tokenizer, "eos_id") and next_tok_id == tokenizer.eos_id:
                break

        elapsed = time.perf_counter() - t_start
        tok_per_sec = generated_count / max(elapsed, 1e-5)
        print(f"\n\n[INFO] Generated {generated_count} tokens in {elapsed:.3f}s ({tok_per_sec:.1f} tok/s, O(1) recurrent step)")


def main():
    parser = argparse.ArgumentParser(description="Interactive IMF Multi-Head SAVG Chat CLI")
    parser.add_argument("--checkpoint", type=str, default="checkpoints/imf_model.pt", help="Path to trained checkpoint")
    parser.add_argument("--temperature", type=float, default=0.75, help="Sampling temperature")
    parser.add_argument("--top_k", type=int, default=30, help="Top-k filtering")
    parser.add_argument("--max_tokens", type=int, default=120, help="Max tokens to generate per turn")
    parser.add_argument("--prompt", type=str, default="", help="Single prompt generation mode")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    ckpt_path = Path(args.checkpoint)
    if ckpt_path.exists():
        print(f"[*] Loading trained IMF checkpoint from {ckpt_path}...")
        ckpt = torch.load(ckpt_path, map_location=device)
        vocab_size = ckpt.get("vocab_size", 65)
        d_model = ckpt.get("d_model", 128)
        num_heads = ckpt.get("num_heads", 4)
        n_layers = ckpt.get("n_layers", 3)
        preset = ckpt.get("preset", "decayotton_orthoplex")
        use_higher_arity = any("arity_binding" in k for k in ckpt["model_state"].keys())
        use_continuous_simplex = any("continuous_binding" in k for k in ckpt["model_state"].keys())
        # Automatically count projection branches in arity_binding
        arity_projs = [k for k in ckpt["model_state"].keys() if "blocks.0.arity_binding.projections." in k]
        arity = len(arity_projs) if arity_projs else (3 if use_higher_arity else 3)

        if "ScaledIMFDecoderLM" in str(ckpt.get("arch", "")) or n_layers >= 6 or use_higher_arity or use_continuous_simplex:
            from train_scaled_imf import ScaledIMFDecoderLM
            model = ScaledIMFDecoderLM(
                vocab_size=vocab_size,
                d_model=d_model,
                num_heads=num_heads,
                n_layers=n_layers,
                preset=preset,
                use_higher_arity=use_higher_arity,
                use_continuous_simplex=use_continuous_simplex,
                arity=arity,
            ).to(device)
        else:
            model = IMFMultiHeadLM(vocab_size=vocab_size, d_model=d_model, num_heads=num_heads, n_layers=n_layers, preset=preset).to(device)
        model.load_state_dict(ckpt["model_state"])

        tokenizer_meta = ckpt.get("tokenizer_meta")
        if tokenizer_meta and "merges" in tokenizer_meta:
            tokenizer = BPETokenizer(vocab=tokenizer_meta["vocab"], merges=tokenizer_meta["merges"])
        elif "chars" in ckpt:
            tokenizer = CharTokenizer("".join(ckpt["chars"]))
        else:
            data_file = Path("data/tinyshakespeare.txt")
            tokenizer = CharTokenizer(data_file.read_text(encoding="utf-8")) if data_file.exists() else None
    else:
        print("[*] No saved checkpoint found. Scaffolding pretrained weights on TinyShakespeare...")
        from train_imf_corpus import load_dataset
        tokenizer, train_data, _ = load_dataset()
        vocab_size = tokenizer.vocab_size
        d_model, num_heads, n_layers = 128, 4, 3
        model = IMFMultiHeadLM(vocab_size=vocab_size, d_model=d_model, num_heads=num_heads, n_layers=n_layers, preset="decayotton_orthoplex").to(device)
        # Quick warm-up training so outputs are sensible
        print("  [>] Quick calibration training (80 steps)...")
        opt = torch.optim.AdamW(model.parameters(), lr=3e-3)
        model.train()
        from train_imf_corpus import get_batch
        for _ in range(80):
            x, y = get_batch(train_data, batch_size=16, seq_len=128, device=device)
            opt.zero_grad()
            loss = F.cross_entropy(model(x).view(-1, vocab_size), y.view(-1))
            loss.backward()
            opt.step()
        print("  [+] Model ready.")

    print("\n" + "=" * 65)
    print("   IMF (Interaction Model Foundations) Streaming Terminal")
    print("   Polytope Virtual Grid: 10D Hendecaxennon / Decayotton")
    print("   Decoding Complexity   : O(1) constant state per step")
    print("=" * 65)

    if args.prompt:
        print(f"\n[Prompt]: {args.prompt}")
        print("[Response]: ", end="", flush=True)
        stream_generate(model, tokenizer, args.prompt, max_new_tokens=args.max_tokens, temperature=args.temperature, top_k=args.top_k, device=device)
        return

    print("Type your prompt and press Enter. Type 'exit' or 'quit' to terminate.\n")
    while True:
        try:
            prompt = input("IMF > ").strip()
            if not prompt:
                continue
            if prompt.lower() in ["exit", "quit", "q"]:
                print("Exiting IMF CLI. Goodbye!")
                break

            print("IMF Response: ", end="", flush=True)
            stream_generate(
                model,
                tokenizer,
                prompt,
                max_new_tokens=args.max_tokens,
                temperature=args.temperature,
                top_k=args.top_k,
                device=device,
            )
            print()
        except KeyboardInterrupt:
            print("\nSession interrupted. Exiting.")
            break


if __name__ == "__main__":
    main()
