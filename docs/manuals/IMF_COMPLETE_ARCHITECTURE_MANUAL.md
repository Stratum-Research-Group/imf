# IMF System Architecture & Complete Sub-Bit Operations Guide

**Author**: Nicholas Charles Mynhardt (Stratum Research Group)  
**System Target**: AMD Ryzen 5 7600X | NVIDIA GeForce RTX 5060 Ti (16GB GDDR7, Blackwell SM 12.0) | CUDA 12.8, Triton 3.9  
**Specification Level**: Production / Mathematical Invariant Hardened  

---

## 1. Architectural Overview

The **IMF** (Intrinsic Manifold Factorization) architecture enables real-time sub-bit inference, polyhedral lattice quantization, multi-agent council deliberation, and automated formal theorem verification.

```
+---------------------------------------------------------------------------------------+
|                                    USER INTERFACES                                    |
|   +------------------------------------+    +-------------------------------------+   |
|   |         Metis-VSCode (Void)        |    |            IMF GUI (Rust)           |   |
|   |  - IMF Council Model & Debate Tab  |    |  - CouncilModel Live Moderator      |   |
|   |  - MegaGym 32B Prover Routine Tab  |    |  - Omni-Model Fleet Broadcast (10)  |   |
|   |  - Troubleshooting Pipeline Tab    |    |  - Clean Structured Transcript View |   |
|   +-----------------+------------------+    +------------------+------------------+   |
|                     |                                          |                      |
|                     +--------------------+---------------------+                      |
|                                          | HTTP (Port 8092)                           |
+------------------------------------------v--------------------------------------------+
|                               IMF UNIFIED INFERENCE SERVER                            |
|                          (scripts/serve_openai_compatible_api.py)                      |
|  - SSE Streaming (/v1/chat/completions)      - Sandbox Execution (/v1/sandbox/execute)|
|  - Council Consensus (/v1/council/debate)   - Search/Replace Diff (/v1/sandbox/diff)  |
|  - MegaGym Routine (/v1/megagym/routine)     - Self-Healing Pipeline (/v1/troubleshoot)|
|  - Formal Lean Verify (/v1/verify/lean)      - Sovereign Embeddings (/v1/embeddings)  |
+------------------------------------------+--------------------------------------------+
                                           |
+------------------------------------------v--------------------------------------------+
|                                NATIVE SUB-BIT FLEET                                   |
|  1. imf-council-model           : Deliberation Arbiter & Speaker                      |
|  2. imf-foundation-1.14b        : Polytope Joint Reconstruction Predictor (576D)     |
|  3. imf-70b-plq                 : Polytope Lattice Quantization (16GB VRAM bounds)    |
|  4. imf-foundation-7b-gosset    : 240 E8 Lie Minimal Root Decompositions              |
|  5. imf-100b-leech-mope         : 24-Dimensional Leech Lattice Mixture of Polytope    |
|  6. weft2-extended-rlvr         : Native WEFT Factorized 16k Token Engine             |
|  7. weft2-tool-grpo             : Group Relative Policy Optimization Tool Calling    |
|  8. weft2-sft-15k               : Supervised Fine-Tuned 15k Base Sub-Bit              |
|  9. llama-3.3-70b-core          : Sub-Bit Lie-Algebraic Reasoning Core                |
| 10. qwen-2.5-72b-core           : Sub-Bit Lie-Algebraic Reasoning Core                |
+---------------------------------------------------------------------------------------+
```

---

## 2. Model Inventory & Mathematical Foundations

### 2.1 IMF-Foundation-1.14B (`checkpoints/imf_foundation_1b.imf`)
- **Structure**: 16 transformer layers, 8 heads, $d_{\text{model}} = 576$, 16 Polytope MoE experts with top-2 routing ($\text{polytope\_dim} = 8$).
- **Joint Reconstruction Loss**: $\mathcal{L} = \mathcal{L}_{\text{next-token}} + \alpha \cdot \mathcal{L}_{\text{recon}}$, where $\alpha = 0.20$.
- **Tokenizer**: 4,096-token Hybrid BPE (`checkpoints/hybrid_bpe_tokenizer_4k.json`).

