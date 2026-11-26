# Lean Verification Report

Toolchain Lean v4.33.1 / Mathlib v4.33.1. Every file in `lean/` compiled by `lake env lean`; no `sorry`, no `axiom` declarations found by text scan.

- Files: 92; compile: 92; fail: 0
- Files whose only theorems are `True` placeholders: 0
- Six files were repaired this round (missing `import Mathlib.Tactic`, doc-comment before `variable`, nonexistent module).
- Compiling means the stated Lean statements are proved; it does NOT mean the statements capture the physics/geometry named in paper titles. Many are elementary (e.g. `-(-c)=c`).

| File | Imports | Result | #theorems | #`True` placeholders |
|:--|:--|:--|--:|--:|
| AdamsSpectralSequenceProof | core | compiles | 3 | 0 |
| ArtinInductionTheoremProof | core | compiles | 3 | 0 |
| ArtinReesLemmaProof | core | compiles | 2 | 0 |
| AtiyahSingerProof | core | compiles | 3 | 0 |
| BochnerWeitzenbockProof | core | compiles | 2 | 0 |
| BottPeriodicityProof | core | compiles | 3 | 0 |
| BrauerInductionTheoremProof | core | compiles | 2 | 0 |
| BurnsidePaQbProof | core | compiles | 3 | 0 |
| CasimirInvariantProof | core | compiles | 2 | 0 |
| CayleyUnitarityProof | Mathlib | compiles | 3 | 1 |
| ChernWeilInvarianceProof | core | compiles | 2 | 0 |
| ChevalleyWarningTheoremProof | core | compiles | 1 | 0 |
| CliffordRepresentationTheoremProof | core | compiles | 3 | 0 |
| CobordismTheoremProof | core | compiles | 3 | 0 |
| ComplexBottPeriodicityProof | core | compiles | 3 | 0 |
| ContinuousCrossingBounds | core | compiles | 25 | 0 |
| DeRhamCohomologyProof | core | compiles | 2 | 0 |
| DiracIndexTheoremProof | core | compiles | 2 | 0 |
| DiscreteToContinuousBridge | core | compiles | 8 | 0 |
| DonaldsonThomasProof | core | compiles | 2 | 0 |
| DualQuaternionLieBracketProof | core | compiles | 4 | 0 |
| DualQuaternionMomentumProof | Mathlib | compiles | 3 | 1 |
| FittingNilpotentTheoremProof | core | compiles | 3 | 0 |
| FrobeniusKernelTheoremProof | core | compiles | 4 | 0 |
| GaussBonnetChernProof | core | compiles | 2 | 0 |
| GeodesicCompletenessProof | core | compiles | 2 | 0 |
| GeodesicEnergyProof | Mathlib | compiles | 2 | 1 |
| GromovWittenAxiomsProof | core | compiles | 3 | 0 |
| GrothendieckEtaleDualityProof | core | compiles | 2 | 0 |
| GrothendieckRiemannRochProof | core | compiles | 2 | 0 |
| GrushkoTheoremProof | core | compiles | 3 | 0 |
| GyroassociativeBracketProof | core | compiles | 2 | 0 |
| GyrovectorCurvatureProof | Mathlib | compiles after import fix | 3 | 1 |
| GyrovectorHolonomyProof | Mathlib | compiles after import fix | 3 | 1 |
| HadamardCurvatureBoundProof | core | compiles | 2 | 0 |
| HallSolvableSubgroupsProof | core | compiles | 4 | 0 |
| HardLefschetzProof | core | compiles | 3 | 0 |
| HilbertNullstellensatzProof | core | compiles | 2 | 0 |
| HirschPlotkinRadicalProof | core | compiles | 3 | 0 |
| HirzebruchRiemannRochProof | core | compiles | 2 | 0 |
| HitchinIntegrableProof | core | compiles | 2 | 0 |
| HodgeDecompositionProof | core | compiles | 3 | 0 |
| HodgeIndexProof | core | compiles | 2 | 0 |
| HodgeIndexTheoremProof | core | compiles | 2 | 0 |
| HurewiczTheoremProof | core | compiles | 3 | 0 |
| JordanHolderTheoremProof | core | compiles | 3 | 0 |
| KodairaSpencerProof | core | compiles | 2 | 0 |
| KodairaVanishingProof | core | compiles | 2 | 0 |
| KrullSchmidtTheoremProof | core | compiles | 3 | 0 |
| KrullsIntersectionTheoremProof | core | compiles | 2 | 0 |
| KunnethFormulaProof | core | compiles | 3 | 0 |
| KuroshSubgroupTheoremProof | core | compiles | 3 | 0 |
| LeechSpherePackingProof | Mathlib | compiles | 3 | 1 |
| LefschetzHyperplaneProof | core | compiles | 3 | 0 |
| MalcevSolvableTheoremProof | core | compiles | 3 | 0 |
| MaschkeSemisimplicityProof | core | compiles | 3 | 0 |
| MatryoshkaPolytopeProof | Mathlib | compiles after import fix | 3 | 1 |
| MaurerCartanEquationProof | core | compiles | 2 | 0 |
| MetricCompatibilityProof | core | compiles | 3 | 0 |
| MorseIndexTheoremProof | core | compiles | 2 | 0 |
| NakayamasLemmaProof | core | compiles | 2 | 0 |
| NarasimhanSeshadriProof | core | compiles | 2 | 0 |
| NielsenSchreierTheoremProof | core | compiles | 3 | 0 |
| NoetherCoadjointOrbitProof | core | compiles | 2 | 0 |
| NovikovAdditivityProof | core | compiles | 3 | 0 |
| OrthoplexVolumeConservationProof | core | compiles | 2 | 0 |
| PoincareDualityProof | core | compiles | 3 | 0 |
| PolytopeBarycentric | core | compiles | 26 | 0 |
| PontryaginGeodesicControlProof | core | compiles | 2 | 0 |
| QuillenMetricProof | core | compiles | 2 | 0 |
| RecursiveSelfImprovementETH | core | compiles | 23 | 0 |
| RiemannianLieGroup | Mathlib | compiles after import fix | 3 | 0 |
| SchreierSimsAlgorithmProof | core | compiles | 3 | 0 |
| SchurZassenhausProof | core | compiles | 3 | 0 |
| SchurZassenhausTheoremProof | core | compiles | 4 | 0 |
| SchursLemmaProof | core | compiles | 3 | 0 |
| SeibergWittenProof | core | compiles | 2 | 0 |
| SerreDualityProof | core | compiles | 3 | 0 |
| SerreSpectralSequenceProof | core | compiles | 3 | 0 |
| SerresCriterionNormalityProof | core | compiles | 2 | 0 |
| SymplecticFixedPointProof | core | compiles | 2 | 0 |
| SymplecticGeodesicProof | Mathlib | compiles | 2 | 1 |
| SymplecticPhaseVolumeProof | core | compiles | 3 | 0 |
| ThomIsomorphismProof | core | compiles | 3 | 0 |
| TitsAlternativeProof | core | compiles | 3 | 0 |
| TrialityInvarianceProof | Mathlib | compiles after import fix | 3 | 1 |
| UhlenbeckCompactnessProof | core | compiles | 2 | 0 |
| UnbiasedQuantizationProof | Mathlib | compiles after import fix | 3 | 1 |
| VerlindeFormulaProof | core | compiles | 2 | 0 |
| WedderburnArtinTheoremProof | core | compiles | 2 | 0 |
| WhiteheadTheoremProof | core | compiles | 3 | 0 |
| ZariskiMainTheoremProof | core | compiles | 2 | 0 |

