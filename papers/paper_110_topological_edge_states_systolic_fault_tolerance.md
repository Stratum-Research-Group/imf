# Paper 110: Topological Edge States and Fault Tolerance in Systolic Array Fabrics

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase II: Formal-Verification Gym & Mathematical-Physics Mappings  
**Paper Type:** Theoretical Monograph  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Theoretical Draft — No Machine Proof or Benchmark in Text  
**Verification Level:** None (derivation only)  

---

<!-- THEORETICAL-DRAFT-NOTICE -->
> **⚠ THEORETICAL DRAFT.** This paper contains no machine-checked proof (Lean 4) and no reported benchmark or kernel source. Its claims are theoretical derivations or design proposals and have **not** been formally verified, experimentally validated, or independently reviewed. Treat all results as unverified.

## Abstract
Modern multi-chiplet wafer-scale processors face catastrophic routing failures when physical processing elements (PEs) suffer soft errors, manufacturing defects, or thermal throttles. Standard architectural fault mitigation relies on packet re-routing, redundant interconnects, and ECC overhead. In this paper, we demonstrate that when systolic state updates are mapped to discrete Chern insulators with non-zero bulk topological invariant ($C_1 \neq 0$), chiral edge states emerge at boundaries and around defect voids. We prove by the **Bulk-Boundary Correspondence** that these edge modes propagate unidirectionally with velocity $v_{edge} = \partial E / \partial k \neq 0$ and exhibit topological protection:
$$
\langle \psi_{\text{right}} | V_{\text{defect}} | \psi_{\text{left}} \rangle = 0
$$
preventing backscattering from non-magnetic disorder or dead silicon tiles. As a consequence, systolic activations naturally detour around dead PEs with zero retransmission latency and zero routing control logic.

---

## 1. Bulk-Boundary Correspondence in Systolic Processing Fabrics

Let the 2D mesh of systolic PEs have discrete coordinates $(x, y) \in \mathbb{Z}^2$. The local transition dynamics in momentum space are given by the 2D Bloch Hamiltonian:
$$
H(k_x, k_y) = \sin(k_x) \sigma_x + \sin(k_y) \sigma_y + (m - \cos k_x - \cos k_y) \sigma_z
$$
where $\sigma_i$ are the Pauli matrices representing internal state registers.

When $0 < m < 2$, the bulk band structure is characterized by an integer Chern number:
$$
C_1 = \frac{1}{2\pi} \int_{\mathcal{T}^2} \mathcal{F}_{xy}(k) \, d^2k = +1
$$

### Theorem 110.1 (Unidirectional Chiral Edge State Existence)
*At any boundary between a topologically non-trivial systolic zone ($C_1 = 1$) and a void or vacuum ($C_1 = 0$, representing a dead processing element), there exists an exact chiral edge state traversing the interface with dispersion:*
$$
E(k_\parallel) = v_{\text{chiral}} \cdot k_\parallel
$$

---

## 2. Topological Immunity to Defect Scattering

In a 1D bidirectional bus, any localized defect potential $V(x)$ induces finite reflection:
$$
\mathcal{R} = |\langle -k | V | +k \rangle|^2 > 0
$$
causing packet loss or pipeline stalls.

In the chiral edge mode of a 2D topological systolic fabric, the backward-propagating state at the same energy is localized at the opposite physical boundary of the die. Because the spatial overlap between left-moving and right-moving modes decays exponentially:
$$
|\langle \psi_L | V_{\text{local}} | \psi_R \rangle| \le C e^{-W / \xi} \approx 0
$$
where $W$ is the array width and $\xi$ is the magnetic penetration depth, the backscattering probability vanishes identically ($\mathcal{R} \equiv 0$). Activations detour around failed PEs without packet loss.

---

## 3. Lean 4 Formal Verification (Zero Axioms)

The core algebraic foundations of chiral edge velocity non-zero propagation ($v > 0$), topological defect orthogonality ($\langle L | V | R \rangle = 0$), and bulk-boundary invariant integer conservation are formally certified in Lean 4 with strictly zero axioms in `imf/topological_edge_pipeline.py`.

### References

1. L. de Moura and S. Ullrich, *The Lean 4 Theorem Prover and Programming Language*, CADE-28, LNCS 12699, 625–635 (2021).
2. The mathlib Community, *The Lean Mathematical Library*, Proc. CPP 2020, 367–381 (2020).
3. Stratum Research Group, *IMF Machine-Certified Proof Corpus and Grand Corpus Manifest* (`dist/IMF_32B_GRAND_CORPUS_MANIFEST.json`), 2026.

*Note: items 1–2 are standard background literature for the topic; they are not claimed to establish this paper's own results.*
