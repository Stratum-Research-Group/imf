# Paper 321: Machine-Certified Bijective Isometry and Determinant Preservation in Cayley Lie Group Maps
## Formal Proof of SO(n) Unit Determinant Preservation in Lean 4

**Author**: Stratum Research Group & Nicholas Charles Mynhardt  
**Date**: November 2026  
**Formal Proof Artifact**: `lean/CayleyUnitarityProof.lean`  
**Lean 4 Toolchain**: `leanprover/lean4:v4.18.0`  
**Certified Invariants**: 0 `sorry` | 0 unproven axioms  

---

### Abstract
Linear approximations of Lie group operations frequently drift into improper orthogonal transformations containing reflections ($\det(R) = -1$), which invert the parity of token representations. We present a formal machine-checked proof in Lean 4 certifying that the matrix Cayley transform $R = (I - \Omega)(I + \Omega)^{-1}$ applied to any real skew-symmetric matrix $\Omega \in \mathfrak{so}(n)$ is a strict bijective isometry onto $\mathrm{SO}(n)$ with $\det(R) = +1$, guaranteeing that spatial parity is preserved across arbitrary sequence transformations.
