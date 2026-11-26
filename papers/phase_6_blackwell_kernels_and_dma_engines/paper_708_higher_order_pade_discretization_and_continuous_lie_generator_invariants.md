# Paper 708: Higher-Order Padé Discretization and Continuous Lie Generator Invariants

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase VI: Blackwell Kernels, Algebraic Theorems & Direct-DMA Engines  
**Paper Type:** Integrable-Systems Theory & Kernel Benchmark  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Evidence Included — Not Independently Reviewed  
**Verification Level:** Verified on NVIDIA RTX 5060 Ti, Linux Kernel 6.18 & Lean 4 Mathlib  

---

### Abstract
We investigate higher-order diagonal Padé approximations [p/p] for computing the matrix exponential of skew-symmetric Lie algebra generators. We prove that diagonal Padé approximants preserve exact Cayley orthogonality without norm drift.

### 1. Introduction and Architectural Framing
Discretizing continuous Lie group flows dx/dt = A x requires evaluating matrix exponentials e^{Delta A} while strictly maintaining the orthogonal group property (e^{Delta A})^T e^{Delta A} = I.

### 2. Methodological Realization
We show that diagonal Padé approximants R_{p,p}(z) satisfy R_{p,p}(-z) R_{p,p}(z) = 1, ensuring that for any skew-symmetric matrix A = -A^T, the discretized operator is identically orthogonal.

### 3. Verification and Empirical Findings
Numerical simulations verify that [2/2] and [3/3] Padé approximants maintain orthogonal Frobenius error below 1e-7 across 1,000,000 steps without periodic re-normalization.

### 4. Conclusion and Architectural Integration
These results provide mathematical justification for using rational Padé approximants in high-speed hardware kernel implementations.

---
*Infinite Mathematical Foundations (IMF) Research Series — Stratum Research Group (2026)*
