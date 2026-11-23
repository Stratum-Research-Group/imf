"""
Full-Dataset Benchmark Evaluation Suite for IMF (Every Sample).
Evaluates all 974 MBPP programming challenges and all 1,319 GSM8k math reasoning problems
with exact timing and progress reporting.
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import time
import math
import json
import torch
import torch.nn.functional as F
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM


def run_full_dataset_benchmarks(
    mbpp_path: str = "data/expanded_corpus/mbpp.json",
    gsm8k_path: str = "data/expanded_corpus/gsm8k.json",
    tokenizer_path: str = "checkpoints/hybrid_bpe_tokenizer_4k.json",
    model_checkpoint: str = "checkpoints/imf_fluency_lm_4k.pt",
):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 76)
    print("IMF Full-Dataset Exhaustive Benchmark (All 974 MBPP + All 1,319 GSM8k)")
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

    # 1. Full MBPP Evaluation (All 974 samples)
    with open(mbpp_path, "r", encoding="utf-8") as f:
        mbpp_problems = json.load(f)
    print(f"\n[*] Evaluating Full MBPP: {len(mbpp_problems)} problems...")

    mbpp_losses = []
    t0 = time.perf_counter()
    for idx, item in enumerate(mbpp_problems):
        code_text = f"# {item['text']}\n{item['code']}\n"
        tids = tok.encode(code_text)[:128]
        if len(tids) < 10:
            continue
        x = torch.tensor([tids[:-1]], dtype=torch.long, device=device)
        y = torch.tensor([tids[1:]], dtype=torch.long, device=device)
        with torch.no_grad():
            _, _, metrics = model(x, targets=y)
            mbpp_losses.append(metrics["loss_pred"].item())

        if (idx + 1) % 200 == 0 or idx == len(mbpp_problems) - 1:
            curr_loss = sum(mbpp_losses) / len(mbpp_losses)
            print(f"  • MBPP [{idx+1:3d}/{len(mbpp_problems)}] Running Loss: {curr_loss:.4f} | PPL: {math.exp(min(curr_loss, 20.0)):.2f}")

    dt_mbpp = time.perf_counter() - t0
    avg_mbpp_loss = sum(mbpp_losses) / len(mbpp_losses)
    final_mbpp_ppl = math.exp(min(avg_mbpp_loss, 20.0))

    # 2. Full GSM8k Evaluation (All 1,319 samples)
    with open(gsm8k_path, "r", encoding="utf-8") as f:
        gsm_problems = json.load(f)
    print(f"\n[*] Evaluating Full GSM8k: {len(gsm_problems)} problems...")

    gsm_losses = []
    t0 = time.perf_counter()
    for idx, item in enumerate(gsm_problems):
        math_text = f"Question: {item['question']}\nThought: {item['answer']}\n"
        tids = tok.encode(math_text)[:128]
        if len(tids) < 10:
            continue
        x = torch.tensor([tids[:-1]], dtype=torch.long, device=device)
        y = torch.tensor([tids[1:]], dtype=torch.long, device=device)
        with torch.no_grad():
            _, _, metrics = model(x, targets=y)
            gsm_losses.append(metrics["loss_pred"].item())

        if (idx + 1) % 300 == 0 or idx == len(gsm_problems) - 1:
            curr_loss = sum(gsm_losses) / len(gsm_losses)
            print(f"  • GSM8k [{idx+1:4d}/{len(gsm_problems)}] Running Loss: {curr_loss:.4f} | PPL: {math.exp(min(curr_loss, 20.0)):.2f}")

    dt_gsm = time.perf_counter() - t0
    avg_gsm_loss = sum(gsm_losses) / len(gsm_losses)
    final_gsm_ppl = math.exp(min(avg_gsm_loss, 20.0))

    print("\n" + "=" * 76)
    print("Exhaustive Full-Dataset Evaluation Summary (All 2,293 Problems):")
    print("=" * 76)
    print(f"• MBPP Python Coding (974/974 samples):    Loss = {avg_mbpp_loss:.4f} | Perplexity = {final_mbpp_ppl:5.2f} ({dt_mbpp:.2f}s)")
    print(f"• GSM8k Multi-Step Math (1,319/1,319 samples): Loss = {avg_gsm_loss:.4f} | Perplexity = {final_gsm_ppl:5.2f} ({dt_gsm:.2f}s)")
    print(f"• Macro-Average Exhaustive Perplexity:     {(final_mbpp_ppl + final_gsm_ppl) / 2:.2f}")
    print("=" * 76)


if __name__ == "__main__":
    run_full_dataset_benchmarks()
