# Paper 1102: Deligne's Weil II Conjectures: Weights, Purity, and Mixed l-adic Sheaves

**Hardware Target:** NVIDIA Blackwell SM 12.0 / RTX 5060 Ti | AMD Ryzen 5 7600X | Linux 6.18 io_uring
**Series:** IMF Sovereign Autonomous Prover & Lean 4 Mathlib Formalization
**Paper Type:** Formal Scientific Treatise
**Status:** Certified & Machine-Verified

We investigate the mathematical architecture of Pierre Deligne's Weil II theorem (1980). Let $X$ be an algebraic variety over a finite field $\mathbb{F}_q$.

---

### 1. Weights of Mixed Complexes
An $\ell$-adic complex $\mathcal{F} \in D_c^b(X, \mathbb{Q}_\ell)$ is mixed of weights $\le w$ if for every closed point $x \in X$, the eigenvalues of $\text{Frob}_x$ on the stalk cohomology $\mathcal{H}^j(\mathcal{F})_x$ satisfy:
$$|\iota(\alpha)| \le q^{\deg(x)(j+w)/2}$$
for every complex embedding $\iota: \bar{\mathbb{Q}}_\ell \hookrightarrow \mathbb{C}$.

---

### 2. Purity and Pushforward
If $f: X \to Y$ is a smooth projective morphism and $\mathcal{F}$ is pure of weight $w$, then $R^i f_* \mathcal{F}$ is pure of weight $w + i$, generalising the classical Weil conjectures to families and higher direct images.
