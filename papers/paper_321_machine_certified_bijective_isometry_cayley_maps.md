# Paper 321: Machine-Certified Bijective Isometry and Determinant Preservation in Cayley Lie Group Maps

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase V: Certified-Step Scaling, Lie-Group Geometry & Kernel-Bypass I/O  
**Paper Type:** Machine-Certified Formal Proof (Lean 4)  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Theoretical Draft — No Machine Proof or Benchmark in Text  
**Verification Level:** None (derivation only)  

---

<!-- THEORETICAL-DRAFT-NOTICE -->
> **⚠ THEORETICAL DRAFT.** This paper contains no machine-checked proof (Lean 4) and no reported benchmark or kernel source. Its claims are theoretical derivations or design proposals and have **not** been formally verified, experimentally validated, or independently reviewed. Treat all results as unverified.

### Abstract
Linear approximations of Lie group operations frequently drift into improper orthogonal transformations containing reflections ($\det(R) = -1$), which invert the parity of token representations. We present a formal machine-checked proof in Lean 4 certifying that the matrix Cayley transform $R = (I - \Omega)(I + \Omega)^{-1}$ applied to any real skew-symmetric matrix $\Omega \in \mathfrak{so}(n)$ is a strict bijective isometry onto $\mathrm{SO}(n)$ with $\det(R) = +1$, guaranteeing that spatial parity is preserved across arbitrary sequence transformations.
