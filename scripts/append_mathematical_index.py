#!/usr/bin/env python3
"""
scripts/append_mathematical_index.py
Appends a Wolfram-grade comprehensive Mathematical & Categorical Index and Symbol Glossary
to the appendices of Volumes I, II, and III.
"""
import os

VOL_INDICES = {
    "docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v01.md": """

---

# Appendix A: Comprehensive Mathematical & Systems Index (Volume I)

### Index of Mathematical Symbols & Operators
- **$\mathbf{d}_k$**: Discrete exterior derivative / coboundary matrix operator ($\mathbf{d}_k \colon C^k(K) \to C^{k+1}(K)$). Satisfies exact machine nilpotency $\mathbf{d} \circ \mathbf{d} = 0$.
- **$\partial_k$**: Simplicial boundary operator ($\partial_k \colon C_k(K) \to C_{k-1}(K)$). Satisfies $\partial \circ \partial = 0$.
- **$\star_k$**: Discrete circumcentric Hodge star operator ($\star_k \colon C^k(K) \to C^{n-k}(\star K)$).
- **$\boldsymbol{\delta}_k$**: Discrete codifferential operator ($\boldsymbol{\delta}_k = \star^{-1} \mathbf{d} \star$).
- **$\boldsymbol{\Delta}_k$**: Discrete Hodge-Laplace-Beltrami operator ($\boldsymbol{\Delta} = \mathbf{d}\boldsymbol{\delta} + \boldsymbol{\delta}\mathbf{d}$).
- **$\mathcal{H}^k(K)$**: Vector space of harmonic $k$-forms ($\ker(\boldsymbol{\Delta}_k) \cong H^k(K; \mathbb{R})$).
- **$e_i(t)$**: Cartan moving frame (orthonormal local basis on tangent bundle $T\mathcal{M}$).
- **$\theta^i$**: Solder 1-form measuring intrinsic frame translation ($\mathrm{d}x = \sum \theta^i e_i$).
- **$\omega^i_j$**: Connection 1-form in $\mathfrak{so}(n)$ governing parallel transport ($\mathrm{d}e_i = \sum \omega^j_i e_j$).
- **$\Omega^i_j$**: Curvature 2-form ($\Omega = \mathrm{d}\omega + \omega \wedge \omega$).
- **$\operatorname{Cay}(A)$**: Cayley transform conformal mapping skew-symmetric matrix $A \in \mathfrak{so}(n)$ to rotation $U \in \mathrm{SO}(n)$: $\operatorname{Cay}(A) = (I-A)(I+A)^{-1}$.
- **$\mathcal{C}\ell(p, q)$**: Clifford geometric algebra over signature $(p, q)$.
- **$\mathcal{R}$**: Bivector rotor sandwich operator ($\mathcal{R} = \exp(-\frac{1}{2} B), v' = \mathcal{R} v \mathcal{R}^\dagger$).

### Index of Systems & Hardware Architecture Terms
- **Blackwell SM 12.0**: NVIDIA GPU architecture with 256 KB register file per SM and 4 dual-issue warp schedulers.
- **TMA (Tensor Memory Accelerator)**: Hardware 5D asynchronous DMA engine bypassing arithmetic ALU pipelines.
- **`__shfl_sync` / `__shfl_down_sync`**: Single-cycle intra-warp register exchange butterfly intrinsics.
- **`io_uring`**: Linux 6.18 kernel-bypass asynchronous ring buffer architecture.
- **`IORING_SETUP_SQPOLL`**: Dedicated kernel thread continuously polling submission queue without system calls.
- **O_DIRECT**: Strict 4096-byte aligned kernel bypass memory mapping directly to physical NVMe controller.
""",
    "docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v02.md": """

---

# Appendix A: Comprehensive Mathematical & Systems Index (Volume II)

### Index of Mathematical Symbols & Polytope Structures
- **$\mathbb{O}$**: The 8-dimensional non-associative normed division algebra of octonions.
- **$G_2$**: 14-dimensional exceptional Lie group; automorphism group of the octonions ($\operatorname{Aut}(\mathbb{O})$).
- **$\operatorname{Spin}(7)$**: 21-dimensional exceptional spin group preserving the self-dual Cayley 4-form in $\mathbb{R}^8$.
- **$\phi_0$**: Associative 3-form in $\mathbb{R}^7$ defining $G_2$ calibration geometry.
- **$\psi_0$**: Coassociative 4-form in $\mathbb{R}^7$ ($\psi_0 = \star \phi_0$).
- **$\Lambda(E_8)$**: The exceptional root lattice in $\mathbb{R}^8$; unique even unimodular lattice in dimension 8.
- **$\Phi(E_8)$**: The 240 minimal root vectors of $E_8$ with $\|x\|^2 = 2$ (112 integral + 128 half-integral roots).
- **Gosset $4_{21}$ Polytope**: Semi-regular 8-polytope whose 240 vertices are the roots of $E_8$. Possesses strictly **17,280 regular 7-simplices** ($\alpha_7$) and **2,160 regular 7-orthoplexes** ($\beta_7$), summing to **19,440 facets**.
- **$W(E_8)$**: Weyl reflection group of $E_8$, order $2^{14} \cdot 3^5 \cdot 5^2 \cdot 7 = \mathbf{696,729,600}$.
- **$\Delta_8$**: Optimal sphere packing density in $\mathbb{R}^8$: $\Delta_8 = \pi^4 / 384$ (Maryna Viazovska, 2016).
- **$\Lambda_{24}$**: The 24-dimensional Leech lattice; unique even, unimodular, rootless lattice in $\mathbb{R}^{24}$.
- **$\tau_{24}$**: Kissing number of $\Lambda_{24}$, strictly **196,560** minimal vectors of squared norm 4 (or 32 unscaled).
  - Orbit 1 (Cross): $1,104$ vectors of type $(\pm 4^2, 0^{22})$.
  - Orbit 2 (Octad): $97,152$ vectors of type $(\pm 2^8, 0^{16})$ on Steiner octads.
  - Orbit 3 (Odd): $98,304$ vectors of type $(\mp 3, \pm 1^{23})$ with Golay signs.
- **$\mathcal{G}_{24}$**: Extended binary Golay code $[24, 12, 8]_2$ containing 4,096 codewords and 759 octads.
- **$S(5, 8, 24)$**: Witt's Steiner system covering all 42,504 5-element subsets with zero overlap.
- **$\operatorname{Co}_0$**: Conway sporadic group of order $2^{22} \cdot 3^9 \cdot 5^4 \cdot 7^2 \cdot 11 \cdot 13 \cdot 23 \approx 8.315 \times 10^{18}$.
- **$\operatorname{Co}_1$**: Sporadic simple quotient $\operatorname{Co}_0 / \{\pm I\}$ of order $\approx 4.158 \times 10^{18}$.
- **$\Delta_{24}$**: Optimal sphere packing density in $\mathbb{R}^{24}$: $\Delta_{24} = \pi^{12} / 12!$ (CKMRV, 2017).
""",
    "docs/thesis/The_Sacred_Sanctum-Foundations_of_Sovereign_Intelligence_v03.md": """

---

# Appendix A: Comprehensive Mathematical & Categorical Index (Volume III)

### Index of Categorical & Chromatic Homotopy Symbols
- **$\mathcal{Sp}$**: The stable homotopy category of spectra.
- **$\mathbb{S}$**: The sphere spectrum; initial object in the symmetric monoidal category of spectra.
- **$\pi_*(\mathbb{S})$**: Stable homotopy groups of spheres.
- **$\mathbb{A}^1$-Homotopy**: Voevodsky-Morel homotopy theory where the algebraic affine line $\mathbb{A}^1$ is contractible.
- **$\operatorname{Sm}_k$**: Category of smooth schemes of finite type over base field $k$.
- **$\operatorname{Nis}$**: The Nisnevich Grothendieck topology with elementary distinguished squares.
- **$\operatorname{Cor}(k)$**: Category of finite algebraic correspondences.
- **$\mathbf{DM}(k)$**: Voevodsky's triangulated category of mixed motives over $k$.
- **$\mathcal{H}^{p,q}(X)$**: Bi-graded motivic cohomology group of weights $(p, q) \cong \operatorname{CH}^q(X, 2q-p)$.
- **$MGL$**: The algebraic cobordism motivic spectrum.
- **$MU_*$**: Complex cobordism ring $\cong \mathbb{Z}[x_1, x_2, \dots]$ isomorphic to Lazard's universal formal group law ring $L$.
- **$BP$**: Brown-Peterson spectrum at prime $p$ with coefficient ring $\mathbb{Z}_{(p)}[v_1, v_2, \dots]$.
- **$K(n)$**: Morava $K$-theory of chromatic height $n$ with coefficients $\mathbb{F}_p[v_n, v_n^{-1}]$.
- **$E_n$**: Lubin-Tate deformation spectrum associated to formal group of height $n$.
- **$\mathbb{S}_n$**: Morava stabilizer group $\operatorname{Aut}(H_n) \rtimes \operatorname{Gal}(\mathbb{F}_{p^n}/\mathbb{F}_p)$.
- **$\operatorname{ANSS}$**: Adams-Novikov Spectral Sequence based on complex cobordism / $BP$.
- **$\alpha, \beta, \gamma$**: Greek letter periodic families in the stable homotopy groups of spheres.
- **$L_n X$**: Bousfield localization with respect to Johnson-Wilson spectrum $E(n)$.
- **$M_n X$**: Monochromatic layer at chromatic height $n$ satisfying chromatic fracture squares.
- **Hopkins-Ravenel Convergence**: Equivalence $\mathbb{S}_{(p)} \simeq \operatorname{holim}_n L_n \mathbb{S}_{(p)}$ reconstructing the sphere spectrum from chromatic towers.
"""
}

for path, index_text in VOL_INDICES.items():
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if "Appendix A: Comprehensive Mathematical" not in content:
            # Insert before final backcover div
            parts = content.rsplit('<div class="cover-page back-cover">', 1)
            if len(parts) == 2:
                new_content = parts[0] + index_text + '\n\n<div class="cover-page back-cover">' + parts[1]
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"[+] Appended comprehensive mathematical index to {path}")

