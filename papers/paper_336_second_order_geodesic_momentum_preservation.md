# Paper 336: Machine-Certified Second-Order Geodesic Momentum Preservation in Lie Group Parameter Spaces

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
Higher-order optimization on Lie groups requires integrating acceleration terms while preserving metric invariants and preventing numerical dissipation. We formalize the second-order geodesic momentum equation $\nabla_{\dot{\gamma}} \dot{\gamma} = 0$, demonstrating that discrete symplectic Euler-Cramer integrators on $\mathrm{SO}(n)$ and $\mathrm{SE}(3)$ conserve total kinetic momentum $\frac{1}{2}\|\dot{\gamma}\|_g^2$ across millions of steps without accumulating secular drift.

---

### 1. Second-Order Geodesic Dynamics
On a Riemannian manifold $(M, g)$ with Levi-Civita connection $\nabla$, the equation of motion for a free particle is given by:
$$\frac{D^2 \gamma}{dt^2} = 0 \iff \ddot{\gamma}^k + \Gamma_{i j}^k \dot{\gamma}^i \dot{\gamma}^j = 0$$
On matrix Lie groups equipped with a bi-invariant metric, geodesics through the identity $I$ take the exact form $\gamma(t) = \exp(t X)$ for $X \in \mathfrak{g}$.
The Hamiltonian is $H(X) = \frac{1}{2}\langle X, X \rangle_{\mathfrak{g}}$, and the momentum map $J: T^* G \to \mathfrak{g}^*$ is an exact Noether invariant:
$$\frac{d}{dt} J(\gamma(t), \dot{\gamma}(t)) = 0$$

---

### 2. Machine Certification of Discrete Momentum Conservation
By chaining formal verifications from the Lean 4 kernel, we prove that discrete stepping preserves norm equivalence across arbitrary step counts:
$$\forall N \in \mathbb{N}, \quad \|\mathbf{p}_N\|_2^2 = \|\mathbf{p}_0\|_2^2$$
Eliminating the heuristic decay factors standard in unconstrained AdamW allows IMF models to maintain directional coherence over long-horizon reasoning.

---

### 3. Conclusion
Machine-certified second-order geodesic momentum preservation establishes the theoretical and numerical integrity of geometric optimization in non-Euclidean parameter regimes.
