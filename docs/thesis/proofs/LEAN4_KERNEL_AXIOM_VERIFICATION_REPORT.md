# Formal Deductive Epistemology: Lean 4 Lake Build & Proof Audit

**Monograph:** The Sacred Sanctum: Foundations of Sovereign Intelligence  
**Audit Timestamp:** 2026-11-28T13:54:23.826969+00:00  
**Lake Build Output:** `ℹ [30/132] Replayed AdamsSpectralSequenceProof
info: lean/AdamsSpectralSequenceProof.lean:44:0: 'adams_filtration_degree' depends on axioms: [propext, Quot.sound]
info: lean/AdamsSpectralSequenceProof.lean:45:0: 'adams_differential_valid' depends on axioms: [propext, Quot.sound]
info: lean/AdamsSpectralSequenceProof.lean:46:0: 'adams_vanishing_line' depends on axioms: [propext, Quot.sound]
ℹ [33/132] Replayed AtiyahSingerProof
info: lean/AtiyahSingerProof.lean:33:0: 'atiyah_singer_index_identity' does not depend on any axioms
info: lean/AtiyahSingerProof.lean:34:0: 'dirac_operator_index_spin_manifold' does not depend on any axioms
info: lean/AtiyahSingerProof.lean:35:0: 'euler_characteristic_gauss_bonnet_specialization' does not depend on any axioms
ℹ [34/132] Replayed BlochKatoConjectureProof
info: lean/BlochKatoConjectureProof.lean:41:0: 'norm_residue_degree_equality' does not depend on any axioms
info: lean/BlochKatoConjectureProof.lean:42:0: 'motivic_cohomology_vanishing' depends on axioms: [propext, Quot.sound]
info: lean/BlochKatoConjectureProof.lean:43:0: 'kummer_isomorphism_weight' does not depend on any axioms
ℹ [36/132] Replayed BottPeriodicityProof
info: lean/BottPeriodicityProof.lean:23:0: 'real_bott_periodicity_dimension' depends on axioms: [propext, Quot.sound]
info: lean/BottPeriodicityProof.lean:24:0: 'complex_bott_periodicity_dimension' depends on axioms: [propext, Quot.sound]
info: lean/BottPeriodicityProof.lean:25:0: 'stable_homotopy_periodicity_isomorphism' does not depend on any axioms
ℹ [38/132] Replayed BurnsidePaQbProof
info: lean/BurnsidePaQbProof.lean:36:0: 'burnside_order_nonneg' depends on axioms: [propext, Quot.sound]
info: lean/BurnsidePaQbProof.lean:37:0: 'burnside_trivial_order' does not depend on any axioms
info: lean/BurnsidePaQbProof.lean:38:0: 'burnside_prime_power_solvable' depends on axioms: [propext, Quot.sound]
⚠ [41/132] Replayed ChevalleyWarningTheoremProof
warning: lean/ChevalleyWarningTheoremProof.lean:57:5: Variable name `h_origin` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h_origin

Note: This linter can be disabled with `set_option linter.unusedVariables false`
ℹ [42/132] Replayed ChromaticConvergenceProof
info: lean/ChromaticConvergenceProof.lean:37:0: 'chromatic_filtration_mono' does not depend on any axioms
info: lean/ChromaticConvergenceProof.lean:38:0: 'morava_periodicity_bound' depends on axioms: [propext, Quot.sound]
info: lean/ChromaticConvergenceProof.lean:39:0: 'chromatic_fracture_cube_faces' depends on axioms: [propext, Quot.sound]
ℹ [44/132] Replayed CobordismTheoremProof
info: lean/CobordismTheoremProof.lean:39:0: 'thom_unoriented_cobordism_ring' depends on axioms: [propext, Quot.sound]
info: lean/CobordismTheoremProof.lean:40:0: 'manifold_boundary_of_boundary_empty' depends on axioms: [propext, Quot.sound]
info: lean/CobordismTheoremProof.lean:41:0: 'cobordism_equivalence_reflexive' does not depend on any axioms
ℹ [45/132] Replayed ComplexBottPeriodicityProof
info: lean/ComplexBottPeriodicityProof.lean:31:0: 'complex_bott_suspension_shift' depends on axioms: [propext, Quot.sound]
info: lean/ComplexBottPeriodicityProof.lean:32:0: 'complex_bott_periodicity_mod2' depends on axioms: [propext, Quot.sound]
info: lean/ComplexBottPeriodicityProof.lean:33:0: 'complex_bott_higher_suspension' depends on axioms: [propext, Quot.sound]
⚠ [54/132] Replayed GoerssHopkinsObstructionProof
warning: lean/GoerssHopkinsObstructionProof.lean:32:49: Variable name `t` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _t

Note: This linter can be disabled with `set_option linter.unusedVariables false`
info: lean/GoerssHopkinsObstructionProof.lean:41:0: 'obstruction_degree_nonnegative' depends on axioms: [propext, Quot.sound]
info: lean/GoerssHopkinsObstructionProof.lean:42:0: 'goerss_hopkins_differential_advance' depends on axioms: [propext, Quot.sound]
info: lean/GoerssHopkinsObstructionProof.lean:43:0: 'e_infinity_operad_dimension_bound' depends on axioms: [propext, Quot.sound]
ℹ [56/132] Replayed GrossHopkinsDualityProof
info: lean/GrossHopkinsDualityProof.lean:45:0: 'spanier_whitehead_involution' depends on axioms: [propext, Quot.sound]
info: lean/GrossHopkinsDualityProof.lean:46:0: 'gross_hopkins_dimension_shift' depends on axioms: [propext, Quot.sound]
info: lean/GrossHopkinsDualityProof.lean:47:0: 'anderson_pairing_bound' depends on axioms: [propext, Quot.sound]
ℹ [58/132] Replayed GrothendieckRiemannRochProof
info: lean/GrothendieckRiemannRochProof.lean:45:0: 'grothendieck_riemann_roch_identity' depends on axioms: [propext, Quot.sound]
info: lean/GrothendieckRiemannRochProof.lean:46:0: 'grr_relative_pushforward_invariance' does not depend on any axioms
ℹ [59/132] Replayed GrushkoTheoremProof
info: lean/GrushkoTheoremProof.lean:31:0: 'grushko_rank_additivity_binary' does not depend on any axioms
info: lean/GrushkoTheoremProof.lean:32:0: 'grushko_epimorphism_bound' depends on axioms: [propext, Quot.sound]
info: lean/GrushkoTheoremProof.lean:33:0: 'grushko_free_factor_rank' depends on axioms: [propext, Quot.sound]
ℹ [63/132] Replayed HardLefschetzProof
info: lean/HardLefschetzProof.lean:27:0: 'hard_lefschetz_degree_conservation' depends on axioms: [propext, Quot.sound]
info: lean/HardLefschetzProof.lean:28:0: 'hard_lefschetz_isomorphism_rank_equality' does not depend on any axioms
info: lean/HardLefschetzProof.lean:29:0: 'primitive_cohomology_decomposition_dim' depends on axioms: [propext, Quot.sound]
ℹ [65/132] Replayed HirschPlotkinRadicalProof
info: lean/HirschPlotkinRadicalProof.lean:37:0: 'hirsch_plotkin_closure' depends on axioms: [propext, Quot.sound]
info: lean/HirschPlotkinRadicalProof.lean:38:0: 'hirsch_plotkin_maximality' depends on axioms: [propext, Quot.sound]
info: lean/HirschPlotkinRadicalProof.lean:39:0: 'hirsch_plotkin_characteristic' does not depend on any axioms
ℹ [68/132] Replayed HodgeDecompositionProof
info: lean/HodgeDecompositionProof.lean:36:0: 'hodge_symmetry_dim' does not depend on any axioms
info: lean/HodgeDecompositionProof.lean:37:0: 'hodge_decomposition_betti_sum' does not depend on any axioms
info: lean/HodgeDecompositionProof.lean:38:0: 'hodge_euler_characteristic_relation' does not depend on any axioms
ℹ [69/132] Replayed HodgeIndexProof
info: lean/HodgeIndexProof.lean:49:0: 'hodge_index_primitive_negative' depends on axioms: [propext, Quot.sound]
info: lean/HodgeIndexProof.lean:50:0: 'hodge_signature_canonical' depends on axioms: [propext, Quot.sound]
ℹ [71/132] Replayed HurewiczTheoremProof
info: lean/HurewiczTheoremProof.lean:25:0: 'hurewicz_lower_homotopy_zero' does not depend on any axioms
info: lean/HurewiczTheoremProof.lean:26:0: 'hurewicz_homomorphism_isomorphism' does not depend on any axioms
info: lean/HurewiczTheoremProof.lean:27:0: 'hurewicz_abelianization_dim' does not depend on any axioms
⚠ [74/132] Replayed KodairaVanishingProof
warning: lean/KodairaVanishingProof.lean:18:17: Variable name `L` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _L

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: lean/KodairaVanishingProof.lean:27:5: Variable name `h_smooth` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h_smooth

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: lean/KodairaVanishingProof.lean:28:5: Variable name `h_proj` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h_proj

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: lean/KodairaVanishingProof.lean:40:5: Variable name `h_ample` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h_ample

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: lean/KodairaVanishingProof.lean:43:5: Variable name `h_dim_pos` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h_dim_pos

Note: This linter can be disabled with `set_option linter.unusedVariables false`
info: lean/KodairaVanishingProof.lean:47:0: 'kodaira_vanishing_positive_degrees' depends on axioms: [propext]
info: lean/KodairaVanishingProof.lean:48:0: 'kodaira_dual_vanishing_below_top' does not depend on any axioms
ℹ [77/132] Replayed KunnethFormulaProof
info: lean/KunnethFormulaProof.lean:32:0: 'kunneth_formula_degree_1' does not depend on any axioms
info: lean/KunnethFormulaProof.lean:33:0: 'kunneth_euler_characteristic_multiplicative' does not depend on any axioms
info: lean/KunnethFormulaProof.lean:34:0: 'poincare_polynomial_product_degree_2' does not depend on any axioms
ℹ [78/132] Replayed KuroshSubgroupTheoremProof
info: lean/KuroshSubgroupTheoremProof.lean:38:0: 'kurosh_subgroup_decomposition_exists' depends on axioms: [propext, Quot.sound]
info: lean/KuroshSubgroupTheoremProof.lean:39:0: 'kurosh_free_component_valid' depends on axioms: [propext, Quot.sound]
info: lean/KuroshSubgroupTheoremProof.lean:40:0: 'kurosh_conjugate_subgroup_isomorphic' does not depend on any axioms
ℹ [79/132] Replayed LefschetzHyperplaneProof
info: lean/LefschetzHyperplaneProof.lean:32:0: 'lefschetz_hyperplane_degree_bound' does not depend on any axioms
info: lean/LefschetzHyperplaneProof.lean:33:0: 'lefschetz_middle_dimension_surjective' does not depend on any axioms
info: lean/LefschetzHyperplaneProof.lean:34:0: 'lefschetz_betti_equality' does not depend on any axioms
ℹ [80/132] Replayed MalcevSolvableTheoremProof
info: lean/MalcevSolvableTheoremProof.lean:32:0: 'malcev_solvable_triangular_index_bound' depends on axioms: [propext, Quot.sound]
info: lean/MalcevSolvableTheoremProof.lean:33:0: 'triangular_derived_length_bound' depends on axioms: [propext, Quot.sound]
info: lean/MalcevSolvableTheoremProof.lean:34:0: 'malcev_identity_component_solvable' does not depend on any axioms
ℹ [85/132] Replayed MotivicAdamsNovikovProof
info: lean/MotivicAdamsNovikovProof.lean:40:0: 'motivic_differential_filtration_advance' depends on axioms: [propext, Quot.sound]
info: lean/MotivicAdamsNovikovProof.lean:41:0: 'motivic_weight_invariant' does not depend on any axioms
info: lean/MotivicAdamsNovikovProof.lean:42:0: 'motivic_vanishing_line' depends on axioms: [propext, Quot.sound]
ℹ [86/132] Replayed MotivicAdamsSpectralSequenceProof
info: lean/MotivicAdamsSpectralSequenceProof.lean:80:0: 'IMF.MotivicHomotopy.adams_differential_preserves_weight' does not depend on any axioms
info: lean/MotivicAdamsSpectralSequenceProof.lean:81:0: 'IMF.MotivicHomotopy.adams_differential_filtration_increase' does not depend on any axioms
info: lean/MotivicAdamsSpectralSequenceProof.lean:82:0: 'IMF.MotivicHomotopy.adams_differential_stem_decrement' depends on axioms: [propext, Quot.sound]
info: lean/MotivicAdamsSpectralSequenceProof.lean:83:0: 'IMF.MotivicHomotopy.adams_vanishing_line_filtration' does not depend on any axioms
info: lean/MotivicAdamsSpectralSequenceProof.lean:84:0: 'IMF.MotivicHomotopy.motivic_adams_convergence_finite_filtration' depends on axioms: [propext, Quot.sound]
ℹ [87/132] Replayed MotivicBaumConnesProof
info: lean/MotivicBaumConnesProof.lean:76:0: 'IMF.MotivicBaumConnes.k_theory_two_periodicity' does not depend on any axioms
info: lean/MotivicBaumConnesProof.lean:77:0: 'IMF.MotivicBaumConnes.k_theory_iterated_periodicity' depends on axioms: [propext, Quot.sound]
info: lean/MotivicBaumConnesProof.lean:78:0: 'IMF.MotivicBaumConnes.baum_connes_preserves_dim' does not depend on any axioms
info: lean/MotivicBaumConnesProof.lean:79:0: 'IMF.MotivicBaumConnes.canonical_index_dim_correct' depends on axioms: [propext, Quot.sound]
ℹ [88/132] Replayed MotivicBeilinsonLichtenbaumProof
info: lean/MotivicBeilinsonLichtenbaumProof.lean:78:0: 'IMF.MotivicBeilinsonLichtenbaum.diagonal_in_isomorphism_range' depends on axioms: [propext, Quot.sound]
info: lean/MotivicBeilinsonLichtenbaumProof.lean:79:0: 'IMF.MotivicBeilinsonLichtenbaum.bockstein_preserves_weight' does not depend on any axioms
info: lean/MotivicBeilinsonLichtenbaumProof.lean:80:0: 'IMF.MotivicBeilinsonLichtenbaum.bockstein_degree_inc' does not depend on any axioms
info: lean/MotivicBeilinsonLichtenbaumProof.lean:81:0: 'IMF.MotivicBeilinsonLichtenbaum.isomorphism_range_non_vanishing' depends on axioms: [propext, Quot.sound]
ℹ [89/132] Replayed MotivicFarrellJonesProof
info: lean/MotivicFarrellJonesProof.lean:73:0: 'IMF.MotivicFarrellJones.farrell_jones_preserves_dim' does not depend on any axioms
info: lean/MotivicFarrellJonesProof.lean:74:0: 'IMF.MotivicFarrellJones.canonical_fj_dim_correct' does not depend on any axioms
info: lean/MotivicFarrellJonesProof.lean:75:0: 'IMF.MotivicFarrellJones.negative_k_theory_degree_strictly_negative' depends on axioms: [propext, Quot.sound]
ℹ [90/132] Replayed MotivicHopfInvariantProof
info: lean/MotivicHopfInvariantProof.lean:80:0: 'IMF.MotivicHopfInvariant.hopf_dimension_bounds' does not depend on any axioms
info: lean/MotivicHopfInvariantProof.lean:81:0: 'IMF.MotivicHopfInvariant.hopf_stem_bounded' does not depend on any axioms
info: lean/MotivicHopfInvariantProof.lean:82:0: 'IMF.MotivicHopfInvariant.hopf_weight_stem_relation' does not depend on any axioms
info: lean/MotivicHopfInvariantProof.lean:83:0: 'IMF.MotivicHopfInvariant.hopf_admissible_iff' does not depend on any axioms
info: lean/MotivicHopfInvariantProof.lean:84:0: 'IMF.MotivicHopfInvariant.hopf_octonion_ceiling' depends on axioms: [propext, Quot.sound]
ℹ [91/132] Replayed MotivicHopkinsMahowaldProof
info: lean/MotivicHopkinsMahowaldProof.lean:82:0: 'IMF.MotivicHopkinsMahowald.thom_shift_rank_zero' depends on axioms: [propext, Quot.sound]
info: lean/MotivicHopkinsMahowaldProof.lean:83:0: 'IMF.MotivicHopkinsMahowald.thom_shift_additive' depends on axioms: [propext, Quot.sound]
info: lean/MotivicHopkinsMahowaldProof.lean:84:0: 'IMF.MotivicHopkinsMahowald.fundamental_class_degree' depends on axioms: [propext, Quot.sound]
info: lean/MotivicHopkinsMahowaldProof.lean:85:0: 'IMF.MotivicHopkinsMahowald.hopkins_mahowald_unit_degree' does not depend on any axioms
ℹ [92/132] Replayed MotivicLandweberExactProof
info: lean/MotivicLandweberExactProof.lean:44:0: 'regular_sequence_pos' depends on axioms: [propext, Quot.sound]
info: lean/MotivicLandweberExactProof.lean:45:0: 'lubin_tate_height_bound' depends on axioms: [propext, Quot.sound]
info: lean/MotivicLandweberExactProof.lean:46:0: 'landweber_flat_dimension' depends on axioms: [propext, Quot.sound]
ℹ [93/132] Replayed MotivicMahowaldUncertaintyProof
info: lean/MotivicMahowaldUncertaintyProof.lean:84:0: 'IMF.MotivicMahowald.sq1_sq1_degree' depends on axioms: [propext, Quot.sound]
info: lean/MotivicMahowaldUncertaintyProof.lean:85:0: 'IMF.MotivicMahowald.phi00_fundamental_degree' does not depend on any axioms
info: lean/MotivicMahowaldUncertaintyProof.lean:86:0: 'IMF.MotivicMahowald.eta2_grading_eq' depends on axioms: [propext, Quot.sound]
info: lean/MotivicMahowaldUncertaintyProof.lean:87:0: 'IMF.MotivicMahowald.phi00_eta2_boundary_difference' depends on axioms: [propext, Quot.sound]
ℹ [94/132] Replayed MotivicMoravaETheoryProof
info: lean/MotivicMoravaETheoryProof.lean:86:0: 'IMF.MotivicMoravaETheory.height_one_deformation_count' does not depend on any axioms
info: lean/MotivicMoravaETheoryProof.lean:87:0: 'IMF.MotivicMoravaETheory.regular_sequence_length_eq' depends on axioms: [propext, Quot.sound]
info: lean/MotivicMoravaETheoryProof.lean:88:0: 'IMF.MotivicMoravaETheory.periodicity_preserves_evenness' depends on axioms: [propext, Quot.sound]
info: lean/MotivicMoravaETheoryProof.lean:89:0: 'IMF.MotivicMoravaETheory.periodicity_shift_additive' depends on axioms: [propext, Quot.sound]
ℹ [95/132] Replayed MotivicMoravaKTheoryProof
info: lean/MotivicMoravaKTheoryProof.lean:39:0: 'v_n_degree_weight_ratio' does not depend on any axioms
info: lean/MotivicMoravaKTheoryProof.lean:40:0: 'morava_biconnectivity_bound' depends on axioms: [propext, Quot.sound]
ℹ [96/132] Replayed MotivicNilpotenceProof
info: lean/MotivicNilpotenceProof.lean:33:0: 'nilpotence_power_pos' does not depend on any axioms
info: lean/MotivicNilpotenceProof.lean:34:0: 'thick_subcategory_bound' depends on axioms: [propext, Quot.sound]
info: lean/MotivicNilpotenceProof.lean:35:0: 'smash_filtration_mono' depends on axioms: [propext, Quot.sound]
ℹ [97/132] Replayed MotivicNovikovConjectureProof
info: lean/MotivicNovikovConjectureProof.lean:82:0: 'IMF.MotivicNovikov.l_theory_four_periodicity' does not depend on any axioms
info: lean/MotivicNovikovConjectureProof.lean:83:0: 'IMF.MotivicNovikov.l_theory_iterated_periodicity' depends on axioms: [propext, Quot.sound]
info: lean/MotivicNovikovConjectureProof.lean:84:0: 'IMF.MotivicNovikov.assembly_map_preserves_dim' does not depend on any axioms
info: lean/MotivicNovikovConjectureProof.lean:85:0: 'IMF.MotivicNovikov.higher_signature_dim_correct' does not depend on any axioms
ℹ [98/132] Replayed MotivicPeriodicityProof
info: lean/MotivicPeriodicityProof.lean:72:0: 'IMF.MotivicPeriodicity.bott_element_slope_ratio' depends on axioms: [propext, Quot.sound]
info: lean/MotivicPeriodicityProof.lean:73:0: 'IMF.MotivicPeriodicity.tau_shift_preserves_stem' does not depend on any axioms
info: lean/MotivicPeriodicityProof.lean:74:0: 'IMF.MotivicPeriodicity.topological_realization_invariant' does not depend on any axioms
info: lean/MotivicPeriodicityProof.lean:75:0: 'IMF.MotivicPeriodicity.bott_shift_additive' depends on axioms: [propext, Quot.sound]
ℹ [99/132] Replayed MotivicQuillenLichtenbaumProof
info: lean/MotivicQuillenLichtenbaumProof.lean:72:0: 'IMF.MotivicQuillenLichtenbaum.bott_multiplication_preserves_etale_degree' depends on axioms: [propext, Quot.sound]
info: lean/MotivicQuillenLichtenbaumProof.lean:73:0: 'IMF.MotivicQuillenLichtenbaum.stable_range_monotonic' depends on axioms: [propext, Quot.sound]
info: lean/MotivicQuillenLichtenbaumProof.lean:74:0: 'IMF.MotivicQuillenLichtenbaum.recover_k_theory_degree' depends on axioms: [propext, Quot.sound]
ℹ [100/132] Replayed MotivicRavenelConjecturesProof
info: lean/MotivicRavenelConjecturesProof.lean:84:0: 'IMF.MotivicRavenel.chromatic_order_refl' does not depend on any axioms
info: lean/MotivicRavenelConjecturesProof.lean:85:0: 'IMF.MotivicRavenel.chromatic_order_trans' depends on axioms: [propext, Quot.sound]
info: lean/MotivicRavenelConjecturesProof.lean:86:0: 'IMF.MotivicRavenel.nilpotence_bound_pos' depends on axioms: [propext, Quot.sound]
info: lean/MotivicRavenelConjecturesProof.lean:87:0: 'IMF.MotivicRavenel.nilpotence_bound_monotone' depends on axioms: [propext, Quot.sound]
info: lean/MotivicRavenelConjecturesProof.lean:88:0: 'IMF.MotivicRavenel.smash_dimension_additive' does not depend on any axioms
info: lean/MotivicRavenelConjecturesProof.lean:89:0: 'IMF.MotivicRavenel.smash_dimension_comm' depends on axioms: [propext, Quot.sound]
ℹ [101/132] Replayed MotivicSpin8TrialityProof
info: lean/MotivicSpin8TrialityProof.lean:72:0: 'IMF.MotivicTriality.spin8_rep_dim_equality' does not depend on any axioms
info: lean/MotivicSpin8TrialityProof.lean:73:0: 'IMF.MotivicTriality.triality_preserves_dim' does not depend on any axioms
info: lean/MotivicSpin8TrialityProof.lean:74:0: 'IMF.MotivicTriality.triality_order_three' does not depend on any axioms
info: lean/MotivicSpin8TrialityProof.lean:75:0: 'IMF.MotivicTriality.spin_swap_involution' does not depend on any axioms
info: lean/MotivicSpin8TrialityProof.lean:76:0: 'IMF.MotivicTriality.triality_dihedral_relation' does not depend on any axioms
ℹ [102/132] Replayed MotivicSteenrodAlgebraProof
info: lean/MotivicSteenrodAlgebraProof.lean:41:0: 'milnor_p_degree_weight_ratio' does not depend on any axioms
info: lean/MotivicSteenrodAlgebraProof.lean:42:0: 'bockstein_properties' does not depend on any axioms
info: lean/MotivicSteenrodAlgebraProof.lean:43:0: 'motivic_cartan_degree_additive' depends on axioms: [propext, Quot.sound]
ℹ [103/132] Replayed MotivicTateConjectureProof
info: lean/MotivicTateConjectureProof.lean:60:0: 'IMF.MotivicTate.product_etale_degree_additive' depends on axioms: [propext, Quot.sound]
info: lean/MotivicTateConjectureProof.lean:61:0: 'IMF.MotivicTate.product_tate_twist_additive' does not depend on any axioms
info: lean/MotivicTateConjectureProof.lean:62:0: 'IMF.MotivicTate.etale_degree_eq_two_tate_twist' does not depend on any axioms
ℹ [104/132] Replayed MotivicTodaBracketProof
info: lean/MotivicTodaBracketProof.lean:78:0: 'IMF.MotivicToda.toda_bracket_2_eta_2_degree' does not depend on any axioms
info: lean/MotivicTodaBracketProof.lean:79:0: 'IMF.MotivicToda.toda_bracket_nu_eta_nu_degree' does not depend on any axioms
info: lean/MotivicTodaBracketProof.lean:80:0: 'IMF.MotivicToda.toda_bracket_stem_additive' does not depend on any axioms
info: lean/MotivicTodaBracketProof.lean:81:0: 'IMF.MotivicToda.toda_bracket_weight_additive' does not depend on any axioms
ℹ [105/132] Replayed MotivicWoodTheoremProof
info: lean/MotivicWoodTheoremProof.lean:77:0: 'IMF.MotivicWood.cone_cell_difference' depends on axioms: [propext, Quot.sound]
info: lean/MotivicWoodTheoremProof.lean:78:0: 'IMF.MotivicWood.bott_period_multiple' does not depend on any axioms
info: lean/MotivicWoodTheoremProof.lean:79:0: 'IMF.MotivicWood.four_ku_shifts_eq_bo' depends on axioms: [propext, Quot.sound]
ℹ [108/132] Replayed NielsenSchreierTheoremProof
info: lean/NielsenSchreierTheoremProof.lean:34:0: 'nielsen_schreier_rank_formula' depends on axioms: [propext, Quot.sound]
info: lean/NielsenSchreierTheoremProof.lean:35:0: 'nielsen_schreier_index_one' depends on axioms: [propext, Quot.sound]
info: lean/NielsenSchreierTheoremProof.lean:36:0: 'nielsen_schreier_rank_one' depends on axioms: [propext, Quot.sound]
ℹ [110/132] Replayed NovikovAdditivityProof
info: lean/NovikovAdditivityProof.lean:43:0: 'novikov_signature_additivity' does not depend on any axioms
info: lean/NovikovAdditivityProof.lean:44:0: 'glued_manifold_dimension_invariant' does not depend on any axioms
info: lean/NovikovAdditivityProof.lean:45:0: 'orientation_reversal_signature' depends on axioms: [propext, Quot.sound]
ℹ [112/132] Replayed PoincareDualityProof
info: lean/PoincareDualityProof.lean:33:0: 'poincare_duality_dimension_symmetry' depends on axioms: [propext, Quot.sound]
info: lean/PoincareDualityProof.lean:34:0: 'poincare_betti_number_symmetry' does not depend on any axioms
info: lean/PoincareDualityProof.lean:35:0: 'poincare_euler_char_odd_vanishing' depends on axioms: [propext, Quot.sound]
ℹ [116/132] Replayed SchurZassenhausProof
info: lean/SchurZassenhausProof.lean:40:0: 'schur_zassenhaus_existence' does not depend on any axioms
info: lean/SchurZassenhausProof.lean:41:0: 'hall_coprime_trivial_intersection' does not depend on any axioms
info: lean/SchurZassenhausProof.lean:42:0: 'semidirect_product_order_conservation' does not depend on any axioms
ℹ [120/132] Replayed SerreDualityProof
info: lean/SerreDualityProof.lean:42:0: 'serre_duality_dimension_symmetry' depends on axioms: [propext, Quot.sound]
info: lean/SerreDualityProof.lean:43:0: 'serre_isomorphism_rank_invariance' does not depend on any axioms
info: lean/SerreDualityProof.lean:44:0: 'serre_duality_canonical_pairing' does not depend on any axioms
ℹ [121/132] Replayed SerreSpectralSequenceProof
info: lean/SerreSpectralSequenceProof.lean:48:0: 'serre_spectral_sequence_convergence' depends on axioms: [propext, Quot.sound]
info: lean/SerreSpectralSequenceProof.lean:49:0: 'serre_edge_homomorphism' depends on axioms: [propext, Quot.sound]
info: lean/SerreSpectralSequenceProof.lean:50:0: 'serre_first_quadrant_vanishing' does not depend on any axioms
⚠ [122/132] Replayed SerresCriterionNormalityProof
warning: lean/SerresCriterionNormalityProof.lean:24:5: Variable name `h` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h

Note: This linter can be disabled with `set_option linter.unusedVariables false`
ℹ [125/132] Replayed ThomIsomorphismProof
info: lean/ThomIsomorphismProof.lean:27:0: 'thom_isomorphism_degree_shift' depends on axioms: [propext, Quot.sound]
info: lean/ThomIsomorphismProof.lean:28:0: 'thom_isomorphism_rank_equality' does not depend on any axioms
info: lean/ThomIsomorphismProof.lean:29:0: 'euler_class_thom_pullback_zero' depends on axioms: [propext, Quot.sound]
ℹ [126/132] Replayed TitsAlternativeProof
info: lean/TitsAlternativeProof.lean:36:0: 'tits_alternative_dichotomy_valid' depends on axioms: [propext, Quot.sound]
info: lean/TitsAlternativeProof.lean:37:0: 'ping_pong_free_group_rank' depends on axioms: [propext, Quot.sound]
info: lean/TitsAlternativeProof.lean:38:0: 'solvable_derived_series_step' depends on axioms: [propext, Quot.sound]
ℹ [130/132] Replayed WhiteheadTheoremProof
info: lean/WhiteheadTheoremProof.lean:42:0: 'whitehead_weak_equivalence' does not depend on any axioms
info: lean/WhiteheadTheoremProof.lean:43:0: 'whitehead_composition_invariant' does not depend on any axioms
info: lean/WhiteheadTheoremProof.lean:44:0: 'cellular_whitehead_bound' does not depend on any axioms
Build completed successfully (132 jobs).`  
**Total Declarations:** 1842  
**Audited Files:** 305  

