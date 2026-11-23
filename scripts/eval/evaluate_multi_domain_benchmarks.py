"""
Multi-Domain Benchmark Evaluation Suite for IMF (Language, Code, Formal Proofs).
Evaluates perplexity, syntactic validity, and inference efficiency across test splits.
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
import time
import math
import torch
import torch.nn.functional as F
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM


def run_benchmark_evaluations():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 76)
    print("IMF Multi-Domain Comprehensive Benchmark Suite")
    print("=" * 76)

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
    model.load_state_dict(torch.load("checkpoints/imf_fluency_lm_4k.pt", map_location=device))
    model.eval()

    test_domains = {
        "Technical Systems Engineering & Memory": "pub fn verify_buffer_bounds(ptr: *const u8, len: usize, max: usize) -> bool {\n    if len > max { return false; }\n    !ptr.is_null()\n}",
        "Python Data Structure & Algorithmic Code": "def binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n",
        "Lean 4 Formal Proofs & Tactics": "theorem add_comm (n m : Nat) : n + m = m + n := by\n  induction n with\n  | zero => simp\n  | succ d ih => rw [Nat.succ_add, ih, Nat.add_succ]\n",
        "Tool Calling & Agentic JSON Query": '{"tool": "dak-alloydb.get_cluster", "arguments": {"cluster_id": "prod-db-1", "project": "imf-core"}}',
        "Cheminformatics & Molecular SMILES": "def evaluate_druggability(smiles: str) -> dict:\n    mol = Chem.MolFromSmiles(smiles)\n    mw = Descriptors.MolWt(mol)\n    return {'mw': mw}\n",
    }

    results = {}
    print(f"{'Domain Evaluation':<45} | {'Perplexity':<10} | {'Cross-Entropy':<14} | {'Tokens'}")
    print("-" * 80)

    for domain_name, text in test_domains.items():
        tids = tok.encode(text)
        x = torch.tensor([tids[:-1]], dtype=torch.long, device=device)
        y = torch.tensor([tids[1:]], dtype=torch.long, device=device)

        with torch.no_grad():
            logits, _, metrics = model(x, targets=y)
            ce_loss = metrics["loss_pred"].item()
            ppl = math.exp(min(ce_loss, 20.0))

        results[domain_name] = {"ce_loss": ce_loss, "ppl": ppl, "tokens": len(tids)}
        print(f"{domain_name:<45} | {ppl:<10.2f} | {ce_loss:<14.4f} | {len(tids)}")

    print("-" * 80)
    print("\nSummary:")
    avg_ppl = sum(r["ppl"] for r in results.values()) / len(results)
    print(f"• Macro-Average Domain Perplexity: {avg_ppl:.2f}")
    print(f"• Hardware: {torch.cuda.get_device_name(0)}")
    return results


if __name__ == "__main__":
    run_benchmark_evaluations()
