#!/usr/bin/env python3
"""
Fast, direct CLI & Python interface for IMF Foundation 1.14B Coprocessor.
Loads checkpoints/imf_foundation_1b.imf and provides single-prompt or interactive generation.
"""

import sys
import os
import time
import torch

from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.imf_model_loader import load_imf_state_dict

_GLOBAL_MODEL = None
_GLOBAL_TOK = None
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

def get_engine():
    global _GLOBAL_MODEL, _GLOBAL_TOK, _DEVICE
    if _GLOBAL_MODEL is not None:
        return _GLOBAL_MODEL, _GLOBAL_TOK, _DEVICE

    tok_path = "checkpoints/hybrid_bpe_tokenizer_4k.json"
    ckpt_path = "checkpoints/imf_foundation_1b.imf"
    
    if not os.path.exists(ckpt_path):
        raise FileNotFoundError(f"Missing {ckpt_path}")
        
    _GLOBAL_TOK = CodeBPETokenizer.load(tok_path)
    vocab_size = len(_GLOBAL_TOK.vocab)

    _GLOBAL_MODEL = IMFJointReconPredictorLM(
        vocab_size=vocab_size,
        d_model=576,
        num_layers=16,
        num_heads=8,
        polytope_dim=8,
        num_experts=16,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.2,
    ).to(_DEVICE)

    sd = load_imf_state_dict(ckpt_path, device=_DEVICE)
    _GLOBAL_MODEL.load_state_dict(sd, strict=False)
    _GLOBAL_MODEL.eval()
    return _GLOBAL_MODEL, _GLOBAL_TOK, _DEVICE

def generate(prompt: str, max_tokens: int = 64, temperature: float = 0.7) -> str:
    model, tok, device = get_engine()
    input_ids = torch.tensor([tok.encode(prompt)], dtype=torch.long, device=device)
    generated = list(input_ids[0].cpu().numpy())
    curr = input_ids

    with torch.no_grad():
        for _ in range(max_tokens):
            pred_logits, recon_logits, metrics = model(curr)
            logits = pred_logits[:, -1, :] / max(temperature, 1e-4)
            probs = torch.softmax(logits, dim=-1)
            # Sample or greedy
            if temperature < 0.1:
                next_tok = torch.argmax(probs, dim=-1, keepdim=True)
            else:
                next_tok = torch.multinomial(probs, num_samples=1)
                
            tok_id = next_tok.item()
            generated.append(tok_id)
            curr = torch.cat([curr, next_tok], dim=1)
            if curr.size(1) > 128:
                curr = curr[:, -128:]

    return tok.decode(generated)

if __name__ == "__main__":
    prompt = sys.argv[1] if len(sys.argv) > 1 else "State the theorem: In any group G"
    print(f"[*] Prompt: {prompt}")
    t0 = time.time()
    out = generate(prompt, max_tokens=32, temperature=0.6)
    t1 = time.time()
    print(f"[*] Output: {out}")
    print(f"[*] Time taken: {t1 - t0:.2f}s")