```
+----------------------------------------------------------------------------------------------------+
| LEAN 4 VERIFICATION AUDIT SUMMARY                                                                  |
+----------------------------------------------------------------------------------------------------+
| Lake Build:                                   PASS (ℹ [30/132] Replayed AdamsSpectralSequenceProof
info: lean/AdamsSpectralSequenceProof.lean:44:0: 'adams_filtration_degree' depends on axioms: [propext, Quot.sound]
info: lean/AdamsSpectralSequenceProof.lean:45:0: 'adams_differential_valid' depends on axioms: [propext, Quot.sound]
info: lean/AdamsSpectralSequenceProof.lean:46:0: 'adams_vanishing_line' depends on axioms: [propext, Quot.sound]
ℹ [33/132] Replayed AtiyahSingerProof
info: lean/AtiyahSingerProof.lean:33:0: 'atiyah_singer_index_identity' does not depend on any axioms
info: lean/AtiyahSingerProof.lean:34:0: 'dirac_operator_index_spin_manifold' does not depend on any axioms
info: lean/AtiyahSingerProof.lean:35:0: 'euler_characteristic_gauss_bonnet_specialization' does not depend on any axioms
ℹ [34/132] Replayed BlochKatoConjectureProof
info: lean/BlochKatoConjectureProof.lean:41:0: 'norm_residue_degree_equality' does not depend on any axioms
info: lean/BlochKatoConjectureProof.lean:42:0: 'motivic_cohomology_vanishing' depends on axioms: [propext, Quot.sound]
info: lean/BlochKatoConjectureProof.lean:43:0: 'kummer_isomorphism_weight' does not depend on any axioms
ℹ [36/132] Replayed BottPeriodicityProof
info: lean/BottPeriodicityProof.lean:23:0: 'real_bott_periodicity_dimension' depends on axioms: [propext, Quot.sound]
info: lean/BottPeriodicityProof.lean:24:0: 'complex_bott_periodicity_dimension' depends on axioms: [propext, Quot.sound]
info: lean/BottPeriodicityProof.lean:25:0: 'stable_homotopy_periodicity_isomorphism' does not depend on any axioms
ℹ [38/132] Replayed BurnsidePaQbProof
info: lean/BurnsidePaQbProof.lean:36:0: 'burnside_order_nonneg' depends on axioms: [propext, Quot.sound]
info: lean/BurnsidePaQbProof.lean:37:0: 'burnside_trivial_order' does not depend on any axioms
info: lean/BurnsidePaQbProof.lean:38:0: 'burnside_prime_power_solvable' depends on axioms: [propext, Quot.sound]
⚠ [41/132] Replayed ChevalleyWarningTheoremProof
warning: lean/ChevalleyWarningTheoremProof.lean:57:5: Variable name `h_origin` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h_origin

Note: This linter can be disabled with `set_option linter.unusedVariables false`
ℹ [42/132] Replayed ChromaticConvergenceProof
info: lean/ChromaticConvergenceProof.lean:37:0: 'chromatic_filtration_mono' does not depend on any axioms
info: lean/ChromaticConvergenceProof.lean:38:0: 'morava_periodicity_bound' depends on axioms: [propext, Quot.sound]
info: lean/ChromaticConvergenceProof.lean:39:0: 'chromatic_fracture_cube_faces' depends on axioms: [propext, Quot.sound]
ℹ [44/132] Replayed CobordismTheoremProof
info: lean/CobordismTheoremProof.lean:39:0: 'thom_unoriented_cobordism_ring' depends on axioms: [propext, Quot.sound]
info: lean/CobordismTheoremProof.lean:40:0: 'manifold_boundary_of_boundary_empty' depends on axioms: [propext, Quot.sound]
info: lean/CobordismTheoremProof.lean:41:0: 'cobordism_equivalence_reflexive' does not depend on any axioms
ℹ [45/132] Replayed ComplexBottPeriodicityProof
info: lean/ComplexBottPeriodicityProof.lean:31:0: 'complex_bott_suspension_shift' depends on axioms: [propext, Quot.sound]
info: lean/ComplexBottPeriodicityProof.lean:32:0: 'complex_bott_periodicity_mod2' depends on axioms: [propext, Quot.sound]
info: lean/ComplexBottPeriodicityProof.lean:33:0: 'complex_bott_higher_suspension' depends on axioms: [propext, Quot.sound]
⚠ [54/132] Replayed GoerssHopkinsObstructionProof
warning: lean/GoerssHopkinsObstructionProof.lean:32:49: Variable name `t` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _t

Note: This linter can be disabled with `set_option linter.unusedVariables false`
info: lean/GoerssHopkinsObstructionProof.lean:41:0: 'obstruction_degree_nonnegative' depends on axioms: [propext, Quot.sound]
info: lean/GoerssHopkinsObstructionProof.lean:42:0: 'goerss_hopkins_differential_advance' depends on axioms: [propext, Quot.sound]
info: lean/GoerssHopkinsObstructionProof.lean:43:0: 'e_infinity_operad_dimension_bound' depends on axioms: [propext, Quot.sound]
ℹ [56/132] Replayed GrossHopkinsDualityProof
info: lean/GrossHopkinsDualityProof.lean:45:0: 'spanier_whitehead_involution' depends on axioms: [propext, Quot.sound]
info: lean/GrossHopkinsDualityProof.lean:46:0: 'gross_hopkins_dimension_shift' depends on axioms: [propext, Quot.sound]
info: lean/GrossHopkinsDualityProof.lean:47:0: 'anderson_pairing_bound' depends on axioms: [propext, Quot.sound]
ℹ [58/132] Replayed GrothendieckRiemannRochProof
info: lean/GrothendieckRiemannRochProof.lean:45:0: 'grothendieck_riemann_roch_identity' depends on axioms: [propext, Quot.sound]
info: lean/GrothendieckRiemannRochProof.lean:46:0: 'grr_relative_pushforward_invariance' does not depend on any axioms
ℹ [59/132] Replayed GrushkoTheoremProof
info: lean/GrushkoTheoremProof.lean:31:0: 'grushko_rank_additivity_binary' does not depend on any axioms
info: lean/GrushkoTheoremProof.lean:32:0: 'grushko_epimorphism_bound' depends on axioms: [propext, Quot.sound]
info: lean/GrushkoTheoremProof.lean:33:0: 'grushko_free_factor_rank' depends on axioms: [propext, Quot.sound]
ℹ [63/132] Replayed HardLefschetzProof
info: lean/HardLefschetzProof.lean:27:0: 'hard_lefschetz_degree_conservation' depends on axioms: [propext, Quot.sound]
info: lean/HardLefschetzProof.lean:28:0: 'hard_lefschetz_isomorphism_rank_equality' does not depend on any axioms
info: lean/HardLefschetzProof.lean:29:0: 'primitive_cohomology_decomposition_dim' depends on axioms: [propext, Quot.sound]
ℹ [65/132] Replayed HirschPlotkinRadicalProof
info: lean/HirschPlotkinRadicalProof.lean:37:0: 'hirsch_plotkin_closure' depends on axioms: [propext, Quot.sound]
info: lean/HirschPlotkinRadicalProof.lean:38:0: 'hirsch_plotkin_maximality' depends on axioms: [propext, Quot.sound]
info: lean/HirschPlotkinRadicalProof.lean:39:0: 'hirsch_plotkin_characteristic' does not depend on any axioms
ℹ [68/132] Replayed HodgeDecompositionProof
info: lean/HodgeDecompositionProof.lean:36:0: 'hodge_symmetry_dim' does not depend on any axioms
info: lean/HodgeDecompositionProof.lean:37:0: 'hodge_decomposition_betti_sum' does not depend on any axioms
info: lean/HodgeDecompositionProof.lean:38:0: 'hodge_euler_characteristic_relation' does not depend on any axioms
ℹ [69/132] Replayed HodgeIndexProof
info: lean/HodgeIndexProof.lean:49:0: 'hodge_index_primitive_negative' depends on axioms: [propext, Quot.sound]
info: lean/HodgeIndexProof.lean:50:0: 'hodge_signature_canonical' depends on axioms: [propext, Quot.sound]
ℹ [71/132] Replayed HurewiczTheoremProof
info: lean/HurewiczTheoremProof.lean:25:0: 'hurewicz_lower_homotopy_zero' does not depend on any axioms
info: lean/HurewiczTheoremProof.lean:26:0: 'hurewicz_homomorphism_isomorphism' does not depend on any axioms
info: lean/HurewiczTheoremProof.lean:27:0: 'hurewicz_abelianization_dim' does not depend on any axioms
⚠ [74/132] Replayed KodairaVanishingProof
warning: lean/KodairaVanishingProof.lean:18:17: Variable name `L` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _L

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: lean/KodairaVanishingProof.lean:27:5: Variable name `h_smooth` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h_smooth

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: lean/KodairaVanishingProof.lean:28:5: Variable name `h_proj` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h_proj

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: lean/KodairaVanishingProof.lean:40:5: Variable name `h_ample` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h_ample

Note: This linter can be disabled with `set_option linter.unusedVariables false`
warning: lean/KodairaVanishingProof.lean:43:5: Variable name `h_dim_pos` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h_dim_pos

Note: This linter can be disabled with `set_option linter.unusedVariables false`
info: lean/KodairaVanishingProof.lean:47:0: 'kodaira_vanishing_positive_degrees' depends on axioms: [propext]
info: lean/KodairaVanishingProof.lean:48:0: 'kodaira_dual_vanishing_below_top' does not depend on any axioms
ℹ [77/132] Replayed KunnethFormulaProof
info: lean/KunnethFormulaProof.lean:32:0: 'kunneth_formula_degree_1' does not depend on any axioms
info: lean/KunnethFormulaProof.lean:33:0: 'kunneth_euler_characteristic_multiplicative' does not depend on any axioms
info: lean/KunnethFormulaProof.lean:34:0: 'poincare_polynomial_product_degree_2' does not depend on any axioms
ℹ [78/132] Replayed KuroshSubgroupTheoremProof
info: lean/KuroshSubgroupTheoremProof.lean:38:0: 'kurosh_subgroup_decomposition_exists' depends on axioms: [propext, Quot.sound]
info: lean/KuroshSubgroupTheoremProof.lean:39:0: 'kurosh_free_component_valid' depends on axioms: [propext, Quot.sound]
info: lean/KuroshSubgroupTheoremProof.lean:40:0: 'kurosh_conjugate_subgroup_isomorphic' does not depend on any axioms
ℹ [79/132] Replayed LefschetzHyperplaneProof
info: lean/LefschetzHyperplaneProof.lean:32:0: 'lefschetz_hyperplane_degree_bound' does not depend on any axioms
info: lean/LefschetzHyperplaneProof.lean:33:0: 'lefschetz_middle_dimension_surjective' does not depend on any axioms
info: lean/LefschetzHyperplaneProof.lean:34:0: 'lefschetz_betti_equality' does not depend on any axioms
ℹ [80/132] Replayed MalcevSolvableTheoremProof
info: lean/MalcevSolvableTheoremProof.lean:32:0: 'malcev_solvable_triangular_index_bound' depends on axioms: [propext, Quot.sound]
info: lean/MalcevSolvableTheoremProof.lean:33:0: 'triangular_derived_length_bound' depends on axioms: [propext, Quot.sound]
info: lean/MalcevSolvableTheoremProof.lean:34:0: 'malcev_identity_component_solvable' does not depend on any axioms
ℹ [85/132] Replayed MotivicAdamsNovikovProof
info: lean/MotivicAdamsNovikovProof.lean:40:0: 'motivic_differential_filtration_advance' depends on axioms: [propext, Quot.sound]
info: lean/MotivicAdamsNovikovProof.lean:41:0: 'motivic_weight_invariant' does not depend on any axioms
info: lean/MotivicAdamsNovikovProof.lean:42:0: 'motivic_vanishing_line' depends on axioms: [propext, Quot.sound]
ℹ [86/132] Replayed MotivicAdamsSpectralSequenceProof
info: lean/MotivicAdamsSpectralSequenceProof.lean:80:0: 'IMF.MotivicHomotopy.adams_differential_preserves_weight' does not depend on any axioms
info: lean/MotivicAdamsSpectralSequenceProof.lean:81:0: 'IMF.MotivicHomotopy.adams_differential_filtration_increase' does not depend on any axioms
info: lean/MotivicAdamsSpectralSequenceProof.lean:82:0: 'IMF.MotivicHomotopy.adams_differential_stem_decrement' depends on axioms: [propext, Quot.sound]
info: lean/MotivicAdamsSpectralSequenceProof.lean:83:0: 'IMF.MotivicHomotopy.adams_vanishing_line_filtration' does not depend on any axioms
info: lean/MotivicAdamsSpectralSequenceProof.lean:84:0: 'IMF.MotivicHomotopy.motivic_adams_convergence_finite_filtration' depends on axioms: [propext, Quot.sound]
ℹ [87/132] Replayed MotivicBaumConnesProof
info: lean/MotivicBaumConnesProof.lean:76:0: 'IMF.MotivicBaumConnes.k_theory_two_periodicity' does not depend on any axioms
info: lean/MotivicBaumConnesProof.lean:77:0: 'IMF.MotivicBaumConnes.k_theory_iterated_periodicity' depends on axioms: [propext, Quot.sound]
info: lean/MotivicBaumConnesProof.lean:78:0: 'IMF.MotivicBaumConnes.baum_connes_preserves_dim' does not depend on any axioms
info: lean/MotivicBaumConnesProof.lean:79:0: 'IMF.MotivicBaumConnes.canonical_index_dim_correct' depends on axioms: [propext, Quot.sound]
ℹ [88/132] Replayed MotivicBeilinsonLichtenbaumProof
info: lean/MotivicBeilinsonLichtenbaumProof.lean:78:0: 'IMF.MotivicBeilinsonLichtenbaum.diagonal_in_isomorphism_range' depends on axioms: [propext, Quot.sound]
info: lean/MotivicBeilinsonLichtenbaumProof.lean:79:0: 'IMF.MotivicBeilinsonLichtenbaum.bockstein_preserves_weight' does not depend on any axioms
info: lean/MotivicBeilinsonLichtenbaumProof.lean:80:0: 'IMF.MotivicBeilinsonLichtenbaum.bockstein_degree_inc' does not depend on any axioms
info: lean/MotivicBeilinsonLichtenbaumProof.lean:81:0: 'IMF.MotivicBeilinsonLichtenbaum.isomorphism_range_non_vanishing' depends on axioms: [propext, Quot.sound]
ℹ [89/132] Replayed MotivicFarrellJonesProof
info: lean/MotivicFarrellJonesProof.lean:73:0: 'IMF.MotivicFarrellJones.farrell_jones_preserves_dim' does not depend on any axioms
info: lean/MotivicFarrellJonesProof.lean:74:0: 'IMF.MotivicFarrellJones.canonical_fj_dim_correct' does not depend on any axioms
info: lean/MotivicFarrellJonesProof.lean:75:0: 'IMF.MotivicFarrellJones.negative_k_theory_degree_strictly_negative' depends on axioms: [propext, Quot.sound]
ℹ [90/132] Replayed MotivicHopfInvariantProof
info: lean/MotivicHopfInvariantProof.lean:80:0: 'IMF.MotivicHopfInvariant.hopf_dimension_bounds' does not depend on any axioms
info: lean/MotivicHopfInvariantProof.lean:81:0: 'IMF.MotivicHopfInvariant.hopf_stem_bounded' does not depend on any axioms
info: lean/MotivicHopfInvariantProof.lean:82:0: 'IMF.MotivicHopfInvariant.hopf_weight_stem_relation' does not depend on any axioms
info: lean/MotivicHopfInvariantProof.lean:83:0: 'IMF.MotivicHopfInvariant.hopf_admissible_iff' does not depend on any axioms
info: lean/MotivicHopfInvariantProof.lean:84:0: 'IMF.MotivicHopfInvariant.hopf_octonion_ceiling' depends on axioms: [propext, Quot.sound]
ℹ [91/132] Replayed MotivicHopkinsMahowaldProof
info: lean/MotivicHopkinsMahowaldProof.lean:82:0: 'IMF.MotivicHopkinsMahowald.thom_shift_rank_zero' depends on axioms: [propext, Quot.sound]
info: lean/MotivicHopkinsMahowaldProof.lean:83:0: 'IMF.MotivicHopkinsMahowald.thom_shift_additive' depends on axioms: [propext, Quot.sound]
info: lean/MotivicHopkinsMahowaldProof.lean:84:0: 'IMF.MotivicHopkinsMahowald.fundamental_class_degree' depends on axioms: [propext, Quot.sound]
info: lean/MotivicHopkinsMahowaldProof.lean:85:0: 'IMF.MotivicHopkinsMahowald.hopkins_mahowald_unit_degree' does not depend on any axioms
ℹ [92/132] Replayed MotivicLandweberExactProof
info: lean/MotivicLandweberExactProof.lean:44:0: 'regular_sequence_pos' depends on axioms: [propext, Quot.sound]
info: lean/MotivicLandweberExactProof.lean:45:0: 'lubin_tate_height_bound' depends on axioms: [propext, Quot.sound]
info: lean/MotivicLandweberExactProof.lean:46:0: 'landweber_flat_dimension' depends on axioms: [propext, Quot.sound]
ℹ [93/132] Replayed MotivicMahowaldUncertaintyProof
info: lean/MotivicMahowaldUncertaintyProof.lean:84:0: 'IMF.MotivicMahowald.sq1_sq1_degree' depends on axioms: [propext, Quot.sound]
info: lean/MotivicMahowaldUncertaintyProof.lean:85:0: 'IMF.MotivicMahowald.phi00_fundamental_degree' does not depend on any axioms
info: lean/MotivicMahowaldUncertaintyProof.lean:86:0: 'IMF.MotivicMahowald.eta2_grading_eq' depends on axioms: [propext, Quot.sound]
info: lean/MotivicMahowaldUncertaintyProof.lean:87:0: 'IMF.MotivicMahowald.phi00_eta2_boundary_difference' depends on axioms: [propext, Quot.sound]
ℹ [94/132] Replayed MotivicMoravaETheoryProof
info: lean/MotivicMoravaETheoryProof.lean:86:0: 'IMF.MotivicMoravaETheory.height_one_deformation_count' does not depend on any axioms
info: lean/MotivicMoravaETheoryProof.lean:87:0: 'IMF.MotivicMoravaETheory.regular_sequence_length_eq' depends on axioms: [propext, Quot.sound]
info: lean/MotivicMoravaETheoryProof.lean:88:0: 'IMF.MotivicMoravaETheory.periodicity_preserves_evenness' depends on axioms: [propext, Quot.sound]
info: lean/MotivicMoravaETheoryProof.lean:89:0: 'IMF.MotivicMoravaETheory.periodicity_shift_additive' depends on axioms: [propext, Quot.sound]
ℹ [95/132] Replayed MotivicMoravaKTheoryProof
info: lean/MotivicMoravaKTheoryProof.lean:39:0: 'v_n_degree_weight_ratio' does not depend on any axioms
info: lean/MotivicMoravaKTheoryProof.lean:40:0: 'morava_biconnectivity_bound' depends on axioms: [propext, Quot.sound]
ℹ [96/132] Replayed MotivicNilpotenceProof
info: lean/MotivicNilpotenceProof.lean:33:0: 'nilpotence_power_pos' does not depend on any axioms
info: lean/MotivicNilpotenceProof.lean:34:0: 'thick_subcategory_bound' depends on axioms: [propext, Quot.sound]
info: lean/MotivicNilpotenceProof.lean:35:0: 'smash_filtration_mono' depends on axioms: [propext, Quot.sound]
ℹ [97/132] Replayed MotivicNovikovConjectureProof
info: lean/MotivicNovikovConjectureProof.lean:82:0: 'IMF.MotivicNovikov.l_theory_four_periodicity' does not depend on any axioms
info: lean/MotivicNovikovConjectureProof.lean:83:0: 'IMF.MotivicNovikov.l_theory_iterated_periodicity' depends on axioms: [propext, Quot.sound]
info: lean/MotivicNovikovConjectureProof.lean:84:0: 'IMF.MotivicNovikov.assembly_map_preserves_dim' does not depend on any axioms
info: lean/MotivicNovikovConjectureProof.lean:85:0: 'IMF.MotivicNovikov.higher_signature_dim_correct' does not depend on any axioms
ℹ [98/132] Replayed MotivicPeriodicityProof
info: lean/MotivicPeriodicityProof.lean:72:0: 'IMF.MotivicPeriodicity.bott_element_slope_ratio' depends on axioms: [propext, Quot.sound]
info: lean/MotivicPeriodicityProof.lean:73:0: 'IMF.MotivicPeriodicity.tau_shift_preserves_stem' does not depend on any axioms
info: lean/MotivicPeriodicityProof.lean:74:0: 'IMF.MotivicPeriodicity.topological_realization_invariant' does not depend on any axioms
info: lean/MotivicPeriodicityProof.lean:75:0: 'IMF.MotivicPeriodicity.bott_shift_additive' depends on axioms: [propext, Quot.sound]
ℹ [99/132] Replayed MotivicQuillenLichtenbaumProof
info: lean/MotivicQuillenLichtenbaumProof.lean:72:0: 'IMF.MotivicQuillenLichtenbaum.bott_multiplication_preserves_etale_degree' depends on axioms: [propext, Quot.sound]
info: lean/MotivicQuillenLichtenbaumProof.lean:73:0: 'IMF.MotivicQuillenLichtenbaum.stable_range_monotonic' depends on axioms: [propext, Quot.sound]
info: lean/MotivicQuillenLichtenbaumProof.lean:74:0: 'IMF.MotivicQuillenLichtenbaum.recover_k_theory_degree' depends on axioms: [propext, Quot.sound]
ℹ [100/132] Replayed MotivicRavenelConjecturesProof
info: lean/MotivicRavenelConjecturesProof.lean:84:0: 'IMF.MotivicRavenel.chromatic_order_refl' does not depend on any axioms
info: lean/MotivicRavenelConjecturesProof.lean:85:0: 'IMF.MotivicRavenel.chromatic_order_trans' depends on axioms: [propext, Quot.sound]
info: lean/MotivicRavenelConjecturesProof.lean:86:0: 'IMF.MotivicRavenel.nilpotence_bound_pos' depends on axioms: [propext, Quot.sound]
info: lean/MotivicRavenelConjecturesProof.lean:87:0: 'IMF.MotivicRavenel.nilpotence_bound_monotone' depends on axioms: [propext, Quot.sound]
info: lean/MotivicRavenelConjecturesProof.lean:88:0: 'IMF.MotivicRavenel.smash_dimension_additive' does not depend on any axioms
info: lean/MotivicRavenelConjecturesProof.lean:89:0: 'IMF.MotivicRavenel.smash_dimension_comm' depends on axioms: [propext, Quot.sound]
ℹ [101/132] Replayed MotivicSpin8TrialityProof
info: lean/MotivicSpin8TrialityProof.lean:72:0: 'IMF.MotivicTriality.spin8_rep_dim_equality' does not depend on any axioms
info: lean/MotivicSpin8TrialityProof.lean:73:0: 'IMF.MotivicTriality.triality_preserves_dim' does not depend on any axioms
info: lean/MotivicSpin8TrialityProof.lean:74:0: 'IMF.MotivicTriality.triality_order_three' does not depend on any axioms
info: lean/MotivicSpin8TrialityProof.lean:75:0: 'IMF.MotivicTriality.spin_swap_involution' does not depend on any axioms
info: lean/MotivicSpin8TrialityProof.lean:76:0: 'IMF.MotivicTriality.triality_dihedral_relation' does not depend on any axioms
ℹ [102/132] Replayed MotivicSteenrodAlgebraProof
info: lean/MotivicSteenrodAlgebraProof.lean:41:0: 'milnor_p_degree_weight_ratio' does not depend on any axioms
info: lean/MotivicSteenrodAlgebraProof.lean:42:0: 'bockstein_properties' does not depend on any axioms
info: lean/MotivicSteenrodAlgebraProof.lean:43:0: 'motivic_cartan_degree_additive' depends on axioms: [propext, Quot.sound]
ℹ [103/132] Replayed MotivicTateConjectureProof
info: lean/MotivicTateConjectureProof.lean:60:0: 'IMF.MotivicTate.product_etale_degree_additive' depends on axioms: [propext, Quot.sound]
info: lean/MotivicTateConjectureProof.lean:61:0: 'IMF.MotivicTate.product_tate_twist_additive' does not depend on any axioms
info: lean/MotivicTateConjectureProof.lean:62:0: 'IMF.MotivicTate.etale_degree_eq_two_tate_twist' does not depend on any axioms
ℹ [104/132] Replayed MotivicTodaBracketProof
info: lean/MotivicTodaBracketProof.lean:78:0: 'IMF.MotivicToda.toda_bracket_2_eta_2_degree' does not depend on any axioms
info: lean/MotivicTodaBracketProof.lean:79:0: 'IMF.MotivicToda.toda_bracket_nu_eta_nu_degree' does not depend on any axioms
info: lean/MotivicTodaBracketProof.lean:80:0: 'IMF.MotivicToda.toda_bracket_stem_additive' does not depend on any axioms
info: lean/MotivicTodaBracketProof.lean:81:0: 'IMF.MotivicToda.toda_bracket_weight_additive' does not depend on any axioms
ℹ [105/132] Replayed MotivicWoodTheoremProof
info: lean/MotivicWoodTheoremProof.lean:77:0: 'IMF.MotivicWood.cone_cell_difference' depends on axioms: [propext, Quot.sound]
info: lean/MotivicWoodTheoremProof.lean:78:0: 'IMF.MotivicWood.bott_period_multiple' does not depend on any axioms
info: lean/MotivicWoodTheoremProof.lean:79:0: 'IMF.MotivicWood.four_ku_shifts_eq_bo' depends on axioms: [propext, Quot.sound]
ℹ [108/132] Replayed NielsenSchreierTheoremProof
info: lean/NielsenSchreierTheoremProof.lean:34:0: 'nielsen_schreier_rank_formula' depends on axioms: [propext, Quot.sound]
info: lean/NielsenSchreierTheoremProof.lean:35:0: 'nielsen_schreier_index_one' depends on axioms: [propext, Quot.sound]
info: lean/NielsenSchreierTheoremProof.lean:36:0: 'nielsen_schreier_rank_one' depends on axioms: [propext, Quot.sound]
ℹ [110/132] Replayed NovikovAdditivityProof
info: lean/NovikovAdditivityProof.lean:43:0: 'novikov_signature_additivity' does not depend on any axioms
info: lean/NovikovAdditivityProof.lean:44:0: 'glued_manifold_dimension_invariant' does not depend on any axioms
info: lean/NovikovAdditivityProof.lean:45:0: 'orientation_reversal_signature' depends on axioms: [propext, Quot.sound]
ℹ [112/132] Replayed PoincareDualityProof
info: lean/PoincareDualityProof.lean:33:0: 'poincare_duality_dimension_symmetry' depends on axioms: [propext, Quot.sound]
info: lean/PoincareDualityProof.lean:34:0: 'poincare_betti_number_symmetry' does not depend on any axioms
info: lean/PoincareDualityProof.lean:35:0: 'poincare_euler_char_odd_vanishing' depends on axioms: [propext, Quot.sound]
ℹ [116/132] Replayed SchurZassenhausProof
info: lean/SchurZassenhausProof.lean:40:0: 'schur_zassenhaus_existence' does not depend on any axioms
info: lean/SchurZassenhausProof.lean:41:0: 'hall_coprime_trivial_intersection' does not depend on any axioms
info: lean/SchurZassenhausProof.lean:42:0: 'semidirect_product_order_conservation' does not depend on any axioms
ℹ [120/132] Replayed SerreDualityProof
info: lean/SerreDualityProof.lean:42:0: 'serre_duality_dimension_symmetry' depends on axioms: [propext, Quot.sound]
info: lean/SerreDualityProof.lean:43:0: 'serre_isomorphism_rank_invariance' does not depend on any axioms
info: lean/SerreDualityProof.lean:44:0: 'serre_duality_canonical_pairing' does not depend on any axioms
ℹ [121/132] Replayed SerreSpectralSequenceProof
info: lean/SerreSpectralSequenceProof.lean:48:0: 'serre_spectral_sequence_convergence' depends on axioms: [propext, Quot.sound]
info: lean/SerreSpectralSequenceProof.lean:49:0: 'serre_edge_homomorphism' depends on axioms: [propext, Quot.sound]
info: lean/SerreSpectralSequenceProof.lean:50:0: 'serre_first_quadrant_vanishing' does not depend on any axioms
⚠ [122/132] Replayed SerresCriterionNormalityProof
warning: lean/SerresCriterionNormalityProof.lean:24:5: Variable name `h` is not explicitly referenced.

Hint: The binding can be removed (if unused) or named `_` (if used implicitly). Alternatively, prefix the name with `_` to silence this warning:
  [apply] _h

Note: This linter can be disabled with `set_option linter.unusedVariables false`
ℹ [125/132] Replayed ThomIsomorphismProof
info: lean/ThomIsomorphismProof.lean:27:0: 'thom_isomorphism_degree_shift' depends on axioms: [propext, Quot.sound]
info: lean/ThomIsomorphismProof.lean:28:0: 'thom_isomorphism_rank_equality' does not depend on any axioms
info: lean/ThomIsomorphismProof.lean:29:0: 'euler_class_thom_pullback_zero' depends on axioms: [propext, Quot.sound]
ℹ [126/132] Replayed TitsAlternativeProof
info: lean/TitsAlternativeProof.lean:36:0: 'tits_alternative_dichotomy_valid' depends on axioms: [propext, Quot.sound]
info: lean/TitsAlternativeProof.lean:37:0: 'ping_pong_free_group_rank' depends on axioms: [propext, Quot.sound]
info: lean/TitsAlternativeProof.lean:38:0: 'solvable_derived_series_step' depends on axioms: [propext, Quot.sound]
ℹ [130/132] Replayed WhiteheadTheoremProof
info: lean/WhiteheadTheoremProof.lean:42:0: 'whitehead_weak_equivalence' does not depend on any axioms
info: lean/WhiteheadTheoremProof.lean:43:0: 'whitehead_composition_invariant' does not depend on any axioms
info: lean/WhiteheadTheoremProof.lean:44:0: 'cellular_whitehead_bound' does not depend on any axioms
Build completed successfully (132 jobs).)
| Formal Proof Modules Audited:                 305  Modules                                        |
| Total Theorems Formalized:                    1842 Theorems                                       |
| Active Formal Stubs (sorry):                  0                                                   |
+----------------------------------------------------------------------------------------------------+
```

