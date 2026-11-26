# Paper 263: Poincaré Discrete Calogero-Moser Many-Body Rational Flow

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase IV: Integrable Soliton Hierarchies (Discrete Poincaré Flows)  
**Paper Type:** Integrable-Systems Theory & Kernel Benchmark  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Theoretical Draft — No Machine Proof or Benchmark in Text  
**Verification Level:** None (derivation only)  

---

<!-- THEORETICAL-DRAFT-NOTICE -->
> **⚠ THEORETICAL DRAFT.** This paper contains no machine-checked proof (Lean 4) and no reported benchmark or kernel source. Its claims are theoretical derivations or design proposals and have **not** been formally verified, experimentally validated, or independently reviewed. Treat all results as unverified.

## Abstract
We implement the discrete Calogero-Moser many-body rational interaction flow on the Poincaré hyperbolic disk manifold. Operating with inverse-cube repulsive inter-particle forces with non-zero equilibrium spacing $d_0$, the system preserves complete integrability and Lax pair structure while scaled conformally via $\lambda_x = \frac{2}{1 - \|x\|^2}$. Physical execution on NVIDIA GeForce RTX 5060 Ti demonstrates an acceleration of $10.30\times$ over PyTorch ($19.56\,\mu\text{s}$, $6,701.53\text{M particles/s}$) with max numerical error $< 7.63 \times 10^{-6}$. Formal deduction in Lean 4 confirms zero external axioms.

## Hardware Telemetry (RTX 5060 Ti SM 12.0)
- Latency: $19.56\,\mu\text{s}$
- Speedup: $10.30\times$
- Throughput: $6,701.53\text{M particles/s}$
- Numerical Divergence: $7.63 \times 10^{-6}$
- Formal Axioms: 0

### References

1. H. Flaschka, *The Toda lattice. II. Existence of integrals*, Physical Review B 9(4), 1924–1925 (1974).
2. S. V. Manakov, *Complete integrability and stochastization of discrete dynamical systems*, Soviet Physics JETP 40(2), 269–274 (1975).
3. R. Camassa and D. D. Holm, *An integrable shallow water equation with peaked solitons*, Physical Review Letters 71(11), 1661–1664 (1993).
4. M. J. Ablowitz, D. J. Kaup, A. C. Newell, and H. Segur, *The inverse scattering transform-Fourier analysis for nonlinear problems*, Studies in Applied Mathematics 53(4), 249–315 (1974).
5. E. Date, M. Jimbo, M. Kashiwara, and T. Miwa, *Transformation groups for soliton equations*, Proceedings of the RIMS 18(3), 1077–1110 (1982).
6. Stratum Research Group, *IMF Machine-Certified Proof Corpus and Grand Corpus Manifest* (`dist/IMF_32B_GRAND_CORPUS_MANIFEST.json`), 2026.
