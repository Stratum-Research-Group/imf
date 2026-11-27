# Paper 1152: The Bass-Quillen Conjecture: Projective Modules over Polynomial Rings, Horrocks' Theorem, and Quillen Patching

**Hardware Target:** NVIDIA Blackwell SM 12.0 (RTX 5060 Ti) + AMD Ryzen 5 7600X
**Series:** Bass-Quillen Conjecture & Horrocks Reduction
**Paper Type:** Technical Monograph
**Status:** Canonical Reference Treatise — Mathematical Formulation

---

## Abstract
This treatise delivers a rigorous mathematical analysis of the Bass-Quillen conjecture on finitely generated projective modules over polynomial extensions. We detail Horrocks' criterion for local rings, Quillen's local-global patching principle, and the induction mechanics over multiple polynomial indeterminates $R[T_1, \ldots, T_n]$.

## 1. Formal Formulation
Let $R$ be a regular Noetherian commutative ring. The Bass-Quillen conjecture asserts that every finitely generated projective $R[T_1, \ldots, T_n]$-module $P$ is extended from $R$. That is, there exists a projective $R$-module $P_0$ such that:
$$P \cong P_0 \otimes_R R[T_1, \ldots, T_n]$$

## 2. Horrocks' Theorem: The Local Reduction Engine
Horrocks proved that if $A$ is a local ring and $P$ is a finitely generated projective module over $A[T]$ that contains a unimodular element upon monic polynomial localization, then $P$ is free:
$$P_f 	ext{ free for monic } f \in A[T] \implies P 	ext{ is free over } A[T]$$
This theorem forms the core inductive pivot: reducing global projective bundles to localized polynomial extensions where unimodular vectors can be factored via elementary transvections.

## 3. Quillen's Local-Global Patching Theorem
Quillen established the crowning structural theorem:
If $M$ is a finitely presented module over $R[T]$, and for every maximal ideal $\mathfrak{m} \subset R$, the localized module $M_\mathfrak{m}$ is extended from $R_\mathfrak{m}$, then $M$ is extended from $R$.
$$orall \mathfrak{m} \in \operatorname{MaxSpec}(R), \; M_\mathfrak{m} \cong (M_0)_\mathfrak{m} \otimes_{R_\mathfrak{m}} R_\mathfrak{m}[T] \implies M \cong M_0 \otimes_R R[T]$$
Combined with Lindel's and Popescu's solutions for geometric regular rings, this closes the Bass-Quillen conjecture across all smooth schemes over fields and Dedekind domains.