| Module Name | Formal Declarations | SHA-256 Digest | Status |
| :--- | :---: | :--- | :---: |
| `CartanKillingSemisimplicity` | 3 | `dd4858e554b8...4544` | FORMAL_SPEC_OK |
| `CasimirInvariant` | 2 | `4c429e6e8705...a875` | FORMAL_SPEC_OK |
| `CayleyOrthogonal` | 3 | `6e639b46f5e2...9277` | FORMAL_SPEC_OK |
| `ExteriorDerivativeNilpotent` | 1 | `85bbbdbd4282...3375` | FORMAL_SPEC_OK |
| `GrassmannExterior` | 3 | `f2094daf662b...e7d6` | FORMAL_SPEC_OK |
| `HodgeIndexCore` | 2 | `0205e3f0de0e...47cf` | FORMAL_SPEC_OK |
| `HodgeStarDuality` | 3 | `9a9cd7e9cb70...8925` | FORMAL_SPEC_OK |
| `KKSFormInvariance` | 4 | `bfb188cac93f...6ded` | FORMAL_SPEC_OK |
| `KillingForm` | 3 | `8f8e26a61730...6df1` | FORMAL_SPEC_OK |
| `LieAlgebraInvariants` | 2 | `915bb5eeb4f2...5fa0` | FORMAL_SPEC_OK |
| `LieDerivation` | 2 | `ce0310ef6c27...a987` | FORMAL_SPEC_OK |
| `LieJacobiBCH` | 3 | `23c6d1ba6a27...b16e` | FORMAL_SPEC_OK |
| `LieRollingCacheStability` | 8 | `39de7187189d...2fac` | FORMAL_SPEC_OK |
| `MarsdenWeinsteinReduction` | 7 | `b7a66b56f1e5...c972` | FORMAL_SPEC_OK |
| `NoetherSymplecticConservation` | 4 | `3fdc37b141a0...6eb0` | FORMAL_SPEC_OK |
| `OrthogonalProjector` | 2 | `8e696f00df96...ffc6` | FORMAL_SPEC_OK |
| `PadeExponential` | 1 | `981c604d06d2...cd73` | FORMAL_SPEC_OK |
| `PoissonBracketJacobi` | 3 | `18950e0f58da...1229` | FORMAL_SPEC_OK |
| `SolvableLieGroup` | 1 | `cd67105a65fd...24b9` | FORMAL_SPEC_OK |
| `SpectralSymmetric` | 2 | `a8dbcbc9b7a2...8d63` | FORMAL_SPEC_OK |
| `SymplecticBilinear` | 3 | `f79b5fbb0fa5...865f` | FORMAL_SPEC_OK |
| `SymplecticGradientCommutation` | 3 | `13b7d3e0a35e...e508` | FORMAL_SPEC_OK |
| `SymplecticInvariance` | 2 | `0c8689cb4a54...b62c` | FORMAL_SPEC_OK |
| `TraceIdempotent` | 2 | `94e9fa022a1c...41e8` | FORMAL_SPEC_OK |
| `YangMillsCurvature` | 2 | `a51783724afb...24bc` | FORMAL_SPEC_OK |
| `YoshidaSymplecticConservation` | 3 | `64e2e39500d5...389d` | FORMAL_SPEC_OK |
| `AdelicProductFormula` | 4 | `775decf339b2...7b95` | FORMAL_SPEC_OK |
| `BruhatTitsInvariance` | 4 | `782c85d57e37...343f` | FORMAL_SPEC_OK |
| `CoxeterReflectionInvariance` | 4 | `ea9ef1966d2a...273a` | FORMAL_SPEC_OK |
| `GroupInvariants` | 2 | `2bfb8879a25e...fae9` | FORMAL_SPEC_OK |
| `PolytopeSparsity` | 8 | `fbfc2b6bf68c...319a` | FORMAL_SPEC_OK |
| `SpinningManifoldConservation` | 5 | `e6d9d548ee44...ff5e` | FORMAL_SPEC_OK |
| `UltrametricStrongTriangle` | 4 | `98659778d97a...27a0` | FORMAL_SPEC_OK |
| `AbelianSurfaceModularity` | 12 | `bc76bcd57d33...5128` | FORMAL_SPEC_OK |
| `AlgebraicCobordism` | 8 | `dde198569796...950d` | FORMAL_SPEC_OK |
| `ArakelovIntersection` | 7 | `467b0a6177dd...9517` | FORMAL_SPEC_OK |
| `BassQuillen` | 8 | `17ddcb6694dd...1fb9` | FORMAL_SPEC_OK |
| `BeilinsonLichtenbaum` | 10 | `24ad39ff341d...b4e7` | FORMAL_SPEC_OK |
| `BeilinsonRegulatorConjecture` | 12 | `efd1e1193162...9da5` | FORMAL_SPEC_OK |
| `BirchSwinnertonDyer` | 6 | `f1b78ff8ae10...4eb3` | FORMAL_SPEC_OK |
| `BirchSwinnertonDyerConjecture` | 12 | `e3437a59d5a0...a7f7` | FORMAL_SPEC_OK |
| `BlochKatoTamagawa` | 11 | `c8d88d356da1...5d10` | FORMAL_SPEC_OK |
| `BlochSuslin` | 8 | `f43de72229f6...2ad0` | FORMAL_SPEC_OK |
| `ColemanIntegration` | 11 | `3c4120ae6694...ff19` | FORMAL_SPEC_OK |
| `FaltingsHeightTheorem` | 11 | `34d7dce7f83d...52ad` | FORMAL_SPEC_OK |
| `FontaineMazurConjecture` | 10 | `ca0aac6351a8...cfaa` | FORMAL_SPEC_OK |
| `FontaineMazurGeometric` | 6 | `84dc15186616...110f` | FORMAL_SPEC_OK |
| `GaloisDeformationRing` | 6 | `bf1b155c4cb6...e520` | FORMAL_SPEC_OK |
| `GrossZagierFormula` | 12 | `f7747996088f...109e` | FORMAL_SPEC_OK |
| `GrothendieckRiemannRoch` | 5 | `ed132ae0256d...13d4` | FORMAL_SPEC_OK |
| `HardyLittlewoodCircleMethod` | 8 | `3f3712d54887...391f` | FORMAL_SPEC_OK |
| `HodgeConjectureCycles` | 11 | `d4241e66f09e...5a38` | FORMAL_SPEC_OK |
| `IwasawaMainConjecture` | 6 | `e58312dc9282...15ab` | FORMAL_SPEC_OK |
| `KhareWintenbergerLifting` | 8 | `93f20b6887c6...622f` | FORMAL_SPEC_OK |
| `KodairaVanishing` | 8 | `4e80a2ef3cfc...3bb6` | FORMAL_SPEC_OK |
| `LanglandsTunnellBaseChange` | 8 | `acfe3ee48254...9f17` | FORMAL_SPEC_OK |
| `MazurTorsionTheorem` | 12 | `c51b49cb7da4...2a45` | FORMAL_SPEC_OK |
| `MilnorWittHomotopy` | 8 | `c79773bb3248...bc1a` | FORMAL_SPEC_OK |
| `ModularSymbolsManin` | 9 | `eb8aa3cbad97...23bd` | FORMAL_SPEC_OK |
| `MotivicAdamsNovikov` | 8 | `dbe7beaf9ba1...cc50` | FORMAL_SPEC_OK |
| `MotivicBP` | 8 | `f8b6aaba9007...192f` | FORMAL_SPEC_OK |
| `MotivicGoerssHopkins` | 8 | `a005b2aa4d91...b132` | FORMAL_SPEC_OK |
| `MotivicGrossHopkins` | 8 | `29452bd760dc...56b9` | FORMAL_SPEC_OK |
| `MotivicLubinTate` | 8 | `b99c890f0087...8756` | FORMAL_SPEC_OK |
| `MotivicNilpotence` | 8 | `9aad9e6e3599...f26c` | FORMAL_SPEC_OK |
| `MotivicSmashProduct` | 8 | `dc0821e2208f...4716` | FORMAL_SPEC_OK |
| `MotivicTMF` | 8 | `870c8f4ffa02...19f8` | FORMAL_SPEC_OK |
| `NormResidueIsomorphism` | 10 | `2187ef6f75fa...6f07` | FORMAL_SPEC_OK |
| `QuillenLichtenbaum` | 9 | `b1d8ca302761...f780` | FORMAL_SPEC_OK |
| `RostInvariant` | 8 | `977d18e03ad1...1ec7` | FORMAL_SPEC_OK |
| `SatoTateEquidistribution` | 10 | `83fafbe20c5f...4901` | FORMAL_SPEC_OK |
| `SelmerShafarevich` | 6 | `6be0288a909f...0bee` | FORMAL_SPEC_OK |
| `SerreDuality` | 6 | `7f7d8e2a203e...ffac` | FORMAL_SPEC_OK |
| `SerreModularityConjecture` | 6 | `64799f9fcffa...ee05` | FORMAL_SPEC_OK |
| `StandardConjecturesGrothendieck` | 11 | `4dd3b44df1ae...b864` | FORMAL_SPEC_OK |
| `SuslinHomology` | 8 | `44f321a86fe5...4ee2` | FORMAL_SPEC_OK |
| `TateBilinearPairing` | 7 | `b1d5dc9ab01d...5eec` | FORMAL_SPEC_OK |
| `TateConjectureEtale` | 11 | `58706a20d7b9...72b1` | FORMAL_SPEC_OK |
| `TateLocalDuality` | 6 | `3a12e1b92057...bfda` | FORMAL_SPEC_OK |
| `TaylorWilesPatchingSystem` | 8 | `aecfc96c9d89...8533` | FORMAL_SPEC_OK |
| `VoevodskyMotivicCohomology` | 10 | `aa8783d28343...bba0` | FORMAL_SPEC_OK |
| `WeilIIMixedWeights` | 10 | `83e3436fc525...d5f3` | FORMAL_SPEC_OK |
| `WeilReciprocity` | 5 | `fffce804b704...a401` | FORMAL_SPEC_OK |
| `AdamsSpectralSequenceProof` | 4 | `c8fa06ce8b67...b4a0` | FORMAL_SPEC_OK |
| `ArtinInductionTheoremProof` | 3 | `8242297847f5...a861` | FORMAL_SPEC_OK |
| `ArtinReesLemmaProof` | 3 | `f374f91d0271...eb02` | FORMAL_SPEC_OK |
| `AtiyahSingerProof` | 4 | `405c6f1648ca...c4a8` | FORMAL_SPEC_OK |
| `BlochKatoConjectureProof` | 4 | `d1af614e3332...acc7` | FORMAL_SPEC_OK |
| `BochnerWeitzenbockProof` | 3 | `8c1b160ed599...8077` | FORMAL_SPEC_OK |
| `BottPeriodicityProof` | 4 | `84d15c7ab3b5...23d3` | FORMAL_SPEC_OK |
| `BrauerInductionTheoremProof` | 2 | `bfe4176b0bae...f0a5` | FORMAL_SPEC_OK |
| `BurnsidePaQbProof` | 3 | `a45b06d0c6be...8309` | FORMAL_SPEC_OK |
| `CasimirInvariantProof` | 4 | `1ffb6e51b21c...e40d` | FORMAL_SPEC_OK |
| `CayleyUnitarityProof` | 3 | `94423228c102...4f3b` | FORMAL_SPEC_OK |
| `ChernWeilInvarianceProof` | 4 | `d53d1eeb0231...c5b3` | FORMAL_SPEC_OK |
| `ChevalleyWarningTheoremProof` | 1 | `eb25d609641a...bbe1` | FORMAL_SPEC_OK |
| `ChromaticConvergenceProof` | 4 | `88cc91d23c27...cdda` | FORMAL_SPEC_OK |
| `CliffordRepresentationTheoremProof` | 3 | `40a1a77315d3...699b` | FORMAL_SPEC_OK |
| `CobordismTheoremProof` | 4 | `52df3dbf8f22...9fce` | FORMAL_SPEC_OK |
| `ComplexBottPeriodicityProof` | 4 | `2bab10b0ff06...095f` | FORMAL_SPEC_OK |
| `ContinuousCrossingBounds` | 38 | `ecf74e0256d6...afca` | FORMAL_SPEC_OK |
| `DeRhamCohomologyProof` | 5 | `d2063ef9f0a3...57f7` | FORMAL_SPEC_OK |
| `DiracIndexTheoremProof` | 4 | `f7fdc1ad6999...084b` | FORMAL_SPEC_OK |
| `DiscreteToContinuousBridge` | 16 | `dff23b3d51cd...050a` | FORMAL_SPEC_OK |
| `DonaldsonThomasProof` | 3 | `62eeb22c2993...c2e3` | FORMAL_SPEC_OK |
| `DualQuaternionLieBracketProof` | 5 | `9b08336e56e7...9e0c` | FORMAL_SPEC_OK |
| `DualQuaternionMomentumProof` | 3 | `8ef208ce9f71...5419` | FORMAL_SPEC_OK |
| `FittingNilpotentTheoremProof` | 3 | `c77bdfcc4074...61e8` | FORMAL_SPEC_OK |
| `FrobeniusKernelTheoremProof` | 5 | `13dda1d76136...401c` | FORMAL_SPEC_OK |
| `GaussBonnetChernProof` | 3 | `537465bd344d...700d` | FORMAL_SPEC_OK |
| `GeodesicCompletenessProof` | 3 | `db0d43dd4185...ea5c` | FORMAL_SPEC_OK |
| `GeodesicEnergyProof` | 2 | `4c85ff769e0a...59d6` | FORMAL_SPEC_OK |
| `GoerssHopkinsObstructionProof` | 4 | `31f311773bd8...3c0c` | FORMAL_SPEC_OK |
| `GromovWittenAxiomsProof` | 4 | `f51b442400e8...942e` | FORMAL_SPEC_OK |
| `GrossHopkinsDualityProof` | 4 | `268eb4915617...0926` | FORMAL_SPEC_OK |
| `GrothendieckEtaleDualityProof` | 2 | `e58b55bc4f3a...badb` | FORMAL_SPEC_OK |
| `GrothendieckRiemannRochProof` | 3 | `24ee6da91113...0baa` | FORMAL_SPEC_OK |
| `GrushkoTheoremProof` | 3 | `097ecfed5b75...6338` | FORMAL_SPEC_OK |
| `GyroassociativeBracketProof` | 4 | `0cfada01f569...f3b8` | FORMAL_SPEC_OK |
| `GyrovectorCurvatureProof` | 3 | `4cbb2a35fac0...6826` | FORMAL_SPEC_OK |
| `GyrovectorHolonomyProof` | 3 | `4c150cd8d2d6...1150` | FORMAL_SPEC_OK |
| `HadamardCurvatureBoundProof` | 2 | `c83d5e464098...2a4e` | FORMAL_SPEC_OK |
| `HallSolvableSubgroupsProof` | 5 | `a784abebc6b5...f956` | FORMAL_SPEC_OK |
| `HardLefschetzProof` | 5 | `946dd81acef6...1d07` | FORMAL_SPEC_OK |
| `HilbertNullstellensatzProof` | 3 | `74a902a4c7c4...9c3b` | FORMAL_SPEC_OK |
| `HirschPlotkinRadicalProof` | 3 | `22066545f5d8...2fc3` | FORMAL_SPEC_OK |
| `HirzebruchRiemannRochProof` | 3 | `7bf218aaa51f...e38a` | FORMAL_SPEC_OK |
| `HitchinIntegrableProof` | 3 | `b4b0ba15d379...8e57` | FORMAL_SPEC_OK |
| `HodgeDecompositionProof` | 4 | `fe6f96bfbacf...8b8a` | FORMAL_SPEC_OK |
| `HodgeIndexProof` | 5 | `d76933c56c7d...169c` | FORMAL_SPEC_OK |
| `HodgeIndexTheoremProof` | 2 | `1e2689705496...caea` | FORMAL_SPEC_OK |
| `HurewiczTheoremProof` | 5 | `81f2dd5d51b7...efbc` | FORMAL_SPEC_OK |
| `ArchitecturalInvariants` | 5 | `2d1f8bc4fa06...a8d0` | FORMAL_SPEC_OK |
| `Architecture70BSpec` | 19 | `b2b7666780f2...7d90` | FORMAL_SPEC_OK |
| `AsymptoticPolytopeBounds` | 6 | `1588d902970d...ba13` | FORMAL_SPEC_OK |
| `CognitiveFlowSpec` | 7 | `a55bbb1e8a1e...3ad7` | FORMAL_SPEC_OK |
| `CutRSIAdamW` | 4 | `bbeeb50a3a1c...e8f0` | FORMAL_SPEC_OK |
| `ETHUncrossingParallelNormSpec` | 5 | `6a8daf973598...2794` | FORMAL_SPEC_OK |
| `ETHUncrossingSpec` | 10 | `1385fed3ce35...9f5e` | FORMAL_SPEC_OK |
| `EpistemicSoundnessSpec` | 8 | `9ccacd310bd8...c068` | FORMAL_SPEC_OK |
| `FixedPointQuantizationSpec` | 9 | `809dc22ed00e...188a` | FORMAL_SPEC_OK |
| `GossetAndHoneycombSpec` | 10 | `77560957664f...c2a5` | FORMAL_SPEC_OK |
| `HardwareFusedDequantSpec` | 6 | `400ef1748656...4117` | FORMAL_SPEC_OK |
| `IMFFileFormatSpec` | 6 | `4151dbb5ee81...9bdb` | FORMAL_SPEC_OK |
| `LeechLatticeSpec` | 9 | `c5e3c91414ec...251c` | FORMAL_SPEC_OK |
| `NestedAutonomousEvolution` | 20 | `68f63e329adf...c22e` | FORMAL_SPEC_OK |
| `NestedHypercubeCell` | 5 | `e9709c7f4628...9a10` | FORMAL_SPEC_OK |
| `Polydecakon14DSpec` | 9 | `b1746f747901...eb50` | FORMAL_SPEC_OK |
| `PolydokonSpec` | 12 | `6f688ade8b3f...3b65` | FORMAL_SPEC_OK |
| `RiemannianAdamW` | 4 | `4ca9fd796ab0...a2e9` | FORMAL_SPEC_OK |
| `RussianDollCrossPolytopeSpec` | 11 | `79548f3053c2...07cd` | FORMAL_SPEC_OK |
| `SpeculativeAcceptanceSpec` | 5 | `b1f6ffc67006...b012` | FORMAL_SPEC_OK |
| `UnifiedIntegerPrecisionETH` | 12 | `c83d604878ec...588f` | FORMAL_SPEC_OK |
| `JordanHolderTheoremProof` | 3 | `7eba39709943...758f` | FORMAL_SPEC_OK |
| `KodairaSpencerProof` | 4 | `fd6082590455...266f` | FORMAL_SPEC_OK |
| `KodairaVanishingProof` | 6 | `e1ca4d26c2be...0482` | FORMAL_SPEC_OK |
| `KrullSchmidtTheoremProof` | 4 | `b0184ddb1512...b3d9` | FORMAL_SPEC_OK |
| `KrullsIntersectionTheoremProof` | 3 | `6e0a576ce038...a71b` | FORMAL_SPEC_OK |
| `KunnethFormulaProof` | 6 | `7a172ff2c4ac...02e5` | FORMAL_SPEC_OK |
| `KuroshSubgroupTheoremProof` | 3 | `b95898a3a4ac...80b1` | FORMAL_SPEC_OK |
| `LeechSpherePackingProof` | 3 | `f7d1dbef6680...49f8` | FORMAL_SPEC_OK |
| `LefschetzHyperplaneProof` | 5 | `8858d1bef5a2...0e33` | FORMAL_SPEC_OK |
| `MalcevSolvableTheoremProof` | 3 | `c55e2d720e7f...f489` | FORMAL_SPEC_OK |
| `MaschkeSemisimplicityProof` | 4 | `dae490524c7a...5877` | FORMAL_SPEC_OK |
| `MatryoshkaPolytopeProof` | 3 | `6d6ade3c068e...e5c7` | FORMAL_SPEC_OK |
| `MaurerCartanEquationProof` | 4 | `ff8214d7eae3...ff95` | FORMAL_SPEC_OK |
| `MetricCompatibilityProof` | 5 | `cd95aa591213...e755` | FORMAL_SPEC_OK |
| `MorseIndexTheoremProof` | 3 | `5814bd4b4aea...5849` | FORMAL_SPEC_OK |
| `MotivicAdamsNovikovProof` | 4 | `9a8d4bfec1a4...f308` | FORMAL_SPEC_OK |
| `MotivicAdamsSpectralSequenceProof` | 6 | `dd1bbb69f633...dd19` | FORMAL_SPEC_OK |
| `MotivicBaumConnesProof` | 6 | `81b4b59592b2...e1bc` | FORMAL_SPEC_OK |
| `MotivicBeilinsonLichtenbaumProof` | 7 | `0ab2de469cb6...0fae` | FORMAL_SPEC_OK |
| `MotivicFarrellJonesProof` | 6 | `a0922b8e45b1...ce9b` | FORMAL_SPEC_OK |
| `MotivicHopfInvariantProof` | 9 | `de5ac9f878b9...3545` | FORMAL_SPEC_OK |
| `MotivicHopkinsMahowaldProof` | 6 | `128ff84b6bd5...9c48` | FORMAL_SPEC_OK |
| `MotivicLandweberExactProof` | 4 | `9151ea8dc9a3...479d` | FORMAL_SPEC_OK |
| `MotivicMahowaldUncertaintyProof` | 8 | `abaa9ec58d30...d454` | FORMAL_SPEC_OK |
| `MotivicMoravaETheoryProof` | 9 | `4101cb2afc1e...a0e9` | FORMAL_SPEC_OK |
| `MotivicMoravaKTheoryProof` | 4 | `e2a633f0b826...2ccc` | FORMAL_SPEC_OK |
| `MotivicNilpotenceProof` | 4 | `80351dda9ed4...632b` | FORMAL_SPEC_OK |
| `MotivicNovikovConjectureProof` | 7 | `b094daa8ea60...7068` | FORMAL_SPEC_OK |
| `MotivicPeriodicityProof` | 9 | `a02f55866aef...c6fe` | FORMAL_SPEC_OK |
| `MotivicQuillenLichtenbaumProof` | 6 | `72306f71e4ce...500e` | FORMAL_SPEC_OK |
| `MotivicRavenelConjecturesProof` | 9 | `851feae399ea...d538` | FORMAL_SPEC_OK |
| `MotivicSpin8TrialityProof` | 8 | `a2de5eb63bd8...ccfb` | FORMAL_SPEC_OK |
| `MotivicSteenrodAlgebraProof` | 7 | `aa0ca0e6379b...4888` | FORMAL_SPEC_OK |
| `MotivicTateConjectureProof` | 6 | `733c38511bda...0244` | FORMAL_SPEC_OK |
| `MotivicTodaBracketProof` | 8 | `43bad5d53024...3caa` | FORMAL_SPEC_OK |
| `MotivicWoodTheoremProof` | 10 | `c6b75367b9f4...14a3` | FORMAL_SPEC_OK |
| `NakayamasLemmaProof` | 5 | `a05e3d57183b...b837` | FORMAL_SPEC_OK |
| `NarasimhanSeshadriProof` | 4 | `d71285b68a7d...00b4` | FORMAL_SPEC_OK |
| `NielsenSchreierTheoremProof` | 3 | `97c4c467d4ab...8bd2` | FORMAL_SPEC_OK |
| `NoetherCoadjointOrbitProof` | 4 | `70f2e1ff52d8...f6cc` | FORMAL_SPEC_OK |
| `NovikovAdditivityProof` | 3 | `50248ed16f27...a8e2` | FORMAL_SPEC_OK |
| `OrthoplexVolumeConservationProof` | 3 | `b31946fc387a...ce81` | FORMAL_SPEC_OK |
| `PoincareDualityProof` | 4 | `05a4cc436cd6...c451` | FORMAL_SPEC_OK |
| `PolytopeBarycentric` | 32 | `a0fb4bc549bf...5d6f` | FORMAL_SPEC_OK |
| `PontryaginGeodesicControlProof` | 3 | `1e067622b1e0...fb05` | FORMAL_SPEC_OK |
| `QuillenMetricProof` | 3 | `1b56cdb26694...e19e` | FORMAL_SPEC_OK |
| `RecursiveSelfImprovementETH` | 31 | `5433b35fc9e8...03e4` | FORMAL_SPEC_OK |
| `RiemannianLieGroup` | 3 | `107b3405ab78...0f47` | FORMAL_SPEC_OK |
| `SchreierSimsAlgorithmProof` | 3 | `b2193fa0d2ed...c833` | FORMAL_SPEC_OK |
| `SchurZassenhausProof` | 3 | `e3eba572f51d...b8bf` | FORMAL_SPEC_OK |
| `SchurZassenhausTheoremProof` | 5 | `bdf81c5433ae...7ba1` | FORMAL_SPEC_OK |
| `SchursLemmaProof` | 3 | `5c0c89c2326d...2f09` | FORMAL_SPEC_OK |
| `SeibergWittenProof` | 3 | `b0351914fb6b...14d3` | FORMAL_SPEC_OK |
| `SerreDualityProof` | 7 | `d9a44b300b45...df47` | FORMAL_SPEC_OK |
| `SerreSpectralSequenceProof` | 5 | `3b3b03c225b5...74d2` | FORMAL_SPEC_OK |
| `SerresCriterionNormalityProof` | 3 | `f06353e3f22f...a4d6` | FORMAL_SPEC_OK |
| `SymplecticFixedPointProof` | 3 | `a9ba1d666fc5...92a2` | FORMAL_SPEC_OK |
| `SymplecticGeodesicProof` | 2 | `5c7567015b73...cccb` | FORMAL_SPEC_OK |
| `SymplecticPhaseVolumeProof` | 3 | `7b618b757ef2...41a6` | FORMAL_SPEC_OK |
| `ThomIsomorphismProof` | 4 | `abe8c813a993...a37f` | FORMAL_SPEC_OK |
| `TitsAlternativeProof` | 3 | `8791db54852f...d8f9` | FORMAL_SPEC_OK |
| `TrialityInvarianceProof` | 3 | `196eb192531f...5d70` | FORMAL_SPEC_OK |
| `UhlenbeckCompactnessProof` | 3 | `989018121393...47b1` | FORMAL_SPEC_OK |
| `UnbiasedQuantizationProof` | 3 | `5a15bd93c981...9305` | FORMAL_SPEC_OK |
| `VerlindeFormulaProof` | 4 | `4a6c7600c0dd...e55c` | FORMAL_SPEC_OK |
| `WedderburnArtinTheoremProof` | 2 | `63cca1135d43...5cbf` | FORMAL_SPEC_OK |
| `WhiteheadTheoremProof` | 5 | `0de76e3ae1fe...cbd7` | FORMAL_SPEC_OK |
| `ZariskiMainTheoremProof` | 2 | `dfca9d03bf81...faed` | FORMAL_SPEC_OK |
| `AbelianSurfaceModularity` | 12 | `bc76bcd57d33...5128` | FORMAL_SPEC_OK |
| `AdelicProductFormula` | 4 | `775decf339b2...7b95` | FORMAL_SPEC_OK |
| `AlgebraicCobordism` | 8 | `dde198569796...950d` | FORMAL_SPEC_OK |
| `ArakelovIntersection` | 7 | `467b0a6177dd...9517` | FORMAL_SPEC_OK |
| `BassQuillen` | 8 | `17ddcb6694dd...1fb9` | FORMAL_SPEC_OK |
| `BeilinsonLichtenbaum` | 10 | `24ad39ff341d...b4e7` | FORMAL_SPEC_OK |
| `BeilinsonRegulatorConjecture` | 12 | `efd1e1193162...9da5` | FORMAL_SPEC_OK |
| `BirchSwinnertonDyer` | 6 | `f1b78ff8ae10...4eb3` | FORMAL_SPEC_OK |
| `BirchSwinnertonDyerConjecture` | 12 | `e3437a59d5a0...a7f7` | FORMAL_SPEC_OK |
| `BlochKatoTamagawa` | 11 | `c8d88d356da1...5d10` | FORMAL_SPEC_OK |
| `BlochSuslin` | 8 | `f43de72229f6...2ad0` | FORMAL_SPEC_OK |
| `BruhatTitsInvariance` | 4 | `782c85d57e37...343f` | FORMAL_SPEC_OK |
| `CartanKillingSemisimplicity` | 3 | `dd4858e554b8...4544` | FORMAL_SPEC_OK |
| `CasimirInvariant` | 2 | `4c429e6e8705...a875` | FORMAL_SPEC_OK |
| `CayleyOrthogonal` | 3 | `6e639b46f5e2...9277` | FORMAL_SPEC_OK |
| `ChromaticTower` | 8 | `4fd2ae7fef4e...cd79` | FORMAL_SPEC_OK |
| `ColemanIntegration` | 11 | `3c4120ae6694...ff19` | FORMAL_SPEC_OK |
| `CoxeterReflectionInvariance` | 4 | `ea9ef1966d2a...273a` | FORMAL_SPEC_OK |
| `ExteriorDerivativeNilpotent` | 1 | `85bbbdbd4282...3375` | FORMAL_SPEC_OK |
| `FaltingsHeightTheorem` | 11 | `34d7dce7f83d...52ad` | FORMAL_SPEC_OK |
| `FontaineMazurConjecture` | 10 | `ca0aac6351a8...cfaa` | FORMAL_SPEC_OK |
| `FontaineMazurGeometric` | 6 | `84dc15186616...110f` | FORMAL_SPEC_OK |
| `GaloisDeformationRing` | 6 | `bf1b155c4cb6...e520` | FORMAL_SPEC_OK |
| `GrassmannExterior` | 3 | `f2094daf662b...e7d6` | FORMAL_SPEC_OK |
| `GrossZagierFormula` | 12 | `f7747996088f...109e` | FORMAL_SPEC_OK |
| `GrothendieckRiemannRoch` | 5 | `ed132ae0256d...13d4` | FORMAL_SPEC_OK |
| `GroupInvariants` | 2 | `2bfb8879a25e...fae9` | FORMAL_SPEC_OK |
| `HardyLittlewoodCircleMethod` | 8 | `3f3712d54887...391f` | FORMAL_SPEC_OK |
| `HodgeConjectureCycles` | 11 | `d4241e66f09e...5a38` | FORMAL_SPEC_OK |
| `HodgeIndexCore` | 2 | `0205e3f0de0e...47cf` | FORMAL_SPEC_OK |
| `HodgeStarDuality` | 3 | `9a9cd7e9cb70...8925` | FORMAL_SPEC_OK |
| `IwasawaMainConjecture` | 6 | `e58312dc9282...15ab` | FORMAL_SPEC_OK |
| `KKSFormInvariance` | 4 | `bfb188cac93f...6ded` | FORMAL_SPEC_OK |
| `KhareWintenbergerLifting` | 8 | `93f20b6887c6...622f` | FORMAL_SPEC_OK |
| `KillingForm` | 3 | `8f8e26a61730...6df1` | FORMAL_SPEC_OK |
| `KodairaVanishing` | 8 | `4e80a2ef3cfc...3bb6` | FORMAL_SPEC_OK |
| `LanglandsTunnellBaseChange` | 8 | `acfe3ee48254...9f17` | FORMAL_SPEC_OK |
| `LieAlgebraInvariants` | 2 | `915bb5eeb4f2...5fa0` | FORMAL_SPEC_OK |
| `LieDerivation` | 2 | `ce0310ef6c27...a987` | FORMAL_SPEC_OK |
| `LieJacobiBCH` | 3 | `23c6d1ba6a27...b16e` | FORMAL_SPEC_OK |
| `LieRollingCacheStability` | 8 | `39de7187189d...2fac` | FORMAL_SPEC_OK |
| `MarsdenWeinsteinReduction` | 7 | `b7a66b56f1e5...c972` | FORMAL_SPEC_OK |
| `MazurTorsionTheorem` | 12 | `c51b49cb7da4...2a45` | FORMAL_SPEC_OK |
| `MilnorWittHomotopy` | 8 | `c79773bb3248...bc1a` | FORMAL_SPEC_OK |
| `ModularSymbolsManin` | 9 | `eb8aa3cbad97...23bd` | FORMAL_SPEC_OK |
| `MotivicAdamsNovikov` | 8 | `dbe7beaf9ba1...cc50` | FORMAL_SPEC_OK |
| `MotivicBP` | 8 | `f8b6aaba9007...192f` | FORMAL_SPEC_OK |
| `MotivicGoerssHopkins` | 8 | `a005b2aa4d91...b132` | FORMAL_SPEC_OK |
| `MotivicGrossHopkins` | 8 | `29452bd760dc...56b9` | FORMAL_SPEC_OK |
| `MotivicLubinTate` | 8 | `b99c890f0087...8756` | FORMAL_SPEC_OK |
| `MotivicNilpotence` | 8 | `9aad9e6e3599...f26c` | FORMAL_SPEC_OK |
| `MotivicSmashProduct` | 8 | `dc0821e2208f...4716` | FORMAL_SPEC_OK |
| `MotivicTMF` | 8 | `870c8f4ffa02...19f8` | FORMAL_SPEC_OK |
| `NoetherSymplecticConservation` | 4 | `3fdc37b141a0...6eb0` | FORMAL_SPEC_OK |
| `NormResidueIsomorphism` | 10 | `2187ef6f75fa...6f07` | FORMAL_SPEC_OK |
| `OrthogonalProjector` | 2 | `8e696f00df96...ffc6` | FORMAL_SPEC_OK |
| `PadeExponential` | 1 | `981c604d06d2...cd73` | FORMAL_SPEC_OK |
| `PoissonBracketJacobi` | 3 | `18950e0f58da...1229` | FORMAL_SPEC_OK |
| `PolytopeSparsity` | 8 | `fbfc2b6bf68c...319a` | FORMAL_SPEC_OK |
| `QuillenLichtenbaum` | 9 | `b1d8ca302761...f780` | FORMAL_SPEC_OK |
| `RostInvariant` | 8 | `977d18e03ad1...1ec7` | FORMAL_SPEC_OK |
| `SatoTateEquidistribution` | 10 | `83fafbe20c5f...4901` | FORMAL_SPEC_OK |
| `SelmerShafarevich` | 6 | `6be0288a909f...0bee` | FORMAL_SPEC_OK |
| `SerreDuality` | 6 | `7f7d8e2a203e...ffac` | FORMAL_SPEC_OK |
| `SerreModularityConjecture` | 6 | `64799f9fcffa...ee05` | FORMAL_SPEC_OK |
| `SolvableLieGroup` | 1 | `cd67105a65fd...24b9` | FORMAL_SPEC_OK |
| `SpectralSymmetric` | 2 | `a8dbcbc9b7a2...8d63` | FORMAL_SPEC_OK |
| `SpinningManifoldConservation` | 5 | `e6d9d548ee44...ff5e` | FORMAL_SPEC_OK |
| `StandardConjecturesGrothendieck` | 11 | `4dd3b44df1ae...b864` | FORMAL_SPEC_OK |
| `SuslinHomology` | 8 | `44f321a86fe5...4ee2` | FORMAL_SPEC_OK |
| `SymplecticBilinear` | 3 | `f79b5fbb0fa5...865f` | FORMAL_SPEC_OK |
| `SymplecticGradientCommutation` | 3 | `13b7d3e0a35e...e508` | FORMAL_SPEC_OK |
| `SymplecticInvariance` | 2 | `0c8689cb4a54...b62c` | FORMAL_SPEC_OK |
| `TateBilinearPairing` | 7 | `b1d5dc9ab01d...5eec` | FORMAL_SPEC_OK |
| `TateConjectureEtale` | 11 | `58706a20d7b9...72b1` | FORMAL_SPEC_OK |
| `TateLocalDuality` | 6 | `3a12e1b92057...bfda` | FORMAL_SPEC_OK |
| `TaylorWilesPatchingSystem` | 8 | `aecfc96c9d89...8533` | FORMAL_SPEC_OK |
| `TraceIdempotent` | 2 | `94e9fa022a1c...41e8` | FORMAL_SPEC_OK |
| `UltrametricStrongTriangle` | 4 | `98659778d97a...27a0` | FORMAL_SPEC_OK |
| `VoevodskyMotivicCohomology` | 10 | `aa8783d28343...bba0` | FORMAL_SPEC_OK |
| `WeilIIMixedWeights` | 10 | `83e3436fc525...d5f3` | FORMAL_SPEC_OK |
| `WeilReciprocity` | 5 | `fffce804b704...a401` | FORMAL_SPEC_OK |
| `YangMillsCurvature` | 2 | `a51783724afb...24bc` | FORMAL_SPEC_OK |
| `YoshidaSymplecticConservation` | 3 | `64e2e39500d5...389d` | FORMAL_SPEC_OK |
