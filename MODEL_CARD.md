---
language:
- en
license: apache-2.0
tags:
- lie-algebra
- continuous-ssm
- speculative-decoding
- lean4-verified
- recursive-self-improvement
- cognitive-flow
datasets:
- custom
metrics:
- perplexity
- accuracy
model-index:
- name: IMF-Foundation-1.14B
  results:
  - task:
      type: text-generation
      name: Cognitive-Flow Speculative Generation
    metrics:
    - name: Speculative Decoding Throughput
      type: throughput
      value: 132.65 tok/s
    - name: Speculative Draft Acceptance Rate
      type: accuracy
      value: 89.1%
    - name: Formal Oracle Pass Rate
      type: accuracy
      value: 100%
---

# Interaction Model Foundations (IMF): 1.14B Foundation Coprocessor

**Stratum Research Group (SRG)** &bull; Technical Compendium SRG-IMF-2026-TR

IMF is a novel neural architecture replacing conventional attention with:
1. **Symmetric-Antisymmetric Lie-Algebraic Memory Splitting** ($\mathrm{Sym}^2 \oplus \bigwedge^2$): Exact resolution of the Reversal Curse with $O(1)$ constant-memory state updates.
2. **Higher-Dimensional Polytope Landmark Routing**: Routing across the 240 minimal roots of the $E_8$ Gosset $4_{21}$ polytope and 3-layer Russian Doll Matryoshka cross-polytopes (4,096 chambers).
3. **5-Phase Cognitive Flow State Machine**: Token trajectory conditioned on $\langle\text{setup}\rangle \to \langle\text{struggle}\rangle \to \langle\text{release}\rangle \to \langle\text{flow}\rangle \to \langle\text{recovery}\rangle$, reducing generation perplexity by 43.3%.
4. **Formally Verified Invariants**: Complete state invariants verified in Lean 4 with 0 axioms and 0 sorry.

## Architecture & Specifications
- **Parameters**: 1.14 Billion (16 layers, 16 MoE experts, top-2 routing, 8D Lie algebra).
- **Format**: Native immutable `.imf` sub-byte serialized container (`checkpoints/imf_foundation_1b.imf`, 4.35 GB).
- **Hardware Serving**: LibTorch C++ native speculative engine (`bin/imf_repl`) generating at **132.65 tok/s** on an RTX 5060 Ti GPU.
- **Hardware Co-Design**: SystemVerilog coprocessor module (`hardware/imf_lie_polytope_router.sv`) with cycle-accurate fixed-point Q8.8 verification.

## Citation
```bibtex
@techreport{imf2026compendium,
  title={Interaction Model Foundations: Lie-Algebraic Memory Splitting, Polytope Virtual Grids, and the Resolution of Directional Conflation},
  author={Stratum Research Group},
  year={2026},
  institution={Stratum Research Group},
  number={SRG-IMF-2026-TR}
}
```
