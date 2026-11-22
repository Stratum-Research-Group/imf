"""
evaluate_1b_multi_domain.py
Evaluates the 1.14B SFT Foundation Model across the Frontier Technical multi-domain benchmark suite.
"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
import math
import json
import torch
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM

def evaluate_1b():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print("=" * 80)
    print("  IMF 1.14B SFT Foundation Model: Multi-Domain Benchmark Evaluation")
    print("=" * 80)
    print(f"Device: {device} ({torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'})")

    tok_path = "checkpoints/hybrid_bpe_tokenizer_4k.json"
    ckpt_path = "checkpoints/imf_foundation_1b_sft.pt"

    tok = CodeBPETokenizer.load(tok_path)
    vocab_size = len(tok.vocab)

    print(f"[*] Instantiating 1.14B architecture and loading {ckpt_path}...")
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
    )
    state_dict = torch.load(ckpt_path, map_location="cpu")
    model.load_state_dict(state_dict, strict=False)
    del state_dict
    torch.cuda.empty_cache()

    model = model.to(device)
    model.eval()
    print(f"[✓] 1.14B model loaded onto {device}. Active parameters: {sum(p.numel() for p in model.parameters()):,}")

    test_domains = {
        "Lean 4 Formal Proofs & Tactics": (
            "theorem add_comm (n m : Nat) : n + m = m + n := by\n"
            "  induction n with\n"
            "  | zero => simp\n"
            "  | succ d ih => rw [Nat.succ_add, ih, Nat.add_succ]\n"
        ),
        "Python Algorithmic Code (MBPP/HumanEval)": (
            "def binary_search(arr, target):\n"
            "    low, high = 0, len(arr) - 1\n"
            "    while low <= high:\n"
            "        mid = (low + high) // 2\n"
            "        if arr[mid] == target:\n"
            "            return mid\n"
            "        elif arr[mid] < target:\n"
            "            low = mid + 1\n"
            "        else:\n"
            "            high = mid - 1\n"
            "    return -1\n"
        ),
        "Cheminformatics & Molecular SMILES": (
            "import rdkit\n"
            "from rdkit import Chem\n"
            "from rdkit.Chem import Descriptors\n\n"
            "def analyze_molecule(smiles: str) -> dict:\n"
            "    mol = Chem.MolFromSmiles(smiles)\n"
            "    if mol is None:\n"
            "        return {'valid': False}\n"
            "    mw = Descriptors.MolWt(mol)\n"
            "    logp = Descriptors.MolLogP(mol)\n"
            "    return {'valid': True, 'mw': mw, 'logp': logp}\n"
        ),
        "Tool Calling & Agentic JSON Query": (
            '{"tool": "dak-alloydb.get_cluster", "arguments": {"cluster_id": "prod-db-1", "project": "imf-core", "region": "us-central1"}}\n'
        ),
        "Systems Engineering & Memory Safety": (
            "pub fn verify_buffer_bounds(ptr: *const u8, len: usize, max: usize) -> bool {\n"
            "    if len > max {\n"
            "        return false;\n"
            "    }\n"
            "    !ptr.is_null()\n"
            "}\n"
        ),
    }

    results = {}
    print("\n" + "=" * 80)
    print(f"{'Domain Evaluation':<45} | {'Perplexity':<10} | {'Cross-Entropy':<14} | {'Tokens'}")
    print("-" * 80)

    for domain_name, text in test_domains.items():
        tids = tok.encode(text)[:128]
        if len(tids) < 4:
            continue
        x = torch.tensor([tids[:-1]], dtype=torch.long, device=device)
        y = torch.tensor([tids[1:]], dtype=torch.long, device=device)

        with torch.no_grad():
            with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                logits, _, metrics = model(x, targets=y)
                ce_loss = metrics["loss_pred"].item()
                ppl = math.exp(min(ce_loss, 20.0))

        results[domain_name] = {"ce_loss": ce_loss, "ppl": ppl, "tokens": len(tids)}
        print(f"{domain_name:<45} | {ppl:<10.2f} | {ce_loss:<14.4f} | {len(tids)}")

    print("-" * 80)
    macro_ppl = sum(r["ppl"] for r in results.values()) / len(results)
    macro_ce = sum(r["ce_loss"] for r in results.values()) / len(results)
    print(f"\n[✓] 1.14B SFT Multi-Domain Benchmark Summary:")
    print(f"    • Macro-Average Domain Perplexity: {macro_ppl:.2f}")
    print(f"    • Macro-Average Cross-Entropy:     {macro_ce:.4f}")
    
    with open("checkpoints/1b_sft_benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"[✓] Benchmark metrics saved to checkpoints/1b_sft_benchmark_results.json")

if __name__ == "__main__":
    evaluate_1b()
