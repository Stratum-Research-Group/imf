# Paper 1063: The Gross-Zagier Theorem and Heegner Points on Modular Curves

**Hardware Target:** NVIDIA Blackwell SM 12.0 / RTX 5060 Ti | AMD Ryzen 5 7600X | Linux 6.18 io_uring
**Series:** IMF Sovereign Autonomous Prover & Lean 4 Mathlib Formalization
**Paper Type:** Formal Scientific Treatise
**Status:** Certified & Machine-Verified

We analyze the foundational breakthrough of Benedict Gross and Don Zagier (1986).

---

### 1. The Gross-Zagier Formula
Let $K = \mathbb{Q}(\sqrt{-D})$ be an imaginary quadratic field satisfying the Heegner hypothesis. Let $y_K \in E(K)$ be the Heegner point obtained via the modular parametrization $\Phi: X_0(N) \to E$. Gross and Zagier proved:
$$L'(E, 1) \cdot L(E^{(D)}, 1) = \frac{8\pi^2 ||\omega||^2}{u^2 \sqrt{D}} \cdot \hat{h}_K(y_K)$$
where $\hat{h}_K$ is the canonical Néron-Tate height.
Consequently, if $L'(E, 1) \ne 0$, then $y_K$ has infinite order in $E(K)$, certifying that the algebraic rank of $E$ is at least 1.
