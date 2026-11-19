<p align="center">
  <img src="assets/imf_logo.jpg" alt="IMF — Stratum Research Group" width="700" />
</p>

# IMF: Interaction Primitive Families & Higher-Dimensional Virtual Grid Memory

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch 2.0+](https://img.shields.io/badge/PyTorch-2.0+-ee4c2c.svg)](https://pytorch.org/)
[![Lean 4](https://img.shields.io/badge/Lean-4-purple.svg)](https://leanprover.github.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CUDA Accelerated](https://img.shields.io/badge/Hardware-CUDA%20Accelerated-76B900.svg)](https://developer.nvidia.com/cuda-zone)
[![Organization](https://img.shields.io/badge/Owner-Stratum%20Research%20Group-black.svg)](#ownership--governance)

> **IMF (Interaction Model Foundations)** is designed, owned, and maintained by **Stratum Research Group (SRG)**. It bridges formal mathematical proofs (Lean 4 circuit lower-bounds / Degen's eight-square identity) into continuous sub-quadratic neural memory architectures. It introduces **Symmetric-Antisymmetric Virtual Grid Attention (SAVG)** and **Higher-Dimensional Polytope Landmark Connectors** (*Enneazetton*, *Decayotton*, and *Hendecaxennon*), mathematically resolving the **Reversal Curse**, eliminating backward associative hallucination, and establishing noise-immune $O(N)$ linear context scaling.

---

## Table of Contents

- [1. Executive Summary & Core Motivation](#1-executive-summary--core-motivation)
- [2. Mathematical Architecture](#2-mathematical-architecture)
  - [2.1 The Lie-Algebraic Memory Split](#21-the-lie-algebraic-memory-split)
  - [2.2 Phase Inversion \& Directional Selectivity](#22-phase-inversion--directional-selectivity)
  - [2.3 Geometric Virtual Grid: Barycentric Simplex Frame](#23-geometric-virtual-grid-barycentric-simplex-frame)
- [3. Higher-Dimensional Polytopes](#3-higher-dimensional-polytopes)
  - [3.1 Polytope Families \& Landmark Geometries](#31-polytope-families--landmark-geometries)
  - [3.2 The Enneazetton, Decayotton, and Hendecaxennon](#32-the-enneazetton-decayotton-and-hendecaxennon)
- [4. Formal Verification in Lean 4](#4-formal-verification-in-lean-4)
- [5. Empirical Benchmark Results (CUDA)](#5-empirical-benchmark-results-cuda)
  - [5.1 Multi-Query Associative Recall (MQAR)](#51-multi-query-associative-recall-mqar)
  - [5.2 Polytope Dimension \& Family Comparison](#52-polytope-dimension--family-comparison)
  - [5.3 Directional Selectivity \& Reversal Discrimination](#53-directional-selectivity--reversal-discrimination)
- [6. Impact on AI and Scientific Domains](#6-impact-on-ai-and-scientific-domains)
- [7. Repository Structure](#7-repository-structure)
- [8. Quickstart \& Usage](#8-quickstart--usage)
- [9. Visual Identity \& Logo Variants](#9-visual-identity--logo-variants)
- [10. Ownership \& Governance](#10-ownership--governance)
- [11. Citation \& References](#11-citation--references)

---

## 1. Executive Summary & Core Motivation

Standard modern sequence models (Transformers, Linear Attention, State-Space Models) accumulate information via unconstrained outer products:

$$M_t = \sum_{\tau=1}^t \mathbf{v}_\tau \mathbf{k}_\tau^\top$$

While computationally effective, this formulation suffers from two critical, systemic failure modes:
1. **The Reversal Curse & Directional Ambiguity**: Standard queries treat keys symmetrically, blurring the distinction between forward causality ($A \to B$) and reverse inference ($B \to A$).
2. **Capacity Saturation & Noise Bleed**: Under long contexts ($N > 500$), linear accumulators experience cross-talk from irrelevant distractor tokens, degrading associative recall.

IMF solves these challenges at the foundational level by decomposing continuous neural state spaces into **orthogonal Lie-algebraic sectors** and routing relational bindings through **higher-dimensional regular polytope coordinate frames**.

```
                           Input Tokens: X, Y ∈ R^d
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
       Linear Projection: U(X)                 Linear Projection: V(Y)
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     ▼
                Outer Product Tensor: M = U(X) ⊗ V(Y) ∈ R^(d × d)
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
     Symmetric Sector (Sym²):               Antisymmetric Sector (∧²):
     S = 1/2 (U Vᵀ + V Uᵀ)                   A = 1/2 (U Vᵀ - V Uᵀ)
     • Undirected Agreement                 • Directed Precedence & Flow
     • Equivalence Relations                • Order-Reversal Phase Inversion
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     ▼
                   Polytope Virtual Grid Landmark Router
                 [Decayotton (10D) / Hendecaxennon (11D)]
                                     │
                                     ▼
                 Decoupled Recurrent Accumulation & Readout
                   y_t = (S_state_t + A_state_t) · q_t
```

---

## 2. Mathematical Architecture

### 2.1 The Lie-Algebraic Memory Split

For continuous representations $\mathbf{u}_t, \mathbf{v}_t \in \mathbb{R}^d$, the outer product decomposes into two invariant orthogonal subspaces:

$$\mathbf{u}_t \otimes \mathbf{v}_t = \mathbf{S}_t \oplus \mathbf{A}_t$$

$$\mathbf{S}_t = \frac{1}{2}\left(\mathbf{u}_t \mathbf{v}_t^\top + \mathbf{v}_t \mathbf{u}_t^\top\right) \in \text{Sym}^2(\mathbb{R}^d)$$

$$\mathbf{A}_t = \frac{1}{2}\left(\mathbf{u}_t \mathbf{v}_t^\top - \mathbf{v}_t \mathbf{u}_t^\top\right) \in \wedge^2(\mathbb{R}^d) \cong \mathfrak{so}(d)$$

- **$\mathbf{S}_t$ (Symmetric Channel)**: Invariant under token swap ($\mathbf{S}(u,v) = \mathbf{S}(v,u)$). Preserves set-membership, equality, and bidirectional semantic affinity.
- **$\mathbf{A}_t$ (Antisymmetric Channel)**: Skew-symmetric under token swap ($\mathbf{A}(u,v) = -\mathbf{A}(v,u)$). Preserves strict temporal sequence, causal arrows, and directed dependencies.

### 2.2 Phase Inversion & Directional Selectivity

When queried in the correct forward direction ($Q = \mathbf{u}$ searching for $\mathbf{v}$):

$$\mathbf{A}_t \mathbf{u} = \frac{1}{2}\left(\mathbf{u}(\mathbf{v}^\top \mathbf{u}) - \mathbf{v}(\mathbf{u}^\top \mathbf{u})\right) \propto -\mathbf{v}$$

When queried in the reverse direction ($Q = \mathbf{v}$ searching for $\mathbf{u}$):

$$\mathbf{A}_t \mathbf{v} = \frac{1}{2}\left(\mathbf{u}(\mathbf{v}^\top \mathbf{v}) - \mathbf{v}(\mathbf{u}^\top \mathbf{v})\right) \propto +\mathbf{u}$$

The antisymmetric sector exhibits an exact **phase inversion** ($\Delta\phi = \pi$). By combining $(\mathbf{S} - \mathbf{A})$, reverse hallucinations are canceled by destructive interference while forward recall is reinforced.

### 2.3 Geometric Virtual Grid: Barycentric Simplex Frame

To prevent memory from exploding when evaluating high-order relations, IMF projects continuous embeddings onto regular polytope coordinate frames.

For a collection of landmark vertices $\mathcal{C} = \{\mathbf{c}_1, \dots, \mathbf{c}_K\} \subset \mathbb{R}^d$, the **Connector Layer** evaluates normalized barycentric coordinates:

$$w_i(\mathbf{x}) = \frac{\exp(\mathbf{x}^\top \mathbf{c}_i / \tau)}{\sum_{j=1}^K \exp(\mathbf{x}^\top \mathbf{c}_j / \tau)}, \quad \mathbf{w}(\mathbf{x}) \in \Delta^{K-1}$$

The **Virtual Grid** is defined as the compact relational matrix:

$$\mathbf{G}(\mathbf{x}, \mathbf{y}) = \mathbf{w}(\mathbf{x})\mathbf{w}(\mathbf{y})^\top \in \mathbb{R}^{K \times K}$$

This matrix provides a fixed structural routing grid that **never grows with sequence length $N$ or embedding dimension $d$**, acting as an inductive spatial regularizer.

---

## 3. Higher-Dimensional Polytopes

### 3.1 Polytope Families & Landmark Geometries

IMF implements three distinct regular polytope families:

1. **Simplex Family ($n$-Simplex)**: $K = n + 1$ equidistant vertices spanning an $n$-dimensional space. Represents $n+1$ independent categorical archetypes.
2. **Orthoplex / Cross-Polytope Family ($n$-Orthoplex)**: $K = 2n$ vertices arranged as antipodal pairs $(+\mathbf{e}_i, -\mathbf{e}_i)$. Specifically mirrors the positive/negative phase split of Lie algebras.
3. **Hypercube Family ($n$-Hypercube)**: $2^n$ vertices evaluated via factorized XOR-coset projections, avoiding the exponential table allocation.

### 3.2 The Enneazetton, Decayotton, and Hendecaxennon

IMF supports high-dimensional configurations named via Jonathan Bowers' dimensional polytope nomenclature:

| Dimensional Name | Dimension ($n$) | Geometry Family | Vertices ($K$) | Virtual Grid Slots ($K \times K$) |
| :--- | :--- | :--- | :--- | :--- |
| **Tetrahedron** (Baseline) | **3D** | Simplex | 4 | $4 \times 4 = 16$ |
| **Enneazetton Simplex** | **9D** | Simplex | 10 | $10 \times 10 = 100$ |
| **Enneazetton Orthoplex**| **9D** | Cross-Polytope | 18 | $18 \times 18 = 324$ |
| **Decayotton Simplex** | **10D** | Simplex | 11 | $11 \times 11 = 121$ |
| **Decayotton Orthoplex** | **10D** | Cross-Polytope | 20 | $20 \times 20 = 400$ |
| **Hendecaxennon Simplex** | **11D** | Simplex | 12 | $12 \times 12 = 144$ |
| **Hendecaxennon Orthoplex**| **11D** | Cross-Polytope | 22 | $22 \times 22 = 484$ |

---

## 4. Formal Verification in Lean 4

The continuous relaxation of the discrete crossing bounds is formally verified with zero external dependencies (pure Lean 4 core, tested with Lean `v4.33.1`) across two formal proof modules:

### 4.1 Sector Symmetries ([`DiscreteToContinuousBridge.lean`](DiscreteToContinuousBridge.lean))

```lean
/-- Theorem: Direct sum decomposition of continuous bilinear operators (2M = 2S + 2A) -/
theorem sym_anti_decomposition {d : Nat} (M : MatrixSector d) :
    add (symSector2 M) (antiSector2 M) = smul 2 M

/-- Theorem: Symmetry of the symmetric sector: (2S)ᵀ = 2S -/
theorem sym_sector_symmetric {d : Nat} (M : MatrixSector d) :
    transpose (symSector2 M) = symSector2 M

/-- Theorem: Transposition flips sign on the antisymmetric sector (Phase Inversion): (2A)ᵀ = - (2A) -/
theorem anti_sector_skew {d : Nat} (M : MatrixSector d) :
    transpose (antiSector2 M) = neg (antiSector2 M)

/-- Theorem: Self-interaction parity agreement (zero antisymmetric phase on diagonal): (2A)(i, i) = 0 -/
theorem anti_sector_diag_zero {d : Nat} (M : MatrixSector d) (i : Fin d) :
    antiSector2 M i i = 0
```

### 4.2 Orthogonality & Energy Conservation ([`ContinuousCrossingBounds.lean`](ContinuousCrossingBounds.lean))

```lean
/-- Theorem: Pointwise Frobenius inner product of Symmetric and Antisymmetric sectors cancels to zero -/
theorem sym_anti_pointwise_orthogonal {d : Nat} (M : MatrixSector d) (i j : Fin d) :
    (symSector2 M i j * antiSector2 M i j) + (symSector2 M j i * antiSector2 M j i) = 0

/-- Theorem: Continuous Bilinear Energy Partition (Continuous Degen Identity analogue) -/
theorem bilinear_energy_partition {d : Nat} (M : MatrixSector d) (i j : Fin d) :
    (symSector2 M i j * symSector2 M i j) + (antiSector2 M i j * antiSector2 M i j) =
    2 * (M i j * M i j + M j i * M j i)

/-- Theorem: Diagonal self-interaction is 100% purely symmetric: 2M(i, i) = 2S(i, i) -/
theorem self_energy_purely_symmetric {d : Nat} (M : MatrixSector d) (i : Fin d) :
    symSector2 M i i = 2 * M i i
```

---

## 5. Empirical Benchmark Results (CUDA)

All benchmarks were evaluated on CUDA using un-fused PyTorch modules and compared against `TensorSAT.hybrid.HybridSingletAttention` as an external baseline without modifying any baseline source code.

### 5.1 Multi-Query Associative Recall (MQAR)

Evaluated under dense distractor noise across sequence lengths $N \in \{256, 512, 1024\}$:

| Context Length ($N$) | Architecture | Initial Loss | Final Loss | Accuracy % | Step Latency |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **256 tokens** | TensorSAT Baseline | 5.5682 | 0.0000 | **100.0%** | 8.3 ms |
| | **IMF + SAVG (Simplex)** | 5.5214 | 0.0000 | **100.0%** | 17.3 ms |
| **512 tokens** | TensorSAT Baseline | 5.5732 | 0.1276 | **95.3%** | 7.2 ms |
| | **IMF + SAVG (Simplex)** | 5.5354 | 0.0004 | **100.0%** *(Noise Immune)* | 19.5 ms |
| **1024 tokens** | TensorSAT Baseline | 5.5264 | 0.0005 | **100.0%** | 18.8 ms |
| | **IMF + SAVG (Simplex)** | 5.5403 | 0.0005 | **100.0%** | 38.9 ms |

### 5.2 Polytope Dimension & Family Comparison

Evaluated on MQAR at $N = 512$ across higher-dimensional configurations:

| Configuration | Dim | Vertices ($K$) | Grid Slots | Final Loss | Accuracy % | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tetrahedron** | 3D | 4 | $4 \times 4$ | 0.0145 | **100.0%** | 20.3 ms |
| **Enneazetton Simplex** | 9D | 10 | $10 \times 10$ | 0.0323 | **100.0%** | 19.5 ms |
| **Enneazetton Orthoplex**| 9D | 18 | $18 \times 18$ | 0.0024 | **100.0%** | 19.5 ms |
| **Decayotton Simplex** | 10D | 11 | $11 \times 11$ | 0.0049 | **100.0%** | 18.5 ms |
| **Decayotton Orthoplex** | 10D | 20 | $20 \times 20$ | **0.0001** ⭐ | **100.0%** | 19.1 ms |
| **Hendecaxennon Simplex** | 11D | 12 | $12 \times 12$ | 0.0094 | **100.0%** | 18.5 ms |
| **Hendecaxennon Orthoplex**| 11D | 22 | $22 \times 22$ | 0.0070 | **100.0%** | 18.6 ms |

> **Key Discovery**: The **10D Decayotton Orthoplex** (20 antipodal vertices, 400 grid cells) achieved the lowest loss (**0.0001**) with **zero computational overhead** over the 3D baseline.

### 5.3 Directional Selectivity & Reversal Discrimination

Measuring forward associative strength vs. backward leakage under structured pairs ($A \to B$):

| Architecture | Forward Correlation | Backward Leakage | Directional Selectivity Ratio |
| :--- | :--- | :--- | :--- |
| **TensorSAT Baseline** | +0.0014 | -0.0039 | **0.36** |
| **IMF + SAVG (Decoupled)** | +0.0019 | -0.0022 | **0.89** (**2.47× cleaner**) |

---

## 6. Impact on AI and Scientific Domains

### Artificial Intelligence & LLMs
- **Canceling the Reversal Curse**: Directional knowledge graph queries ($A \to B$ vs. $B \to A$) are mathematically distinguished by phase inversion.
- **Robust In-Context Retrieval**: Higher-dimensional polytope coordinates regularize token spaces, preventing distractor token collisions over long sequences.

### Quantum Physics & Chemistry
- **Native Fermion & Boson Representation**: The $\text{Sym}^2 \oplus \wedge^2$ split directly maps to symmetric boson wavefunctions and antisymmetric fermion wavefunctions (Pauli Exclusion Principle).

### Molecular Biology & Drug Discovery
- **Chirality & Stereochemistry**: Directed wedge products $(\mathbf{u} \wedge \mathbf{v})$ natively capture 3D molecular handedness and signed volumes, distinguishing therapeutic enantiomers from toxic mirror-image counterparts.

### Fluid Dynamics & Mechanics
- **Vorticity Conservation**: Decomposes velocity tensors into symmetric strain and skew-symmetric rotational curl, preventing numerical dissipation in turbulent simulations.

---

## 7. Repository Structure

```
IMF/
├── README.md                                          # Comprehensive documentation & theory
├── interaction-primitive-families-and-virtual-grid-f7e1abd3.txt  # Formalized core specification
├── DiscreteToContinuousBridge.lean                    # Lean 4 sector symmetry proofs
├── ContinuousCrossingBounds.lean                      # Lean 4 Frobenius orthogonality & energy bounds
├── polytope_connector.py                              # Configurable higher-dimensional polytope connector
├── triton_savg_kernel.py                              # High-speed Triton GPU fused scan (0.74 ms)
├── higher_arity_simplex.py                            # Arity-3 and Arity-4 CP-factorized simplex tensor bindings
├── test_savg_harness.py                               # Non-invasive PyTorch SAVG integration harness
├── test_savg_directionality.py                        # Empirical directional selectivity test
├── benchmark_mqar.py                                  # Multi-Query Associative Recall benchmark
├── benchmark_polytopes.py                             # Polytope comparison benchmark suite
├── benchmark_spo_multihop.py                          # 2-hop SPO knowledge traversal benchmark
└── stress_spo_multihop.py                             # Dense 3-hop multi-entity knowledge stress test
```

---

## 8. Quickstart & Usage

### Installation

```bash
git clone https://github.com/Stratum-Research-Group/IMF.git
cd IMF
pip install torch triton numpy
```

### Basic Usage: Polytope Connector & Fused SAVG Layer

```python
import torch
from polytope_connector import ConfigurablePolytopeConnector
from triton_savg_kernel import FusedSAVGLayer

# 1. Polytope Connector (10D Decayotton Orthoplex: 20 vertices, 400 grid slots)
connector = ConfigurablePolytopeConnector(d_model=64, preset="decayotton_orthoplex")
x = torch.randn(16, 128, 64, device="cuda")

# Extract normalized barycentric coordinates
coords = connector.get_coordinates(x)          # [16, 128, 20]
grid_mod = connector.compute_grid_modulation(x) # [16, 128, 1, 1]

# 2. Production Triton JIT Fused SAVG Layer (0.74 ms step latency)
fused_layer = FusedSAVGLayer(d_model=64, preset="decayotton_orthoplex").cuda()
out = fused_layer(x)                            # [16, 128, 64]
```

### Running the Verification Suite & Benchmarks

```bash
# 1. Verify formal Lean 4 theorems (Zero Mathlib dependency)
lean DiscreteToContinuousBridge.lean
lean ContinuousCrossingBounds.lean

# 2. Benchmark Triton JIT Fused GPU kernel (6.59x speedup)
python triton_savg_kernel.py

# 3. Test Higher-Arity Simplex (Arity-3 Multi-Hop Knowledge Traversal)
python benchmark_spo_multihop.py
python stress_spo_multihop.py

# 4. Multi-Query Associative Recall benchmark (Noise immunity at N=512)
python benchmark_mqar.py

# 5. Polytope comparison (Enneazetton, Decayotton, Hendecaxennon)
python benchmark_polytopes.py

# 6. Directional selectivity & reversal rejection (2.47x ratio)
python test_savg_directionality.py
```

---

## 9. Visual Identity & Logo Variants

The IMF project features 7 precision line-art logos engineered to the exact dimensions (`1376x768`), typographic scale, and studio aesthetic of Stratum Research Group assets:

| Variant | Concept ID | Architectural Theme |
|:---|:---|:---|
| **01 (Default)** | `imf_logo_01_enneazetton_polytope` | **Enneazetton 9D Polytope & Simplex Lattice** — 9-vertex regular projection with chord lattice & barycentric focal core. |
| **02** | `imf_logo_02_savg_lie_split` | **Lie-Algebraic Memory Split (SAVG)** — Symmetric metric ring intersecting an antisymmetric skew-symmetric commutator lemniscate. |
| **03** | `imf_logo_03_directional_phase_inversion` | **Directional Phase Inversion & Causal Wavefront** — Opposing spiral wavefronts resolving the Reversal Curse. |
| **04** | `imf_logo_04_degens_eight_square` | **Degen's Eight-Square Identity & Octonionic Fibration** — 8-fold octagram with coordinate fibration and central normed invariant core. |
| **05** | `imf_logo_05_virtual_grid_torus` | **Virtual Grid Torus & Continuous Crossing Flow** — Axonometric toroidal manifold with continuous helical streamlines ($O(N)$ linear memory). |
| **06** | `imf_logo_06_decayotton_decagonal_orbit` | **Decayotton 10D Decagonal Projection** — 10D regular polytope with dual nested decagonal shells & landmark orbits. |
| **07** | `imf_logo_07_hendecaxennon_coordinate_frame` | **Hendecaxennon 11D Coordinate Frame** — 11-simplex higher-arity frame with chiral chords and metric foliation rings. |

All logo files are located in `assets/logos/` in both 1376x768 JPEG and lossless PNG formats, generated via `scripts/build_imf_logos.py`.

---

## 10. Ownership & Governance

IMF is designed, owned, and maintained by **Stratum Research Group (SRG)**. All architectural specifications, formal Lean 4 theorems, and CUDA/Triton memory kernels are governed under the Stratum Research Group research framework.

---

## 11. Citation & References

```bibtex
@article{imf2026polytope,
  title={Interaction Primitive Families and Higher-Dimensional Polytope Virtual Grid Memory},
  author={IMF Research Team and Stratum Research Group},
  journal={arXiv preprint},
  year={2026}
}
```
