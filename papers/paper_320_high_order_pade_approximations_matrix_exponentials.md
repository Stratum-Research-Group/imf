# Paper 320: High-Order Padé Approximations of Matrix Exponentials in Skew-Symmetric Lie Algebra Attention Manifolds
## Unitary Preservation and Register-File Scaling on Blackwell SM 12.0

**Author**: Stratum Research Group & Nicholas Charles Mynhardt  
**Date**: November 2026  
**Hardware Verification Target**: NVIDIA GeForce RTX 5060 Ti 16GB (Blackwell SM 12.0)  
**Lean 4 Toolchain**: `leanprover/lean4:v4.18.0`  
**Certified Invariants**: 0 `sorry` | 0 unproven axioms  

---

### Abstract
While the rational Cayley transform provides a fast first-order approximation to Lie group rotations, higher-order rotary interactions require computing the true matrix exponential $\exp(\Omega)$ for skew-symmetric generator matrices $\Omega \in \mathfrak{so}(8)$. We evaluate high-order [6/6] Padé approximants combined with scaling and squaring. Implemented directly inside Blackwell SM 12.0 warp registers, our kernel achieves double-precision rotational accuracy while eliminating transcendent function evaluations and shared memory bank conflicts.
