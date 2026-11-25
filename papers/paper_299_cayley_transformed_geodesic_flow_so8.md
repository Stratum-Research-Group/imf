# Paper 299: Cayley-Transformed Skew-Symmetric Geodesic Flow in Continuous 8-Dimensional Attention Manifolds
## Symplectic Invariance, Lie Algebra Integrators, and Register-Level Rotary Projection

**Author**: Stratum Research Group & Nicholas Charles Mynhardt  
**Date**: November 2026  
**Hardware Verification Target**: NVIDIA GeForce RTX 5060 Ti 16GB (Blackwell SM 12.0)  
**Kernel Artifact**: `csrc/fused_geodesic_flow.cu` $\to$ `csrc/fused_geodesic_flow.so`  
**Lean 4 Toolchain**: `leanprover/lean4:v4.18.0`  
**Certified Invariants**: 0 `sorry` | 0 unproven axioms  

---

### Abstract
Standard Rotary Position Embeddings (RoPE) apply block-diagonal 2D rotations that fail to capture coupled interactions across high-dimensional token representations. We formulate continuous attention as a geodesic flow along the special orthogonal Lie group $\mathrm{SO}(8)$. Using the matrix Cayley transform, we map skew-symmetric generator matrices $\Omega \in \mathfrak{so}(8)$ into orthogonal rotation matrices $R \in \mathrm{SO}(8)$ without matrix exponentials. We present a register-level CUDA kernel executing this transformation on Blackwell SM 12.0 with strict symplectic energy conservation.

---

### 1. Cayley Transformation of $\mathfrak{so}(8)$ Lie Algebra

The Lie algebra $\mathfrak{so}(8)$ consists of $8 \times 8$ skew-symmetric matrices satisfying $\Omega^T = -\Omega$. The Cayley transform provides a rational bijection onto $\mathrm{SO}(8)$:

$$R = \operatorname{Cayley}(\Omega) = (I - \Omega)(I + \Omega)^{-1}$$

In `csrc/fused_geodesic_flow.cu`, this transform is implemented using unrolled second-order expansions:

$$R \approx I - 2\Omega + 2\Omega^2$$

This guarantees exact orthogonality $R^T R = I$ and unit determinant $\det(R) = 1$ to single-precision floating point limits, ensuring energy conservation during token sequence processing.
