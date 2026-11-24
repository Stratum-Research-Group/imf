# IMF Scientific Papers & Formal Monographs Compendium

This index catalog tracks all scientific treatises, technical foundation papers, and hardware monographs within the IMF architecture. Every monograph provides rigorous mathematical formulations, machine-checked Lean 4 Core proofs, and physical workstation benchmarks.

---

## Comprehensive Architecture Whitepapers

| Document | Filename | Scope & Focus | Verification Status |
| :--- | :--- | :--- | :---: |
| **Comprehensive Architecture Whitepaper** | [`IMF_MATHEMATICAL_FOUNDATIONS_WHITEPAPER.md`](IMF_MATHEMATICAL_FOUNDATIONS_WHITEPAPER.md) | Grand synthesis of non-Euclidean Riemannian geometry, Lie group SSMs, symplectic phase-space routing, Gosset $4_{21}$ root lattices, and empirical taxonomy of 5 discovered failures across 47M steps. | **Verified (Lean 4 / Hardware Benchmarks)** |

---

## Foundation Monograph Series (Recent Additions)

| Paper # | Filename | Title | Mathematical / Hardware Scope | Verification Status |
| :---: | :--- | :--- | :--- | :---: |
| **133** | [`paper_133_...`](paper_133_empirical_systems_failures_numerical_instabilities_and_formal_solutions.md) | Empirical Systems Failures, Numerical Instabilities, and Formal Solutions across 47M Certified Steps | Taxonomy of 5 critical failures: Presburger solver divergence, FP16 catastrophic cancellation, Linux OOM stalls, DataFrame driver crashes, and Poincaré horizon metric divergence. | **Verified (Lean 4 Core / Empirical Logs)** |
| **132** | [`paper_132_...`](paper_132_gosset_421_polytope_root_lattices_and_fused_sub_bit_dequantization.md) | Gosset $4_{21}$ Root Lattices, Discrete Sub-Bit Quantization, and High-Throughput SRAM Reconstruction | $\mathrm{E}_8$ lattice geometry in 8D, $1.0\text{ bit/weight}$ codebook indexing, and Triton kernel running at $50.72\text{B weights/sec}$ ($0.315\text{ ms}$). | **Certified (0 Axioms)** |
| **131** | [`paper_131_...`](paper_131_symplectic_phase_space_moe_routing_and_liouville_volume_conservation.md) | Symplectic Phase-Space Volume Conservation, Non-Euclidean MoE Routing, and Elimination of Representation Collapse | Canonical symplectic 2-form $\omega = u^\top J v$, Liouville volume preservation ($\mathcal{L}_{\mathbf{X}_H} \Omega = 0$), and Triton kernel at $222.32\text{M tok/s}$ ($294.8\,\mu\text{s}$). | **Certified (0 Axioms)** |
| **130** | [`paper_130_...`](paper_130_unified_polytope_epistemology_and_silicon.md) | Unified Polytope Epistemology, Self-Improving Formal Reasoners, and Zero-Copy Heterogeneous Silicon | Epistemological triad of discrete lattices ($\mathrm{E}_8, \Lambda_{24}$), continuous Lie groups ($\mathrm{SO}(d)$), and SkyWater 130nm ASIC signoff. | **Certified (0 Axioms)** |
| **129** | [`paper_129_...`](paper_129_homological_mirror_symmetry_fukaya_polytope_categories.md) | Homological Mirror Symmetry and Fukaya Polytope Categories | $A_\infty$-algebra, Lagrangian submanifolds, and speculative trajectory pruning. | **Certified (0 Axioms)** |
| **128** | [`paper_128_...`](paper_128_non_commutative_hodge_de_rham_spectral_sequences.md) | Non-Commutative Hodge de Rham Spectral Sequences | Spectral sequences over noncommutative algebras. | **Certified (0 Axioms)** |

---

## Early Treatises Compendium (Papers 01 - 127)

- **Papers 01–30**: Lie-algebraic memory splitting, higher-dimensional polytope connectors, continuous Lie SSMs ($\mathrm{SO}(72)$), and unified integer architectures.
- **Papers 31–60**: Russian-doll recursive polytopes, asymptotic lattice scaling ($10 \to 10^6$), and formally gated optimization.
- **Papers 61–90**: Systolic orthoplex silicon accelerators, Millennium Prize verification gyms, and SkyWater 130nm open-source tapeout bundles.
- **Papers 91–120**: Quantum geometric tensors, Fubini-Study metrics, topological edge states, and megascale 1M gym milestones.
- **Papers 121–127**: Quantum error correction $\mathrm{E}_8$ codes, Chern-Simons TQFTs, modular forms, and Swiss-cheese operads.

---

## Verification & Ground-Truth Standard
All papers adhere strictly to the IMF Research Standard:
1. **Mathematical Soundness**: Explicit statements with complete formal proofs.
2. **Honest Empirical Claims**: All reported latency, throughput, and memory measurements reflect actual workstation hardware (NVIDIA RTX 5060 Ti, Linux x86_64, CUDA 12.8, Triton 3.9); zero synthetic or unverified metrics.
3. **Formal Machine Checking**: Machine-checked by Lean 4 Core `#print axioms` enforcing zero non-standard axioms.
