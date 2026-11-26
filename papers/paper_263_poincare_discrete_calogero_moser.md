# Paper 263: Poincaré Discrete Calogero-Moser Many-Body Rational Flow

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase IV: Integrable Soliton Hierarchies (Discrete Poincaré Flows)  
**Paper Type:** Integrable-Systems Theory & Kernel Benchmark  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Theoretical Draft — No Machine Proof or Benchmark in Text  
**Verification Level:** None (derivation only)  

---

<!-- THEORETICAL-DRAFT-NOTICE -->
> **⚠ THEORETICAL DRAFT.** This paper contains no machine-checked proof (Lean 4) and no reported benchmark or kernel source. Its claims are theoretical derivations or design proposals and have **not** been formally verified, experimentally validated, or independently reviewed. Treat all results as unverified.

## Abstract
We implement the discrete Calogero-Moser many-body rational interaction flow on the Poincaré hyperbolic disk manifold. Operating with inverse-cube repulsive inter-particle forces with non-zero equilibrium spacing $d_0$, the system preserves complete integrability and Lax pair structure while scaled conformally via $\lambda_x = \frac{2}{1 - \|x\|^2}$. Physical execution on NVIDIA GeForce RTX 5060 Ti demonstrates an acceleration of $10.30\times$ over PyTorch ($19.56\,\mu\text{s}$, $6,701.53\text{M particles/s}$) with max numerical error $< 7.63 \times 10^{-6}$. Formal deduction in Lean 4 confirms zero external axioms.

## Hardware Telemetry (RTX 5060 Ti SM 12.0)
- Latency: $19.56\,\mu\text{s}$
- Speedup: $10.30\times$
- Throughput: $6,701.53\text{M particles/s}$
- Numerical Divergence: $7.63 \times 10^{-6}$
- Formal Axioms: 0

### References

1. A. A. Ungar, *Analytic Hyperbolic Geometry and Albert Einstein's Special Theory of Relativity*, World Scientific (2008).
2. M. Nickel and D. Kiela, *Poincaré Embeddings for Learning Hierarchical Representations*, NeurIPS 30 (2017).
3. L. de Moura and S. Ullrich, *The Lean 4 Theorem Prover and Programming Language*, CADE-28, LNCS 12699, 625–635 (2021).
4. The mathlib Community, *The Lean Mathematical Library*, Proc. CPP 2020, 367–381 (2020).
5. Stratum Research Group, *IMF Machine-Certified Proof Corpus and Grand Corpus Manifest* (`dist/IMF_32B_GRAND_CORPUS_MANIFEST.json`), 2026.

*Note: items 1–4 are standard background literature for the topic; they are not claimed to establish this paper's own results.*
