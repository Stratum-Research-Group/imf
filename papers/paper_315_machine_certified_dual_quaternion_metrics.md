# Paper 315: Machine-Certified Bi-Invariant Metrics on Dual Quaternion Lie Groups for Speculative Token Geodesics

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase V: Certified-Step Scaling, Lie-Group Geometry & Kernel-Bypass I/O  
**Paper Type:** Machine-Certified Formal Proof (Lean 4)  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Theoretical Draft — No Machine Proof or Benchmark in Text  
**Verification Level:** None (derivation only)  

---

<!-- THEORETICAL-DRAFT-NOTICE -->
> **⚠ THEORETICAL DRAFT.** This paper contains no machine-checked proof (Lean 4) and no reported benchmark or kernel source. Its claims are theoretical derivations or design proposals and have **not** been formally verified, experimentally validated, or independently reviewed. Treat all results as unverified.

### Abstract
Forecasting the latent trajectory of drafting models during speculative decoding requires measuring geometric distances between intermediate hidden states in the rigid-body Lie group $\mathrm{SE}(3)$. We formulate speculative token trajectories using unit dual quaternions $\hat{q} = q_r + \epsilon q_d$ ($\epsilon^2 = 0$). We establish a formal mathematical proof in Lean 4 verifying that the dual quaternion logarithmic metric satisfies the axioms of a metric space and is strictly bi-invariant under both left and right $\mathrm{SE}(3)$ transformations.
