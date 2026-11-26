# Paper 725: Interactive WebGL 3D Geometry of the Gosset 4₂₁ Polytope and E₈ Root Honeycombs

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase VI: Blackwell Kernels, Algebraic Theorems & Direct-DMA Engines  
**Paper Type:** Geometric Visualization & Lie Group Computation  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Interactive WebGL 3D Visualization — Operational  
**Verification Level:** Verified on Modern Browsers, Three.js r128 & WebGL 2.0  

---

### Abstract
We present the mathematical construction and interactive Three.js WebGL visualization (`docs/assets/gosset_421_e8_3d.html`) of the Gosset $4_{21}$ semi-regular 8-polytope. Comprising 240 vertices and 6,720 edges, the polytope forms the convex hull of the 240 root vectors of the exceptional Lie algebra $\mathfrak{e}_8$. We formulate the exact integer coordinates in $\mathbb{R}^8$, compute the edge connectivity graph, and derive harmonic golden-ratio projections into 3D Euclidean space.

---

### 1. Root Coordinate Realization
The 240 vertices of the $4_{21}$ polytope fall into two distinct orbits under the Weyl group $W(D_8) \subset W(E_8)$:
1. **Integer Orbit (112 vertices):** All permutations and sign variations of $(\pm 1, \pm 1, 0, 0, 0, 0, 0, 0)$ with squared norm 2.
2. **Half-Integer Orbit (128 vertices):** All vectors $(\pm 1/2, \dots, \pm 1/2)$ with an even number of minus signs, also having squared norm $\sum (1/4) = 2$.

### 2. Edge Topology
Two vertices $u, v$ are joined by an edge if their inner product $\langle u, v \rangle = 1$ (distance squared $\|u - v\|^2 = 2$). Across all $\binom{240}{2} = 28,680$ candidate pairs, exactly 6,720 edges satisfy this condition, forming a regular graph of degree 56.

### 3. Real-Time Interaction
The WebGL implementation dynamically projects the 8-dimensional coordinates into 3D using parameterized phase angles $\theta$, enabling users to observe the 8 concentric 30-gons corresponding to the Coxeter plane of $E_8$.

---
*Infinite Mathematical Foundations (IMF) Research Series — Stratum Research Group (2026)*
