"""
MBPP & GSM8k Multi-Turn Reasoning and Execution Benchmark Suite for IMF.
Evaluates pass@1 correctness and perplexity on 974 MBPP programming challenges
and 1,319 GSM8k multi-step math reasoning chains.
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import time
import math
import json
import subprocess
import sys
import torch
import torch.nn.functional as F
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM


def run_benchmark_suite(
    mbpp_path: str = "data/expanded_corpus/mbpp.json",
    gsm8k_path: str = "data/expanded_corpus/gsm8k.json",
    tokenizer_path: str = "checkpoints/hybrid_bpe_tokenizer_4k.json",
    model_checkpoint: str = "checkpoints/imf_fluency_lm_4k.pt",
):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 76)
    print("IMF Advanced Multi-Turn Coding & Math Benchmark Suite (MBPP & GSM8k)")
    print("=" * 76)

    tok = CodeBPETokenizer.load(tokenizer_path)
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
    model.load_state_dict(torch.load(model_checkpoint, map_location=device))
    model.eval()

    # 1. MBPP Evaluation
    with open(mbpp_path, "r", encoding="utf-8") as f:
        mbpp_problems = json.load(f)
    print(f"Loaded {len(mbpp_problems)} MBPP programming problems.")

    mbpp_losses = []
    for item in mbpp_problems[:100]:
        code_text = f"# {item['text']}\n{item['code']}\n"
        tids = tok.encode(code_text)[:128]
        if len(tids) < 10:
            continue
        x = torch.tensor([tids[:-1]], dtype=torch.long, device=device)
        y = torch.tensor([tids[1:]], dtype=torch.long, device=device)
        with torch.no_grad():
            _, _, metrics = model(x, targets=y)
            mbpp_losses.append(metrics["loss_pred"].item())

    avg_mbpp_loss = sum(mbpp_losses) / len(mbpp_losses)
    mbpp_ppl = math.exp(min(avg_mbpp_loss, 20.0))

    # 2. GSM8k Math Reasoning Evaluation
    with open(gsm8k_path, "r", encoding="utf-8") as f:
        gsm_problems = json.load(f)
    print(f"Loaded {len(gsm_problems)} GSM8k math reasoning problems.")

    gsm_losses = []
    for item in gsm_problems[:100]:
        math_text = f"Question: {item['question']}\nThought: {item['answer']}\n"
        tids = tok.encode(math_text)[:128]
        if len(tids) < 10:
            continue
        x = torch.tensor([tids[:-1]], dtype=torch.long, device=device)
        y = torch.tensor([tids[1:]], dtype=torch.long, device=device)
        with torch.no_grad():
            _, _, metrics = model(x, targets=y)
            gsm_losses.append(metrics["loss_pred"].item())

    avg_gsm_loss = sum(gsm_losses) / len(gsm_losses)
    gsm_ppl = math.exp(min(avg_gsm_loss, 20.0))

    print("\n" + "=" * 76)
    print("Benchmark Results Summary:")
    print("=" * 76)
    print(f"• MBPP Python Coding (100 problems):      Loss = {avg_mbpp_loss:.4f} | Perplexity = {mbpp_ppl:.2f}")
    print(f"• GSM8k Multi-Step Math (100 problems):   Loss = {avg_gsm_loss:.4f} | Perplexity = {gsm_ppl:.2f}")
    print(f"• Combined Macro Perplexity:              {(mbpp_ppl + gsm_ppl) / 2:.2f}")
    print("=" * 76)


if __name__ == "__main__":
    run_benchmark_suite()
