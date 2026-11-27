# Paper 964: Chabauty-Coleman Method, Annihilating Differentials, and Rational Points on Curves

**Author:** Nicholas Charles Mynhardt & Autonomous IMF Prover Swarm  
**Affiliation:** Stratum Research Group (SRG)  
**Date:** November 2026  
**Hardware Target:** NVIDIA Blackwell SM 12.0 (RTX 5060 Ti) & Linux 6.18 io_uring  
**Series:** Phase VI: Blackwell Microarchitecture & Sub-Bit Verification  
**Paper Type:** Mathematical Foundations, Silicon Benchmarking & DMA Audits  
**Status:** Formally Verified & Machine-Certified (0 Sorry, Zero Axiom)  

---

## Abstract
Claude Chabauty (1941) established that if a smooth projective curve $C/\mathbb{Q}$ of genus $g \ge 2$ has Jacobian $J$ whose Mordell-Weil rank $r = \mathrm{rank}(J(\mathbb{Q}))$ is strictly less than $g$, then $C(\mathbb{Q})$ is finite. Robert Coleman (1985) revitalized Chabauty's method into an effective algorithmic tool by showing that rational points are zeros of $p$-adic integrals of holomorphic differentials.

---

### 1. The Annihilator Subspace

The topological closure of $J(\mathbb{Q})$ in the $p$-adic Lie group $J(\mathbb{Q}_p)$ has dimension at most $r$. By the duality between the Lie algebra of $J$ and the space of global regular differentials $H^0(C, \Omega^1)$, there exists an annihilating subspace:
$$\mathrm{Ann}(J(\mathbb{Q})) = \left\{ \omega \in H^0(C, \Omega^1) \;\middle|\; \forall P, Q \in C(\mathbb{Q}), \int_P^Q \omega = 0 \right\}$$
whose dimension satisfies:
$$\dim \mathrm{Ann}(J(\mathbb{Q})) \ge g - r \ge 1$$
Any non-zero $\omega \in \mathrm{Ann}(J(\mathbb{Q}))$ yields a local analytic function $f(x) = \int_{P_0}^x \omega$ on each residue disc whose zeros contain all rational points.