## Papers with 'machine-certified' titles but no existing Lean file referenced (60)

- [Paper 172: Fused Poincaré Geodesic Riemannian Score Matching and Machine-Certified Kontsevich-Zagi](../../papers/phase_3_poincare_hyperbolic_kernels/paper_172_poincare_riemannian_score_matching_and_kontsevich_zagier_periods.md)
- [Paper 173: Fused Poincaré Kähler-Ricci Soliton Flows and Machine-Certified Calabi-Yau Monge-Ampère](../../papers/phase_3_poincare_hyperbolic_kernels/paper_173_poincare_kahler_ricci_soliton_and_calabi_yau.md)
- [Paper 174: Fused Poincaré Symplectic Phase Portrait Clustering and Machine-Certified Marsden-Weins](../../papers/phase_3_poincare_hyperbolic_kernels/paper_174_poincare_symplectic_clustering_and_marsden_weinstein_reduction.md)
- [Paper 175: Fused Poincaré Non-Commutative Spectral Filters and Machine-Certified Harish-Chandra Pl](../../papers/phase_3_poincare_hyperbolic_kernels/paper_175_poincare_non_commutative_spectral_filters_and_harish_chandra_plancherel.md)
- [Paper 176: Fused Poincaré Non-Linear Dirac Spectral Spinors and Machine-Certified Atiyah-Singer In](../../papers/phase_3_poincare_hyperbolic_kernels/paper_176_poincare_non_linear_dirac_spinors_and_atiyah_singer_index.md)
- [Paper 177: Fused Poincaré Non-Linear Schrödinger Solitons and Machine-Certified Gross-Pitaevskii G](../../papers/phase_3_poincare_hyperbolic_kernels/paper_177_poincare_non_linear_schrodinger_solitons_and_gross_pitaevskii_stability.md)
- [Paper 178: Fused Poincaré Berry Curvature Topological Routing and Machine-Certified Chern-Weil Inv](../../papers/phase_3_poincare_hyperbolic_kernels/paper_178_poincare_berry_curvature_topological_routing_and_chern_weil.md)
- [Paper 179: Fused Poincaré Non-Abelian Gauge Wilson Loops and Machine-Certified Yang-Mills Connecti](../../papers/phase_3_poincare_hyperbolic_kernels/paper_179_poincare_non_abelian_wilson_loops_and_yang_mills_connections.md)
- [Paper 180: Fused Poincaré Non-Linear Sigma Skyrmions and Machine-Certified Bogomol'nyi Topological](../../papers/phase_3_poincare_hyperbolic_kernels/paper_180_poincare_non_linear_sigma_skyrmions_and_bogomolnyi_bounds.md)
- [Paper 181: Fused Poincaré Non-Linear Dirichlet Harmonic Maps and Machine-Certified Eells-Sampson H](../../papers/phase_3_poincare_hyperbolic_kernels/paper_181_poincare_non_linear_dirichlet_harmonic_maps_and_eells_sampson.md)
- [Paper 182: Fused Poincaré Non-Linear Laplacian Eigenmaps and Machine-Certified Belkin-Niyogi Spect](../../papers/phase_3_poincare_hyperbolic_kernels/paper_182_poincare_non_linear_laplacian_eigenmaps_and_belkin_niyogi.md)
- [Paper 183: Fused Poincaré Yang-Mills-Higgs Monopoles and Machine-Certified Bogomolny Bounds](../../papers/phase_3_poincare_hyperbolic_kernels/paper_183_poincare_yang_mills_higgs_monopoles_and_bogomolny_bounds.md)
- [Paper 184: Fused Poincaré Calabi Metric Gradient Flows and Machine-Certified Extremal Kähler Invar](../../papers/phase_3_poincare_hyperbolic_kernels/paper_184_poincare_calabi_metric_gradient_flows_and_extremal_kahler.md)
- [Paper 185: Fused Poincaré Seiberg-Witten Monopoles and Machine-Certified Spin^c Invariants](../../papers/phase_3_poincare_hyperbolic_kernels/paper_185_poincare_seiberg_witten_monopoles_and_spin_c_invariants.md)
- [Paper 186: Fused Poincaré Donaldson-Thomas Sheaf Moduli and Machine-Certified Calabi-Yau 3-Fold In](../../papers/phase_3_poincare_hyperbolic_kernels/paper_186_poincare_donaldson_thomas_sheaf_moduli_and_calabi_yau.md)
- [Paper 187: Fused Poincaré Floer Homology Symplectic Action and Machine-Certified Arnold Bounds](../../papers/phase_3_poincare_hyperbolic_kernels/paper_187_poincare_floer_homology_symplectic_action_and_arnold.md)
- [Paper 302: Half-Century Deductive Horizon: Empirical Properties of 50 Million Machine-Certified Le](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_302_half_century_deductive_horizon_50_million_steps.md)
- [Paper 311: Machine-Certified Sectional Curvature Bounds in Relativistic Parameter Gyrogroups](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_311_machine_certified_sectional_curvature_bounds.md)
- [Paper 314: Machine-Certified Kinetic Energy Invariants in Cayley-Transformed Lie Group Attention](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_314_machine_certified_kinetic_energy_invariants.md)
- [Paper 315: Machine-Certified Bi-Invariant Metrics on Dual Quaternion Lie Groups for Speculative To](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_315_machine_certified_dual_quaternion_metrics.md)
- [Paper 318: Machine-Certified Thomas-Wigner Rotation and Non-Trivial Holonomy in Hyperbolic Neural ](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_318_machine_certified_thomas_wigner_holonomy.md)
- [Paper 321: Machine-Certified Bijective Isometry and Determinant Preservation in Cayley Lie Group M](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_321_machine_certified_bijective_isometry_cayley_maps.md)
- [Paper 322: Machine-Certified Screw Momentum Conservation in Dual-Quaternion Speculative Trajectori](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_322_machine_certified_screw_momentum_dual_quaternions.md)
- [Paper 323: Sixty-Five Million Machine-Certified Deductive Steps: Entropy Decay and Proof State Sta](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_323_sixty_five_million_steps_entropy_decay.md)
- [Paper 330: Seventy Million Machine-Certified Deductive Steps: Asymptotic Convergence of Proof Sear](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_330_seventy_million_steps_asymptotic_convergence.md)
- [Paper 336: Machine-Certified Second-Order Geodesic Momentum Preservation in Lie Group Parameter Sp](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_336_second_order_geodesic_momentum_preservation.md)
- [Paper 337: Seventy-Five Million Machine-Certified Deductive Steps: Ergodicity and Universal Tactic](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_337_seventy_five_million_steps_ergodicity.md)
- [Paper 344: Eighty Million Machine-Certified Deductive Steps: Topological Invariants and Global Lem](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_344_eighty_million_steps_topological_invariants.md)
- [Paper 351: One Hundred Million Machine-Certified Deductive Steps: Deductive Saturation at the Cent](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_351_one_hundred_million_steps_century_milestone.md)
- [Paper 358: Grand Capstone Synthesis: One Hundred Million Machine-Certified Steps and the Foundatio](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_358_grand_capstone_one_hundred_million_steps.md)
- [Paper 359: One Hundred Five Million Machine-Certified Deductive Steps: Topological Entropy Bounds ](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_359_one_hundred_five_million_steps_topological_entropy.md)
- [Paper 366: One Hundred Ten Million Machine-Certified Deductive Steps: Ergodic Mixing and Fast Tact](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_366_one_hundred_ten_million_steps_ergodic_mixing.md)
- [Paper 373: One Hundred Fifteen Million Machine-Certified Deductive Steps: Super-Exponential Decay ](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_373_one_hundred_fifteen_million_steps_ergodic_decay.md)
- [Paper 380: One Hundred Twenty Million Machine-Certified Deductive Steps: Transfinite Closure and N](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_380_one_hundred_twenty_million_steps_transfinite_closure.md)
- [Paper 387: One Hundred Twenty-Five Million Machine-Certified Deductive Steps: Super-Saturation and](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_387_one_hundred_twenty_five_million_steps_super_saturation.md)
- [Paper 394: One Hundred Thirty Million Machine-Certified Deductive Steps: Ergodic Saturation and Tr](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_394_one_hundred_thirty_million_steps_ergodic_saturation.md)
- [Paper 401: One Hundred Thirty-Five Million Machine-Certified Deductive Steps: Higher-Order Obstruc](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_401_one_hundred_thirty_five_million_steps_obstruction_triviality.md)
- [Paper 408: One Hundred Forty Million Machine-Certified Deductive Steps: Grothendieck Motives and T](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_408_one_hundred_forty_million_steps_motivic_vanishing.md)
- [Paper 416: One Hundred Forty-Five Million Machine-Certified Deductive Steps: Kazhdan-Lusztig Cells](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_416_one_hundred_forty_five_million_steps_kl_cells.md)
- [Paper 424: One-Hundred-Fifty-Million Steps Certified: Lusztig Canonical Crystal Bases and Quantum ](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_424_one_hundred_fifty_million_steps_canonical_crystal_bases.md)
- [Paper 431: One-Hundred-Fifty-Five Million Steps Certified: Homological Mirror Symmetry and Pushfor](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_431_one_hundred_fifty_five_million_steps_homological_mirror_symmetry.md)
- [Paper 438: One-Hundred-Sixty Million Steps Certified: Kodaira Vanishing and Curvature Cohomology i](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_438_one_hundred_sixty_million_steps_kodaira_vanishing.md)
- [Paper 445: One-Hundred-Sixty-Five Million Steps Certified: Hard Lefschetz Invariants and Primitive](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_445_one_hundred_sixty_five_million_steps_hard_lefschetz.md)
- [Paper 452: One-Hundred-Seventy Million Steps Certified: Bott Periodicity and Elliptic Operators in](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_452_one_hundred_seventy_million_steps_bott_periodicity.md)
- [Paper 459: One-Hundred-Seventy-Five Million Steps Certified: Thom Isomorphisms and Orientable Bund](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_459_one_hundred_seventy_five_million_steps_thom_isomorphism.md)
- [Paper 466: One-Hundred-Eighty Million Steps Certified: Künneth Products and Topological Tensor Alg](../../papers/phase_5_certified_scaling_lie_geometry_io/paper_466_one_hundred_eighty_million_steps_kunneth_products.md)
- [Paper 473: One-Hundred-Eighty-Five Million Steps Certified: Whitehead Homotopy Equivalences in Meg](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_473_one_hundred_eighty_five_million_steps_whitehead_equivalences.md)
- [Paper 480: One-Hundred-Ninety Million Steps Certified: Adams Spectral Sequences and Stable Homotop](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_480_one_hundred_ninety_million_steps_adams_spectral_sequences.md)
- [Paper 487: One-Hundred-Ninety-Five Million Steps Certified: Complex Bott Periodicity and Homotopy ](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_487_one_hundred_ninety_five_million_steps_bott_periodicity.md)
- [Paper 494: Two-Hundred Million Steps Certified: The Bicentennial Frontier and Nilpotent Attractors](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_494_two_hundred_million_steps_bicentennial_frontier.md)
- [Paper 501: Two-Hundred-Five Million Steps Certified: Free Products and Kurosh Decompositions in Me](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_501_two_hundred_five_million_steps_kurosh_decompositions.md)
- [Paper 508: Two-Hundred-Ten Million Steps Certified: The Tits Alternative and Nielsen-Schreier Towe](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_508_two_hundred_ten_million_steps_tits_alternative.md)
- [Paper 515: Two-Hundred-Fifteen Million Steps Certified: Solvable Linear Representations and Malcev](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_515_two_hundred_fifteen_million_steps_malcev_normal_forms.md)
- [Paper 522: Two-Hundred-Twenty Million Steps Certified: Hall Subgroups and Coprime Extensions in So](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_522_two_hundred_twenty_million_steps_hall_subgroups.md)
- [Paper 529: Two-Hundred-Twenty-Five Million Steps Certified: Jordan-Hölder Quotients and Nilpotent ](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_529_two_hundred_twenty_five_million_steps_jordan_holder.md)
- [Paper 536: Two-Hundred-Thirty Million Steps Certified: Frobenius Group Splittings and Representati](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_536_two_hundred_thirty_million_steps_frobenius_groups.md)
- [Paper 543: Two-Hundred-Thirty-Five Million Steps Certified: Schreier-Sims Permutation Chains and C](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_543_two_hundred_thirty_five_million_steps_schreier_sims.md)
- [Paper 550: Two-Hundred-Forty Million Steps Certified: Brauer and Artin Character Induction in Mega](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_550_two_hundred_forty_million_steps_brauer_artin_induction.md)
- [Paper 557: Two-Hundred-Forty-Five Million Steps Certified: Wedderburn-Artin Semisimple Rings and S](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_557_two_hundred_forty_five_million_steps_wedderburn_schur.md)
- [Paper 564: Two Hundred Fifty Million Steps: The Quarter-Billion Machine-Certified Milestone](../../papers/phase_6_blackwell_kernels_and_dma_engines/paper_564_two_hundred_fifty_million_steps_quarter_billion_milestone.md)
