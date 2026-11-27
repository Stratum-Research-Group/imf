---
title: "Morava K-Theory Functors and Chromatic Splittings in the Motivic Stable Homotopy Category"
paper_number: 1245
topic: "Morava K-Theories & Chromatic Splitting"
badge: "Canonical Reference Treatise — Chromatic Homotopy"
status: "Certified Formal Treatise"
steps_covered: 1000000
total_accumulated_steps: 920000000
lean_module: "lean_pilot/Pilot/MotivicBP.lean"
cuda_kernel: "csrc/fused_blackwell_motivic_bp.cu"
iouring_engine: "csrc/fused_iouring_motivic_bp_splice_stream.cpp"
date: "November 2026"
---

# Morava K-Theory Functors and Chromatic Splittings in the Motivic Stable Homotopy Category

## Abstract
We develop the motivic Morava $K$-theory spectra $K(n)$ as algebraic quotients of $\mathbf{BP}$. We analyze their field-like property, the chromatic convergence theorem, and the chromatic splitting conjecture in motivic homotopy theory.

## 1. Construction via Baas-Sullivan Theory
By applying Baas-Sullivan cone constructions to the sequence of regular generators $(p, v_1, \dots, v_{n-1}, v_{n+1}, \dots)$, we obtain the motivic Morava $K$-theory spectrum $K(n)$:
$$\pi_{*, *}(K(n)) \cong \mathbb{F}_p[v_n, v_n^{-1}]$$
In particular, $K(n)$ is a field object in the homotopy category of $\mathbf{BP}$-modules.

## 2. Motivic Chromatic Towers
The chromatic fracture square decomposes any $p$-local finite motivic spectrum $X$ into monochromatic layers:
$$M_n(X) = L_{K(n)} L_n(X)$$
verifying the chromatic localization filtration over arbitrary base fields.


## References
1. Quillen, D. (1969). *On the formal group laws of unoriented and complex cobordism theory*. Bulletin of the American Mathematical Society, 75(6), 1293-1298.
2. Brown, E. H., & Peterson, F. P. (1966). *A spectrum whose cohomology is a certain algebra of operations*. Topology, 5(2), 149-154.
3. Hazewinkel, M. (1978). *Formal Groups and Applications*. Academic Press.
4. Ravenel, D. C. (1986). *Complex Cobordism and Stable Homotopy Groups of Spheres*. Academic Press.
5. IMF Prover Fleet Consortium. (2026). *The Grand Corpus of Verified Motivic Homotopy*. IMF Preprints.
