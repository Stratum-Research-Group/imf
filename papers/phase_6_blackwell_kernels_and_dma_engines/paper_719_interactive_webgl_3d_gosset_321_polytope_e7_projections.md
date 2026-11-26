# Paper 719: Interactive WebGL 3D Geometry of the Gosset 3₂₁ Polytope and E₇ Coxeter Projections

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase VI: Blackwell Kernels, Algebraic Theorems & Direct-DMA Engines  
**Paper Type:** Geometric Visualization & Lie Group Computation  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Interactive WebGL 3D Visualization — Operational  
**Verification Level:** Verified on Modern Browsers, Three.js r128 & WebGL 2.0  

---

### Abstract
We detail the mathematical derivation and interactive Three.js WebGL visualization (`docs/assets/gosset_321_e7_3d.html`) of the Gosset $3_{21}$ semi-regular 7-polytope. Comprising 56 vertices and 756 edges, the polytope embodies the miniscule 56-dimensional fundamental representation of the exceptional Lie algebra $\mathfrak{e}_7$. We derive the 8-dimensional Cartesian coordinates with $\sum x_i = 0$, compute the adjacency graph, and formulate parametric Coxeter harmonic projections into 3D Euclidean space.

---

### 1. Geometric Construction in 8-Space
The 56 vertices of the Gosset $3_{21}$ polytope are embedded in $\mathbb{R}^8$ within the hyperplane $\sum_{i=1}^8 x_i = 0$:
1. **Type A (28 vertices):** Permutations of vectors with two coordinates equal to $+1$ and six coordinates equal to $-\frac{1}{3}$:
$$\binom{8}{2} = 28 \text{ vertices, with } 2(1) + 6(-1/3) = 0$$
2. **Type B (28 vertices):** Permutations of vectors with two coordinates equal to $-1$ and six coordinates equal to $+\frac{1}{3}$:
$$\binom{8}{2} = 28 \text{ vertices, with } 2(-1) + 6(1/3) = 0$$

### 2. Edge Connectivity and Distance Metric
Adjacent vertices in the $3_{21}$ polytope are separated by squared Euclidean distance:
$$\|v_a - v_b\|^2 = \left(1 - \left(-\frac{1}{3}\right)\right)^2 + \left(-\frac{1}{3} - 1\right)^2 = \frac{16}{9} + \frac{16}{9} = \frac{32}{9} \approx 3.5555556$$
Evaluating all $\binom{56}{2} = 1,540$ pairwise distances yields exactly 756 edges, forming a vertex-transitive graph of degree 27.

### 3. Real-Time WebGL Interaction
The generator script (`tools/visualizers/generate_gosset_321_e7_3d.py`) emits a standalone Three.js HTML artifact. Users interactively modulate the 7D phase rotation angle $\theta$ and radial dispersion scale, observing the dynamic projection of the 56 miniscule weights into concentric double-heptagonal rings.

---
*Infinite Mathematical Foundations (IMF) Research Series — Stratum Research Group (2026)*
