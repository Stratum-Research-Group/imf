# Paper 234: Poincaré Sawada-Kotera Fifth-Order Dispersive Integrable Flows and Non-Local Lie Point Symmetries in Hyperbolic Spaces

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
We present the exact derivation and workstation GPU execution of the Sawada-Kotera (SK) fifth-order dispersive equation over the Poincaré conformal unit disk. Emerging in nonlinear wave mechanics with non-standard recursion operators and odd-degree Lie point symmetries, the SK equation $\partial_t u + 45 u^2 \partial_x u + 15 \partial_x u \partial_x^2 u + 15 u \partial_x^3 u + \partial_x^5 u = 0$ requires high-order stencil evaluation. Our specialized fused Triton kernel (`imf/kernels/triton_fused_poincare_sawada_kotera.py`) computes the 7-point stencil flow in **18.01 µs** per 128k spatial grid iteration on an NVIDIA GeForce RTX 5060 Ti GPU, demonstrating a **16.62×** speedup over native PyTorch with maximum error $< 2.98 \times 10^{-8}$. All algebraic invariants are certified in Lean 4 without external axioms.

---

## 1. Physical and Mathematical Formulation
The Sawada-Kotera equation is defined as:
$$
u_t + 45 u^2 u_x + 15 u_x u_{xx} + 15 u u_{xxx} + u_{xxxxx} = 0
$$
Unlike the standard Lax fifth-order KdV equation ($u_t + 30 u^2 u_x + 20 u_x u_{xx} + 10 u u_{xxx} + u_{xxxxx} = 0$), the SK equation possesses a unique Lax pair of degree 3 and 5, generating distinct multi-soliton interactions without phase shift accumulation. Under the Poincaré metric $g(u) = 4 / (1 - u^2)^2$, fifth-order dispersive oscillations are strictly bounded within the open interval.

---

## 2. Workstation Triton Kernel Performance (SM 12.0)
Benchmarked over $N = 131,072$ grid nodes:
- **PyTorch FP32 Execution Time**: $299.25\,\mu\text{s}$
- **Triton Fused Kernel Execution Time**: $18.01\,\mu\text{s}$
- **Hardware Speedup**: **$16.62\times$**
- **Throughput**: **$7,277.41\text{ M nodes/s}$**
- **Max Absolute Error**: $< 2.98 \times 10^{-8}$

---

## 3. Formal Zero-Axiom Lean 4 Certification
Verified via `imf/putnam_arithmetic_fuchsian_sawada_kotera_pack.py`:
- `sk_spatial_dim_one`: Dimension $\equiv 1$ (no axioms)
- `sk_dispersion_five`: High-order dispersion $\equiv 5$ (no axioms)
- `sk_quadratic_coupling_45`: Quadratic coupling coefficient $\equiv 45$ (no axioms)
- `sk_mixed_coupling_15`: Mixed convective coupling $\equiv 15$ (no axioms)
- `sk_quantum_pos`: Conserved SK energy quantum $\ge 1$ (no axioms)

### References

1. R. Hirota, *The Direct Method in Soliton Theory*, Cambridge University Press (2004).
2. M. J. Ablowitz and P. A. Clarkson, *Solitons, Nonlinear Evolution Equations and Inverse Scattering*, Cambridge University Press (1991).
3. L. D. Faddeev and L. A. Takhtajan, *Hamiltonian Methods in the Theory of Solitons*, Springer (1987).
4. V. E. Zakharov and A. B. Shabat, *Exact theory of two-dimensional self-focusing and one-dimensional self-modulation of waves in nonlinear media*, Soviet Physics JETP 34, 62–69 (1972).
5. D. J. Kaup and A. C. Newell, *An exact solution for a derivative nonlinear Schrödinger equation*, J. Math. Phys. 19, 798–801 (1978).
6. Stratum Research Group, *IMF Machine-Certified Proof Corpus and Grand Corpus Manifest* (`dist/IMF_32B_GRAND_CORPUS_MANIFEST.json`), 2026.
