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

> **IMF (Interaction Model Foundations)** is a research prototype by **Stratum Research Group (SRG)** exploring continuous sub-quadratic neural memory architectures with formal algebraic structure. It investigates **Symmetric-Antisymmetric Virtual Grid Attention (SAVG)** and **Higher-Dimensional Polytope Landmark Connectors (HDPLC)** (*Enneazetton*, *Decayotton*, and *Hendecaxennon*), designing anti-commutative operators to mitigate directional ambiguity and evaluating geometric regularizers in associative retrieval tasks.

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
- [6. Theoretical Parallels & Exploratory Hypotheses](#6-theoretical-parallels--exploratory-hypotheses)
- [7. Repository Structure](#7-repository-structure)
- [8. Quickstart \& Usage](#8-quickstart--usage)
- [9. Technical Reports & Publications](#9-technical-reports--publications)
- [10. Visual Identity \& Logo Variants](#10-visual-identity--logo-variants)
- [11. Ownership \& Governance](#11-ownership--governance)
- [12. Citation \& References](#12-citation--references)

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

### 4.1 Sector Symmetries ([`lean/DiscreteToContinuousBridge.lean`](lean/DiscreteToContinuousBridge.lean))

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

### 4.2 Orthogonality & Energy Conservation ([`lean/ContinuousCrossingBounds.lean`](lean/ContinuousCrossingBounds.lean))

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

All benchmark scripts are fully automated and evaluate both baseline and IMF-augmented architectures on CUDA (`NVIDIA GeForce RTX 5060 Ti`).

### 5.1 Multi-Query Associative Recall (MQAR)

Evaluated under dynamic sequence-specific key-value pairs with a shared, persistent vocabulary codebook across training and held-out evaluation batches (`benchmark_mqar.py`):

| Context Length ($N$) | Architecture | Train Loss (60 steps) | Held-Out Eval Acc % | Step Latency |
| :--- | :--- | :--- | :--- | :--- |
| **128 tokens** | TensorSAT Baseline | 0.6989 | **1.6%** | 20.8 ms |
| | **IMF + SAVG Channel** | **0.1364** | **1.6%** | **6.2 ms** |
| **256 tokens** | TensorSAT Baseline | 0.8993 | **1.6%** | 9.5 ms |
| | **IMF + SAVG Channel** | **0.0599** | **0.0%** | **9.0 ms** |

> *Note on Generalization*: The toy training regime (60 steps on a small batch) demonstrates rapid training-set loss minimization and fast step times. True out-of-distribution associative recall on held-out sequences requires larger-scale pretraining across diverse sequence distributions.

### 5.2 Polytope Dimension & Family Comparison

Evaluated on MQAR at $N = 512$ with a shared held-out evaluation batch across higher-dimensional configurations (`benchmark_polytopes.py`):

| Configuration | Dim | Vertices ($K$) | Grid Slots | Final Train Loss | Held-Out Eval Acc % | Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tetrahedron** | 3D | 4 | $4 \times 4$ | 0.0054 | 0.8% | 27.3 ms |
| **Enneazetton Simplex** | 9D | 10 | $10 \times 10$ | 0.0055 | 2.3% | 26.5 ms |
| **Enneazetton Orthoplex**| 9D | 18 | $18 \times 18$ | 0.0193 | 0.8% | 26.8 ms |
| **Decayotton Simplex** | 10D | 11 | $11 \times 11$ | 0.0187 | 1.6% | 25.2 ms |
| **Decayotton Orthoplex** | 10D | 20 | $20 \times 20$ | 0.0072 | 2.3% | 27.3 ms |
| **Hendecaxennon Simplex** | 11D | 12 | $12 \times 12$ | 0.0057 | 0.8% | 24.0 ms |
| **Hendecaxennon Orthoplex**| 11D | 22 | $22 \times 22$ | 0.0417 | 1.6% | 26.3 ms |

### 5.3 Directional Selectivity & Reversal Discrimination

Evaluating forward associative training ($A \to B$) and reverse probing ($B \to ?$) with the query placed after contextual facts (`test_savg_directionality.py`):

| Architecture | Forward Accuracy ($A \to B$) | Forward Cosine | Reverse Leakage ($B \to A$) | Reverse Cosine | Directional Separation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TensorSAT Baseline** | 100.0% | +0.7432 | 6.2% | +0.0238 | +0.7194 |
| **IMF + SAVG (Decoupled)** | 100.0% | +0.8238 | 18.8% | +0.1165 | +0.7074 |

---

## 6. Theoretical Parallels & Exploratory Hypotheses

*(Note: The following physical and biochemical connections represent conceptual structural parallels stemming from Lie-algebraic symmetry rather than empirically verified domain models. The codebase currently evaluates synthetic associative recall and relational query tasks.)*

### Artificial Intelligence & Sequence Modeling
- **Directional Selectivity**: Directional knowledge pairs ($A \to B$ vs. $B \to A$) can be structurally separated using the alternating property of the skew-symmetric operator $A = -A^\top$.
- **Structured Latent Anchors**: High-dimensional polytope vertices provide bounded barycentric coordinate frames that regularize token representations.

### Mathematical Parallels: Fermion/Boson Statistics & Stereochemistry
- **Wavefunction Symmetry Analogy**: The $\text{Sym}^2 \oplus \wedge^2$ decomposition mirrors the mathematical split between symmetric bosonic wavefunctions and antisymmetric fermionic wavefunctions (Pauli Exclusion Principle).
- **Chirality & Wedge Products**: Directed exterior products $(\mathbf{u} \wedge \mathbf{v})$ algebraically model signed areas and handedness in low dimensions, suggesting future applications in stereochemical molecular representation.
- **Vorticity Analogy**: Decomposing second-order tensors into symmetric deformation and antisymmetric rotational curl is standard in continuum mechanics; whether learned neural state spaces benefit from this decomposition in physical simulations remains an active research question.

---

## 7. Repository Structure

```
IMF/
├── README.md                                          # Comprehensive documentation & grounded theory
├── pyproject.toml                                     # Python project configuration (uv / pip)
├── lakefile.lean                                      # Lean 4 Lake configuration
├── lean-toolchain                                     # Lean 4 version pinning (v4.33.1)
├── lean/                                              # Formally verified Lean 4 theorems
│   ├── DiscreteToContinuousBridge.lean                # Sector symmetry & direct sum decomposition
│   └── ContinuousCrossingBounds.lean                  # Frobenius orthogonality & energy conservation
├── polytope_connector.py                              # Configurable higher-dimensional polytope connector
├── triton_savg_kernel.py                              # Triton GPU fused scan with Autograd backward support
├── higher_arity_simplex.py                            # Arity-3 and Arity-4 CP-factorized simplex tensor bindings
├── test_savg_harness.py                               # PyTorch SAVG integration harness
├── test_savg_directionality.py                        # Empirical directional selectivity test on trained pairs
├── benchmark_mqar.py                                  # Multi-Query Associative Recall benchmark
├── benchmark_polytopes.py                             # Polytope comparison benchmark suite
├── benchmark_spo_multihop.py                          # Multi-hop SPO knowledge retrieval (no target leakage)
├── stress_spo_multihop.py                             # 3-hop multi-entity knowledge stress test
├── tests/                                             # Automated pytest verification test suite
├── scripts/                                           # Asset and logo generation scripts
├── papers/                                            # Research reports and theoretical foundations
├── docs/reviews/                                      # Specification notes and peer reviews
└── assets/                                            # Project brand assets and logos
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
device = "cuda" if torch.cuda.is_available() else "cpu"
connector = ConfigurablePolytopeConnector(d_model=64, preset="decayotton_orthoplex").to(device)
x = torch.randn(16, 128, 64, device=device)

# Extract normalized barycentric coordinates
coords = connector.get_coordinates(x)          # [16, 128, 20]
grid_mod = connector.compute_grid_modulation(x) # [16, 128, 1, 1]

# 2. Fused SAVG Layer
fused_layer = FusedSAVGLayer(d_model=64, preset="decayotton_orthoplex").to(device)
out = fused_layer(x)                            # [16, 128, 64]
```

### Running the Verification Suite & Benchmarks

```bash
# 1. Verify formal Lean 4 theorems (Zero Mathlib dependency)
lake build

# 2. Benchmark Triton JIT Fused GPU kernel & verify backward autograd
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

## 9. Technical Reports & Publications

The IMF foundation and its empirical/theoretical formulations are detailed across three internal Stratum Research Group publications located in `papers/`:

1. **[Technical Report 01: Lie-Algebraic Memory Splitting](papers/01_savg_lie_algebraic_memory_splitting.md)**  
   *Symmetric-Antisymmetric Virtual Grid Attention (SAVG) and Directional Discrimination.*  
   Formalizes the $\mathrm{Sym}^2 \oplus \bigwedge^2$ Jordan-Lie decomposition, phase-inversion dynamics, and hardware-fused Triton JIT kernels with PyTorch autograd compatibility.

2. **[Technical Report 02: Higher-Dimensional Polytope Landmark Connectors (HDPLC)](papers/02_hdplc_higher_dimensional_polytope_connectors.md)**  
   *Barycentric Simplex Frames, Orthoplex Antipodal Pairs, and Multi-Hop Knowledge Topology.*  
   Formulates regular polytope coordinate embeddings across the Enneazetton (9D), Decayotton (10D), and Hendecaxennon (11D), featuring Canonical Polyadic (CP) rank factorizations for arity-3 and arity-4 hyperface bindings.

3. **[Foundational Position Paper 03: The Architecture of Meaning](papers/03_epistemological_foundations_and_real_world_applications.md)**  
   *Epistemological Foundations, Symmetry-Governed Topology, and Potential Application Horizons of SAVG and HDPLC.*  
   Examines the conceptual transition from unconstrained correlation to symmetry-governed topological geometry, algebraic bridge proofs, and potential research horizons across mechanistic interpretability, neuromorphic hardware, automated theorem proving, and sequence modeling.

---

## 10. Visual Identity & Logo Variants

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

The primary IMF logo is located in `assets/imf_logo.jpg` (`1376x768`), with script-based generation for custom variants available in `scripts/build_imf_logos.py`.

---

## 11. Ownership & Governance

IMF is designed, owned, and maintained by **Stratum Research Group (SRG)**. All architectural specifications, formal Lean 4 theorems, and CUDA/Triton memory kernels are governed under the Stratum Research Group research framework.

---

## 12. Citation & References

```bibtex
@techreport{imf2026polytope,
  title={Interaction Primitive Families and Higher-Dimensional Polytope Virtual Grid Memory},
  author={Stratum Research Group},
  institution={Stratum Research Group},
  number={SRG-IMF-2026-TR01},
  year={2026}
}
```
