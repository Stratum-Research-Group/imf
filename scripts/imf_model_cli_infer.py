"""
scripts/imf_model_cli_infer.py
Unified CLI inference bridge for native IMF models and Hugging Face checkpoints.
Allows imf_gui to spawn and query any model on disk (IMF 125M, 15M, HF Qwen-0.5B, DeepSeek-R1-1.5B, etc.).
"""

import sys
import json
import argparse
import torch
from pathlib import Path


def infer_imf_flagship(checkpoint_path: str, prompt: str, max_tokens: int = 48) -> str:
    from imf.code_bpe_tokenizer import CodeBPETokenizer
    sys.path.insert(0, "scripts/training"); from train_flagship_omnilm_mope import IMFOmniLMMoPE

    tok_path = "dist/hf_flagship_bundle/code_bpe_tokenizer.json"
    if not Path(tok_path).exists():
        tok_path = "code_bpe_tokenizer.json"

    tok = CodeBPETokenizer.load(tok_path)
    v_size = len(tok.vocab)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    if "15m" in checkpoint_path:
        model = IMFOmniLMMoPE(
            vocab_size=v_size, d_model=128, num_layers=2, num_heads=4,
            polytope_dim=5, num_experts=8, top_k=2, max_seq_len=128, alpha_recon=0.1
        ).to(device)
    else:
        model = IMFOmniLMMoPE(
            vocab_size=v_size, d_model=256, num_layers=4, num_heads=8,
            polytope_dim=5, num_experts=32, top_k=4, max_seq_len=128, alpha_recon=0.3
        ).to(device)

    model.load_state_dict(torch.load(checkpoint_path, map_location=device))
    model.eval()

    p_ids = tok.encode(prompt)
    if not p_ids:
        p_ids = [0]
    x = torch.tensor([p_ids], device=device, dtype=torch.long)

    with torch.no_grad():
        for _ in range(max_tokens):
            if x.shape[1] >= 128:
                break
            logits = model(x)
            next_tok = torch.argmax(logits[:, -1, :], dim=-1, keepdim=True)
            x = torch.cat([x, next_tok], dim=-1)

    return tok.decode(x[0].tolist())


def infer_hf_model(model_name: str, prompt: str, max_tokens: int = 64) -> str:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto" if torch.cuda.is_available() else None
    )
    inputs = tok(prompt, return_tensors="pt")
    if torch.cuda.is_available():
        inputs = {k: v.to("cuda") for k, v in inputs.items()}
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=max_tokens, do_sample=True, temperature=0.7)
    return tok.decode(out[0], skip_special_tokens=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["imf", "hf"], required=True)
    parser.add_argument("--target", type=str, required=True)
    parser.add_argument("--prompt", type=str, required=True)
    parser.add_argument("--max_tokens", type=int, default=64)
    args = parser.parse_args()

    try:
        if args.engine == "imf":
            res = infer_imf_flagship(args.target, args.prompt, args.max_tokens)
        else:
            res = infer_hf_model(args.target, args.prompt, args.max_tokens)
        print(json.dumps({"success": True, "response": res}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))


if __name__ == "__main__":
    main()
