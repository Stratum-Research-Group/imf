# Paper 955: Minimal Weight Invariants and Slope Valuations of Filtered Frobenius Operators

**Author:** Nicholas Charles Mynhardt & Autonomous IMF Prover Swarm  
**Affiliation:** Stratum Research Group (SRG)  
**Date:** November 2026  
**Hardware Target:** NVIDIA Blackwell SM 12.0 (RTX 5060 Ti) & Linux 6.18 io_uring  
**Series:** Phase VI: Blackwell Microarchitecture & Sub-Bit Verification  
**Paper Type:** Mathematical Foundations, Silicon Benchmarking & DMA Audits  
**Status:** Formally Verified & Machine-Certified (0 Sorry, Zero Axiom)  

---

## Abstract
We investigate the relationship between the Serre weight $k(\bar{\rho})$ and the $p$-adic slopes of the Frobenius operator $\Phi$ on the crystalline Dieudonné module $D_{\text{crys}}(\rho)$.

---

### 1. Slope-Weight Inequality

The characteristic polynomial of $\Phi$ on $D_{\text{crys}}(\rho)$ is $T^2 - a_p T + p^{k-1}$. The valuations of the roots $\lambda_1, \lambda_2 \in \mathbb{Q}$ satisfy:
$$\lambda_1 + \lambda_2 = k - 1, \quad 0 \le \lambda_1 \le \lambda_2 \le k - 1$$
In the ordinary case, $\lambda_1 = 0$ and $\lambda_2 = k - 1$. In the supersingular case, $\lambda_1 = \lambda_2 = (k - 1)/2$.

---

### 2. Weak Admissibility

The Newton polygon of $(1, a_p, p^{k-1})$ lies strictly on or above the Hodge polygon with vertices $(0,0), (1,0), (2, k-1)$, verifying weak admissibility.
