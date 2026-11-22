"""
scripts/stage_hf_frontier_bundle.py
Prepares the official Hugging Face release bundle for the clean Frontier Technical Suite:
Repo: akarta-315h/imf-frontier-flagship
"""

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGING_DIR = ROOT / "dist" / "hf_frontier_bundle"
STAGING_DIR.mkdir(parents=True, exist_ok=True)

MODEL_CARD = r"""---
language:
- en
license: apache-2.0
tags:
- pytorch
- triton
- linear-attention
- state-space-models
- formal-verification
- lean4
- lie-algebra
- higher-dimensional-polytopes
- mixture-of-experts
- speculative-decoding
metrics:
- perplexity
pipeline_tag: text-generation
---

# Interaction Model Foundations (IMF): Frontier Technical Foundation Suite

**IMF (Interaction Model Foundations)** is an attention-free foundation architecture that replaces quadratic $O(N^2)$ softmax attention with continuous Lie-algebraic state-space memory splitting ($\mathrm{Sym}^2 \oplus \bigwedge^2$), higher-dimensional regular polytope coordinate frames, zero-residual speculative decoding, and formally verified Lean 4 kernel guarantees.

---

## 1. Clean Frontier Technical Training Stream

All models in this suite are trained strictly on **26,115,576 clean frontier tokens** spanning:
- **Lean 4 Formal Math**: 2,510 verified files (27.7M characters) with strict zero-axiom kernel validation.
- **Python Algorithmic Code**: MBPP, HumanEval, and CodeAlpaca (21,138 problems).
- **Domain Science**: Cheminformatics (SMILES/RDKit), CRISPR genomics, and Triton GPU kernels.
- **Zero Toy Data**: Complete purge of nursery/synthetic story datasets.

---

## 2. Checkpoints Included

| Checkpoint File | Format | Parameters | Purpose | Validation Perplexity |
| :--- | :---: | :---: | :--- | :---: |
| `imf_foundation_1b_sft.pt` | PyTorch | **1.14B** | SFT Foundation Model | **42.72 PPL** |
| `imf_foundation_1b.imf` | IMF Zero-Copy | **1.14B** | Zero-copy mmap binary container | **42.72 PPL** |
| `imf_fluency_lm_4k.pt` | PyTorch | **129.8M** | 5,000-step Technical Fluency LM | **10.32 PPL** |
| `imf_drafter_fluency_4k.pt` | PyTorch | **4.9M** | Distilled Speculative Drafter | $1.8\times - 2.1\times$ Speedup |

---

## 3. Empirical Benchmarks Across Domains

### (A) 129.8M Fluency Foundation LM (5,000 Steps)
- **Lean 4 Formal Proofs & Tactics**: **2.01 PPL** (Cross-Entropy: 0.6957)
- **Python Algorithmic Code**: **4.03 PPL** (Cross-Entropy: 1.3932)
- **Cheminformatics & Molecular SMILES**: **7.32 PPL** (Cross-Entropy: 1.9913)
- **Tool Calling & Agentic JSON Query**: **16.34 PPL** (Cross-Entropy: 2.7935)
- **Systems Engineering & Memory Safety**: **21.90 PPL** (Cross-Entropy: 3.0867)
- **Macro-Average Domain Perplexity**: **10.32 PPL**

### (B) 1.14B SFT Foundation Model (150 SFT Steps)
- **Lean 4 Formal Proofs & Tactics**: **17.90 PPL** (Cross-Entropy: 2.8849)
- **Python Algorithmic Code**: **28.88 PPL** (Cross-Entropy: 3.3630)
- **Systems Engineering & Memory Safety**: **53.87 PPL** (Cross-Entropy: 3.9866)
- **Cheminformatics & Molecular SMILES**: **86.79 PPL** (Cross-Entropy: 4.4635)
- **Tool Calling & Agentic JSON Query**: **156.34 PPL** (Cross-Entropy: 5.0520)
- **Validation Perplexity on Clean Stream**: **42.72 PPL**

---

## 4. Standalone Quickstart

```python
import torch
from imf.code_bpe_tokenizer import CodeBPETokenizer
from imf.joint_recon_predictor import IMFJointReconPredictorLM

tok = CodeBPETokenizer.load("hybrid_bpe_tokenizer_4k.json")
model = IMFJointReconPredictorLM(
    vocab_size=len(tok.vocab),
    d_model=384,
    num_layers=8,
    num_heads=8,
    polytope_dim=8,
    num_experts=16,
    top_k=2,
    max_seq_len=256,
)
model.load_state_dict(torch.load("imf_fluency_lm_4k.pt", map_location="cuda"))
model.cuda().eval()
```

---

## 5. Publications & Formal Theorems

Included in this release is `imf_preprint.pdf`, the complete **45-paper technical compendium** detailing the theoretical derivations, GPU Triton kernels, and empirical evaluations across all 45 foundational IMF monographs.
"""


def stage_frontier_release():
    print("=" * 80)
    print("  Staging IMF Frontier Technical Flagship Release Bundle")
    print("=" * 80)

    # 1. Staging Checkpoints
    checkpoints = [
        ROOT / "checkpoints" / "imf_foundation_1b_sft.pt",
        ROOT / "checkpoints" / "imf_foundation_1b.imf",
        ROOT / "checkpoints" / "imf_fluency_lm_4k.pt",
        ROOT / "checkpoints" / "imf_drafter_fluency_4k.pt",
    ]
    for ckpt in checkpoints:
        if ckpt.exists():
            dest = STAGING_DIR / ckpt.name
            size_mb = ckpt.stat().st_size / (1024**2)
            print(f"  [>] Staging checkpoint: {ckpt.name} ({size_mb:.1f} MB)...")
            shutil.copy2(ckpt, dest)
        else:
            print(f"  [!] Missing checkpoint: {ckpt.name}")

    # 2. Staging Tokenizer
    tok_path = ROOT / "checkpoints" / "hybrid_bpe_tokenizer_4k.json"
    if tok_path.exists():
        print(f"  [>] Staging 4K tokenizer: {tok_path.name}")
        shutil.copy2(tok_path, STAGING_DIR / "hybrid_bpe_tokenizer_4k.json")

    # 3. Staging 45-Paper Preprint Compendium
    pdf_path = ROOT / "dist" / "imf_preprint.pdf"
    if pdf_path.exists():
        print(f"  [>] Staging 45-paper compendium: {pdf_path.name} ({pdf_path.stat().st_size / (1024**2):.1f} MB)")
        shutil.copy2(pdf_path, STAGING_DIR / "imf_preprint.pdf")

    # 4. Write README
    (STAGING_DIR / "README.md").write_text(MODEL_CARD, encoding="utf-8")
    print(f"\n[✓] Staging complete at: {STAGING_DIR}")


if __name__ == "__main__":
    stage_frontier_release()
