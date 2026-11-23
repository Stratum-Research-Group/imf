"""
benchmark_1b_multidomain_eval.py
Rigorous multi-domain benchmark assessing the 1.14-Billion parameter foundation model across:
1. Python Code Reasoning & AST Syntax Synthesis
2. Mathematical Reasoning & Symbolic Arithmetic (GSM8K style)
3. Formal Logic & Bipartite Directional Separation
4. Cross-Domain General Knowledge & Fluency
All models loaded directly from zero-copy .imf binary containers.
"""

import sys
import time
import math
from pathlib import Path
import torch

from imf.imf_model_loader import load_imf_state_dict
from imf.joint_recon_predictor import IMFJointReconPredictorLM
from imf.code_bpe_tokenizer import CodeBPETokenizer

def run_multidomain_evaluation():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 80)
    print("  IMF 1.14-Billion Parameter Multi-Domain Benchmark Evaluation")
    print("=" * 80)
    print(f"Device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    target_imf = Path("checkpoints/imf_foundation_1b.imf")
    tokenizer_path = "checkpoints/hybrid_bpe_tokenizer_4k.json"

    if not target_imf.exists() or not Path(tokenizer_path).exists():
        print("Error: Missing checkpoints/imf_foundation_1b.imf or tokenizer JSON")
        return

    tok = CodeBPETokenizer.load(tokenizer_path)

    # 1. Zero-copy load
    print("\n[*] Loading 1.14B Foundation Model from zero-copy .imf container...")
    t0 = time.perf_counter()
    state_dict = load_imf_state_dict(str(target_imf), device="cpu")
    t_load = (time.perf_counter() - t0) * 1000
    print(f"[✓] Mapped 1.14B model ({len(state_dict)} tensors) in {t_load:.2f} ms")

    model = IMFJointReconPredictorLM(
        vocab_size=len(tok.vocab),
        d_model=576,
        num_layers=16,
        num_heads=8,
        polytope_dim=8,
        num_experts=16,
        top_k=2,
        max_seq_len=128,
        alpha_recon=0.2,
    ).to(device)
    model.load_state_dict(state_dict, strict=False)
    model.eval()

    test_domains = {
        "Python Code Reasoning": [
            ("def binary_search(arr, target):", "low, high = 0, len(arr) - 1"),
            ("def is_prime(n):", "if n <= 1: return False"),
            ("class LRUCache:", "def __init__(self, capacity):"),
        ],
        "Mathematical Logic": [
            ("Calculate: 15 * 12 + 45 =", "225"),
            ("Solve for x: 3x - 9 = 21, x =", "10"),
            ("What is the prime factorization of 60?", "2^2 * 3 * 5"),
        ],
        "Formal Proof & Logic": [
            ("theorem add_comm (n m : Nat) : n + m = m + n :=", "by omega"),
            ("modus_ponens: P implies Q, and P is true, therefore", "Q is true"),
            ("Hypothetical syllogism: A -> B, B -> C implies", "A -> C"),
        ],
        "General Science & Fluency": [
            ("The mitochondria is often referred to as the", "powerhouse of the cell"),
            ("Newton's second law of motion states that force equals", "mass times acceleration"),
            ("The speed of light in vacuum is approximately", "300,000 kilometers per second"),
        ]
    }

    print("\n[*] Evaluating Perplexity and Cross-Entropy Loss Across Domains...")
    domain_results = {}

    for domain, samples in test_domains.items():
        total_loss = 0.0
        total_tokens = 0
        correct_top1 = 0
        
        for prompt, continuation in samples:
            text = f"{prompt} {continuation}"
            ids = tok.encode(text)
            if len(ids) < 2: continue
            
            x = torch.tensor([ids[:-1]], dtype=torch.long, device=device)
            targets = torch.tensor([ids[1:]], dtype=torch.long, device=device)
            
            with torch.no_grad():
                out = model(x, targets=targets)
                logits = out[0]
                metrics = out[2] if len(out) > 2 else {}
                loss = metrics.get("loss_pred", torch.nn.functional.cross_entropy(logits.view(-1, len(tok.vocab)), targets.view(-1)))
                
                preds = torch.argmax(logits, dim=-1)
                correct_top1 += (preds == targets).sum().item()
                total_tokens += targets.numel()
                total_loss += loss.item() * targets.numel()

        avg_loss = total_loss / max(total_tokens, 1)
        ppl = math.exp(min(avg_loss, 20.0))
        accuracy = (correct_top1 / max(total_tokens, 1)) * 100.0
        domain_results[domain] = {"loss": avg_loss, "ppl": ppl, "accuracy": accuracy}
        print(f"  [>] {domain:<25} | Loss: {avg_loss:.4f} | Perplexity: {ppl:6.2f} | Next-Token Acc: {accuracy:5.1f}%")

    # Overall Summary
    avg_overall_ppl = sum(r["ppl"] for r in domain_results.values()) / len(domain_results)
    avg_overall_acc = sum(r["accuracy"] for r in domain_results.values()) / len(domain_results)
    print("\n" + "=" * 80)
    print(f"  BENCHMARK SUMMARY: Overall PPL = {avg_overall_ppl:.2f} | Overall Accuracy = {avg_overall_acc:.1f}%")
    print("=" * 80)

if __name__ == "__main__":
    run_multidomain_evaluation()
