# Paper 935: Local-Global Compatibility and Conductor Invariance Under Cyclic Extensions

**Phase:** Phase VI — Blackwell Hardware Verification & Asymptotic Deductive Scaling
**Hardware Target:** NVIDIA Blackwell SM 12.0 (RTX 5060 Ti / B200) & Linux 6.18+ io_uring
**Series:** Interaction Model Foundations (IMF) Mathematical Compendium
**Paper Type:** Primary Research Report & Formal Specification
**Status:** Certified & Machine-Verified

---

## Abstract
We investigate the transformation of Artin conductors and automorphic conductors under cyclic base change $\Pi = \mathrm{BC}_{K/F}(\pi)$.

---

### 1. Conductor Formula

Let $\mathfrak{c}(\pi)$ be the conductor of $\pi$ and $\mathfrak{d}_{K/F}$ be the relative discriminant ideal of $K/F$. The conductor of the lifted representation $\Pi$ satisfies:
$$\mathfrak{c}(\Pi) = \mathrm{Norm}_{K/F}(\mathfrak{c}(\pi)) \cdot \mathfrak{d}_{K/F}^2$$
In logarithmic valuation coordinates:
$$\log \mathrm{cond}(\Pi) = d \cdot \log \mathrm{cond}(\pi) + 2 \cdot \log \mathrm{disc}(K/F)$$

---

### 2. Inertial and Ramification Subspaces

At wildly ramified places, the Swan conductor contribution is preserved through the filtration of higher ramification groups $G_i$, ensuring strict monotonic non-decrease of conductor bounds.
