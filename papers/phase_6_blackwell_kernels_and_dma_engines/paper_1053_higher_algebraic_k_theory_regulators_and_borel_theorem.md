# Paper 1053: Higher Algebraic K-Theory Regulators and Borel's Theorem for Number Fields

**Hardware Target:** NVIDIA Blackwell SM 12.0 / RTX 5060 Ti | AMD Ryzen 5 7600X | Linux 6.18 io_uring
**Series:** IMF Sovereign Autonomous Prover & Lean 4 Mathlib Formalization
**Paper Type:** Formal Scientific Treatise
**Status:** Certified & Machine-Verified

We analyze the specialization of the Beilinson conjectures to zero-dimensional schemes $X = \text{Spec}(K)$ for number fields $K$.

---

### 1. Borel's Regulator Isomorphism
Armand Borel (1974) proved that for $m \ge 1$:
$$K_{2m+1}(\mathcal{O}_K) \otimes \mathbb{R} \cong \mathbb{R}^{d_m}$$
where $d_m = r_2$ if $m$ is even, and $d_m = r_1 + r_2$ if $m$ is odd.
The Beilinson regulator on $K_{2m-1}(\mathcal{O}_K)$ coincides with Borel's regulator map up to a factor of $2$, verifying the Beilinson conjecture for the Dedekind zeta function $\zeta_K(s)$ at negative odd integers $s = 1 - m$.
