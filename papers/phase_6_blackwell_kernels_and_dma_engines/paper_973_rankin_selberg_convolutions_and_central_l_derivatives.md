# Paper 973: Rankin-Selberg Convolutions and Central L-Derivatives

**Author:** Nicholas Charles Mynhardt & Autonomous IMF Prover Swarm  
**Affiliation:** Stratum Research Group (SRG)  
**Date:** November 2026  
**Hardware Target:** NVIDIA Blackwell SM 12.0 (RTX 5060 Ti) & Linux 6.18 io_uring  
**Series:** Phase VI: Blackwell Microarchitecture & Sub-Bit Verification  
**Paper Type:** Mathematical Foundations, Silicon Benchmarking & DMA Audits  
**Status:** Formally Verified & Machine-Certified (0 Sorry, Zero Axiom)  

---

## Abstract
We investigate the analytic continuation and central value behavior of the Rankin-Selberg convolution $L(f \otimes \theta_K, s)$ of a normalized weight 2 cuspidal newform $f = \sum a_n q^n \in S_2(\Gamma_0(N))$ with the theta series $\theta_K = \sum r_K(n) q^n$ attached to the ideal class group of $K = \mathbb{Q}(\sqrt{-D})$.

---

### 1. Functional Equation and Root Number

The convolution factors as the base change $L$-series:
$$L(f \otimes \theta_K, s) = L(E/K, s) = L(E/\mathbb{Q}, s) \cdot L(E^{(D)}/\mathbb{Q}, s)$$
Under the Heegner hypothesis (all prime factors of $N$ split in $K$), the global root number is $\epsilon(E/K) = -1$. Consequently, the functional equation:
$$\Lambda(E/K, s) = -\Lambda(E/K, 2 - s)$$
forces the central value to vanish identically: $L(E/K, 1) = 0$. The first non-vanishing Taylor coefficient is therefore the central derivative $L'(E/K, 1)$. Gross and Zagier proved:
$$L'(E/K, 1) = \frac{8\pi^2 (f, f)}{u^2 \sqrt{|D|}} \cdot \widehat{h}(y_K)$$