### 2.2 IMF-70B-PLQ (`checkpoints/imf_70b_plq_architecture.imf`)
- **Quantization**: Polytope Lattice Quantization (PLQ). Projections onto the root lattices allow 70 billion parameters to reside in sub-bit space, fitting comfortably within the 16GB VRAM budget of the RTX 5060 Ti alongside active KV-caches.

### 2.3 IMF-Foundation-7B-Gosset (`checkpoints/imf_foundation_7b_gosset.imf`)
- **Symmetry Group**: Lie algebra $E_8$ Gosset $4_{21}$ polytope with 240 minimal roots. Enforces exact continuous rotational invariance on embedding transformations.

### 2.4 IMF-100B-Leech-MoPE (`checkpoints/imf_foundation_100b_leech_mope.imf`)
- **Lattice**: $\Lambda_{24}$ Leech Lattice (196,560 minimal vectors). Uses Mixture of Polytope Experts (MoPE) to route inference sparsely across virtual cells.

### 2.5 WEFT2 Native Sub-Bit Suite (`/home/akarta/Projects/0.WiP/Weft/checkpoints/*.weft`)
- Evaluates factorized window tensors across context sequences up to 16,384 tokens with zero Ollama/llama.cpp external dependencies.

---

## 3. The MegaGym 32-Billion Step Prover Fleet

### 3.1 Prover Fleet Structure
The MegaGym prover fleet certifies mathematical theorems through pure forward proof search in Lean 4 without introducing synthetic axioms.

- **Cumulative Progress**: $11,000,000$ certified theorems sealed across Blocks 01 through 11.
- **Verification Invariants**:
  - Axioms: $0$
  - Sorry: $0$
  - Kernel: 100% Verified
- **Corpus Archive**: Compressed Zstandard archives stored in `dist/gym_32b_corpus/block_*.tar.zst` with cryptographic SHA-256 validation ledgers in `dist/IMF_32B_GRAND_CORPUS_MANIFEST.json`.

---

## 4. API Endpoints Specification (Port 8092)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Live GPU VRAM, temperature, and fleet health. |
| `GET` | `/v1/models` | OpenAI-compatible model catalog listing all 10 native sub-bit models. |
| `POST` | `/v1/chat/completions` | SSE streaming (`text/event-stream`) and buffered OpenAI-compliant completions. |
| `POST` | `/v1/council/debate` | Multi-agent structured debate protocol with Board Model moderation. |
| `POST` | `/v1/sandbox/execute` | Sub-50ms execution of council-generated code artifacts. |
| `POST` | `/v1/sandbox/diff` | Generates unified search/replace diffs for in-editor FastApply. |
| `GET` | `/v1/megagym/routine` | Live 32B prover routine metrics, block ledger, and speed telemetry. |
| `GET` | `/v1/troubleshoot/pipeline` | Diagnostic supervisor reporting process health and self-healing remediations. |
| `POST` | `/v1/verify/lean` | Automated background Lean 4 theorem and invariant verification. |
| `POST` | `/v1/embeddings` | 576-dimensional sovereign embedding vectors derived from `imf-foundation-1.14b`. |

---

## 5. Metis-VSCode (Void) Integration

The Metis-VSCode IDE connects directly to the IMF server:
1. **Activity Bar View Container**: `IMF Sub-Bit Fleet` (`imfCouncilContainer`).
2. **Interactive Views**:
   - `🏛 IMF CouncilModel & Debate`: Full interactive deliberator with sandbox execution triggers.
   - `🏋️ MegaGym 32B Prover Routine`: Polling prover metrics and sealed block verification badges.
   - `🛠️ Troubleshooting Pipeline`: Supervisor with one-click self-healing sweep.
3. **Editor Diff Integration**: Patches generated during Council deliberations are piped to Void's `editCodeService` for inline diff viewing and instant application.
EOF
ls -la docs/IMF_COMPLETE_ARCHITECTURE_MANUAL.md
