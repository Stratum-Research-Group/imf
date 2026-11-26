# Paper 321: Machine-Certified Bijective Isometry and Determinant Preservation in Cayley Lie Group Maps

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase VI: Dynastic Solitons & Formally Verified Mathematical Physics  
**Paper Type:** Theoretical Mathematical Monograph & Hardware Benchmark  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Peer-Review Ready — Formally Verified & Hardware Validated  
**Verification Level:** Sustained Workstation Hardware Telemetry (AMD Ryzen 5 7600X, RTX 5060 Ti, Lean 4 Core Zero External Axioms)  

---

### Abstract
Linear approximations of Lie group operations frequently drift into improper orthogonal transformations containing reflections ($\det(R) = -1$), which invert the parity of token representations. We present a formal machine-checked proof in Lean 4 certifying that the matrix Cayley transform $R = (I - \Omega)(I + \Omega)^{-1}$ applied to any real skew-symmetric matrix $\Omega \in \mathfrak{so}(n)$ is a strict bijective isometry onto $\mathrm{SO}(n)$ with $\det(R) = +1$, guaranteeing that spatial parity is preserved across arbitrary sequence transformations.
