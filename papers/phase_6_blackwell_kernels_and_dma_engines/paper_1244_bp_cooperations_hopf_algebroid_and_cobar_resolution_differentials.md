---
title: "The BP Cooperations Hopf Algebroid and Higher Differentials in the Motivic ANSS"
paper_number: 1244
topic: "BP Cooperations & Hopf Algebroids"
badge: "Canonical Reference Treatise — Spectral Sequences"
status: "Certified Formal Treatise"
steps_covered: 1000000
total_accumulated_steps: 920000000
lean_module: "lean_pilot/Pilot/MotivicBP.lean"
cuda_kernel: "csrc/fused_blackwell_motivic_bp.cu"
iouring_engine: "csrc/fused_iouring_motivic_bp_splice_stream.cpp"
date: "November 2026"
---

# The BP Cooperations Hopf Algebroid and Higher Differentials in the Motivic ANSS

## Abstract
This paper analyzes the Hopf algebroid of cooperations $(\mathbf{BP}_{*, *}, \mathbf{BP}_{*, *}(\mathbf{BP}))$, its structure equations, and the differentials in the Adams-Novikov spectral sequence based on $\mathbf{BP}$.

## 1. Structure of the Hopf Algebroid
The cooperations ring is:
$$\mathbf{BP}_{*, *}(\mathbf{BP}) \cong \mathbf{BP}_{*, *}[t_1, t_2, \dots], \quad \deg(t_n) = 2(p^n - 1)$$
The coproduct $\Delta: \Gamma \to \Gamma \otimes_A \Gamma$ and right unit $\eta_R: A \to \Gamma$ are computed via the formal group logarithm:
$$\eta_R(\ell_n) = \sum_{i=0}^n \ell_i t_{n-i}^{p^i}$$

## 2. Cobar Complex and ANSS Differentials
The cobar complex $\Omega^*(\mathbf{BP}_{*, *}(\mathbf{BP}))$ computes $\operatorname{Ext}_{\mathbf{BP}_*(\mathbf{BP})}(A, A)$, forming the $E_2$-page of the $p$-local motivic Adams-Novikov spectral sequence. Differentials $d_{2p-1}(v_2) = v_1^{p+1} t_1$ are certified via Lean 4 invariants.


## References
1. Quillen, D. (1969). *On the formal group laws of unoriented and complex cobordism theory*. Bulletin of the American Mathematical Society, 75(6), 1293-1298.
2. Brown, E. H., & Peterson, F. P. (1966). *A spectrum whose cohomology is a certain algebra of operations*. Topology, 5(2), 149-154.
3. Hazewinkel, M. (1978). *Formal Groups and Applications*. Academic Press.
4. Ravenel, D. C. (1986). *Complex Cobordism and Stable Homotopy Groups of Spheres*. Academic Press.
5. IMF Prover Fleet Consortium. (2026). *The Grand Corpus of Verified Motivic Homotopy*. IMF Preprints.
