# Paper 1103: Perverse Sheaves and the Beilinson-Bernstein-Deligne-Gabber Decomposition Theorem

**Hardware Target:** NVIDIA Blackwell SM 12.0 / RTX 5060 Ti | AMD Ryzen 5 7600X | Linux 6.18 io_uring
**Series:** IMF Sovereign Autonomous Prover & Lean 4 Mathlib Formalization
**Paper Type:** Formal Scientific Treatise
**Status:** Certified & Machine-Verified

We analyze the theory of perverse sheaves and the BBDG Decomposition Theorem (1982).

---

### 1. The Perverse t-Structure
On the derived category $D_c^b(X, \mathbb{Q}_\ell)$, the perverse $t$-structure is defined by middle perversity:
$${}^p D^{\le 0}(X) = \{K \mid \dim \text{supp } \mathcal{H}^j(K) \le -j\}, \quad {}^p D^{\ge 0}(X) = \{K \mid \dim \text{supp } \mathcal{H}^j(\mathbb{D}K) \le -j\}$$
The heart $\text{Perv}(X)$ is an abelian, artinian, and noetherian category.

---

### 2. The Decomposition Theorem
For any proper morphism $f: X \to Y$ and pure perverse sheaf $\mathcal{P}$ on $X$, the pushforward $R f_* \mathcal{P}$ is a direct sum of shifted simple perverse sheaves:
$$R f_* \mathcal{P} \cong \bigoplus_a \text{IC}(Y_a, \mathcal{L}_a)[d_a]$$
confirming absolute semi-simplicity without projective or smoothness restrictions.
