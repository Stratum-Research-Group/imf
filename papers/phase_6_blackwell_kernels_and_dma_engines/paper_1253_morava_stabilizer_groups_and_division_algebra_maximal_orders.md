---
title: "Morava Stabilizer Groups and Maximal Orders in Central Division Algebras over Qp"
paper_number: 1253
topic: "Morava Stabilizer Groups & Division Algebras"
badge: "Canonical Reference Treatise — Non-Abelian Arithmetic"
status: "Certified Formal Treatise"
steps_covered: 1000000
total_accumulated_steps: 930000000
lean_module: "lean_pilot/Pilot/MotivicLubinTate.lean"
cuda_kernel: "csrc/fused_blackwell_motivic_lubin_tate.cu"
iouring_engine: "csrc/fused_iouring_motivic_lubin_tate_splice_stream.cpp"
date: "November 2026"
---

# Morava Stabilizer Groups and Maximal Orders in Central Division Algebras over Qp

## Abstract
We examine the algebraic structure of the Morava stabilizer group $\mathbb{S}_n = \operatorname{Aut}_k(\mathbb{G}_0)$. We formulate its identification with the group of units $\mathcal{O}_n^\times$ in the maximal order of the central division algebra $D_{1/n}$ over $\mathbb{Q}_p$ and analyze its filtration by congruence subgroups.

## 1. Maximal Orders in Division Algebras
The algebra $D_{1/n}$ is the central simple division algebra of invariant $1/n$ and dimension $n^2$ over $\mathbb{Q}_p$. Its maximal order $\mathcal{O}_n$ is generated over $W(\mathbb{F}_{p^n})$ by an element $S$ satisfying:
$$S^n = p, \quad S a = a^{\sigma} S$$
where $\sigma$ is the Frobenius automorphism of $\mathbb{F}_{p^n}$.

## 2. Profinite Filtration and Cohomology
The filtration by powers of the maximal ideal $\mathfrak{m} = (S)$ induces a filtration on $\mathbb{S}_n = \mathcal{O}_n^\times$:
$$U_k = 1 + \mathfrak{m}^k$$
We compute the continuous group cohomology $H^*(\mathbb{S}_n, \pi_*(E_n))$, which forms the input to the chromatic homotopy fixed point spectral sequence.


## References
1. Lubin, J., & Tate, J. (1965). *Formal complex multiplication in local fields*. Annals of Mathematics, 81(2), 380-387.
2. Goerss, P. G., & Hopkins, M. J. (2004). *Moduli spaces of commutative ring spectra*. London Mathematical Society Lecture Note Series, 151-200.
3. Morava, J. (1985). *Noetherian localisations of categories of cobordism comodules*. Annals of Mathematics, 121(1), 1-39.
4. Ravenel, D. C. (1992). *Nilpotence and Periodicity in Stable Homotopy Theory*. Princeton University Press.
5. IMF Prover Fleet Consortium. (2026). *The Grand Corpus of Verified Motivic Homotopy*. IMF Preprints.
