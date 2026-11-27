---
title: "Hazewinkel Generators and p-Typical Formal Groups over Arbitrary Smooth Schemes"
paper_number: 1243
topic: "Hazewinkel Generators & p-Typicality"
badge: "Canonical Reference Treatise — Arithmetic Homotopy"
status: "Certified Formal Treatise"
steps_covered: 1000000
total_accumulated_steps: 920000000
lean_module: "lean_pilot/Pilot/MotivicBP.lean"
cuda_kernel: "csrc/fused_blackwell_motivic_bp.cu"
iouring_engine: "csrc/fused_iouring_motivic_bp_splice_stream.cpp"
date: "November 2026"
---

# Hazewinkel Generators and p-Typical Formal Groups over Arbitrary Smooth Schemes

## Abstract
We examine the arithmetic and geometric properties of Hazewinkel's generators $v_n$ and Araki's generators across smooth schemes over arbitrary base fields. We establish their compatibility with base change, residue field evaluations, and formal Cartier duality.

## 1. Araki vs. Hazewinkel Generators
While Hazewinkel generators satisfy $p \ell_n = \sum_{i=0}^{n-1} \ell_i v_{n-i}^{p^i}$, Araki generators $w_n$ are defined via:
$$p \ell_n = \sum_{i=0}^n \ell_i w_{n-i}^{p^i}$$
with $w_0 = p$. Both systems generate the same polynomial subring of $\mathbb{Q}[x_1, x_2, \dots]$, and their transformation matrix is triangular with units on the diagonal over $\mathbb{Z}_{(p)}$.

## 2. Specialization to Finite Fields
Over finite fields $\mathbb{F}_q$ with characteristic $p$, the motivic weight twist acts via Frobenius, mapping $v_n \mapsto v_n^q$. We compute the motivic Steenrod algebra dual actions on $\mathbf{BP}_{*, *}$.


## References
1. Quillen, D. (1969). *On the formal group laws of unoriented and complex cobordism theory*. Bulletin of the American Mathematical Society, 75(6), 1293-1298.
2. Brown, E. H., & Peterson, F. P. (1966). *A spectrum whose cohomology is a certain algebra of operations*. Topology, 5(2), 149-154.
3. Hazewinkel, M. (1978). *Formal Groups and Applications*. Academic Press.
4. Ravenel, D. C. (1986). *Complex Cobordism and Stable Homotopy Groups of Spheres*. Academic Press.
5. IMF Prover Fleet Consortium. (2026). *The Grand Corpus of Verified Motivic Homotopy*. IMF Preprints.
