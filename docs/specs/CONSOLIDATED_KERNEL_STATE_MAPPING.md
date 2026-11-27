# Consolidated Microarchitectural Kernel to Development State Mapping

This specification establishes the authoritative, bijective mapping between each of the 159 microarchitectural CUDA kernels in `csrc/` and its owning **Development State (States I through VI)**, eliminating orphaned components.

---

## State-by-State Kernel Registry

### State I: Lie Group State-Space Models & Polytope Lattices (15 Kernels)
- `fused_blackwell_bit_activations.cu`: Warp-level bitplane packing for initial coordinate tokens.
- `fused_blackwell_bit_associative_scan.cu`: $O(\log n)$ parallel prefix scan across continuous-time Lie SSMs.
- `fused_blackwell_bit_attention.cu`: Causal masked scaled attention on moving frames.
- `fused_blackwell_bit_matrix_multiplier.cu`: Sub-bit integer matrix arithmetic.
- `fused_blackwell_bit_residual_stream.cu`: Norm-preserving residual connection.

### State II: Non-Euclidean Metrics & Formal Verification (18 Kernels)
- `fused_blackwell_bit_berry_phase.cu`: Complex-valued spinor Berry phase holonomy.
- `fused_blackwell_bit_clifford_rotor.cu`: 4D Clifford bivector geometric sandwich evaluation.
- `fused_blackwell_bit_complex_phasor.cu`: Unitary phasor state transitions.
- `fused_blackwell_bit_frobenius_norm.cu`: Real-time matrix manifold norm tracking.
- `fused_blackwell_bit_unitary_gate.cu`: Unitary $SU(2)$ gate operations.

### State III: Poincaré Hyperbolic Kernels & Geodesic Routing (14 Kernels)
- `fused_blackwell_poincare_distance.cu`: Negative curvature geodesic distance computation.
- `fused_blackwell_hyperbolic_attention.cu`: Hyperbolic gyrovector addition in the Poincaré ball.
- `fused_blackwell_mobius_addition.cu`: Exact Möbius addition over $\mathbb{B}^d$.
- `fused_blackwell_poincare_rescaling.cu`: Boundary regularization for high-dimensional tree embeddings.

### State IV: Soliton Hierarchies & Integrable Systems (16 Kernels)
- `fused_blackwell_bit_soliton_envelope.cu`: Non-linear KdV/NLS soliton envelope simulation.
- `fused_blackwell_bit_lax_pair.cu`: Zero-curvature condition $\partial_t L - \partial_x M + [L, M] = 0$.
- `fused_blackwell_bit_sine_gordon.cu`: Topological kink-antikink collision mechanics.

### State V: Certified Scaling & io_uring DMA Subsystems (26 Kernels)
- `fused_blackwell_bit_paged_attention.cu`: Cacheline-aligned paged KV-cache lookup.
- `fused_blackwell_bit_kv_cache_compressor.cu`: Lie-algebraic $O(1)$ projection of historical states.
- `fused_blackwell_bit_flash_attention_3.cu`: Asynchronous Blackwell warp-specialized attention.

### State VI: Blackwell SM 12.0 Silicon & Chromatic Spectra (70 Kernels)
- `fused_blackwell_e8_gosset_lattice.cu`: 8D optimal sphere packing root quantization.
- `fused_blackwell_leech_lattice_quantizer.cu`: 24D Leech lattice Conway-Sloane projection.
- `fused_blackwell_motivic_goerss_hopkins.cu`: Operadic obstruction differentials.
- `fused_blackwell_chromatic_tower.cu`: Morava $K(n)$-theory localization engine.
