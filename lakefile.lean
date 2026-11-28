import Lake
open Lake DSL

package "IMF" where
  version := v!"0.1.0"
  keywords := #["mathematics", "neural-memory", "formal-verification", "circuit-complexity"]

@[default_target]
lean_lib «DiscreteToContinuousBridge» where
  srcDir := "lean"
  roots := #[`DiscreteToContinuousBridge]

@[default_target]
lean_lib «ContinuousCrossingBounds» where
  srcDir := "lean"
  roots := #[`ContinuousCrossingBounds]

@[default_target]
lean_lib «PolytopeBarycentric» where
  srcDir := "lean"
  roots := #[`PolytopeBarycentric]

@[default_target]
lean_lib «RecursiveSelfImprovementETH» where
  srcDir := "lean"
  roots := #[`RecursiveSelfImprovementETH]

@[default_target]
lean_lib «IMF» where
  srcDir := "lean"
  roots := #[
    `IMF.CutRSIAdamW,
    `IMF.NestedHypercubeCell,
    `IMF.NestedAutonomousEvolution,
    `IMF.RiemannianAdamW,
    `IMF.UnifiedIntegerPrecisionETH,
    `IMF.IMFFileFormatSpec,
    `IMF.ETHUncrossingSpec,
    `IMF.Architecture70BSpec,
    `IMF.PolydokonSpec,
    `IMF.Polydecakon14DSpec,
    `IMF.RussianDollCrossPolytopeSpec,
    `IMF.GossetAndHoneycombSpec,
    `IMF.LeechLatticeSpec,
    `IMF.ETHUncrossingParallelNormSpec,
    `IMF.SpeculativeAcceptanceSpec,
    `IMF.CognitiveFlowSpec,
    `IMF.FixedPointQuantizationSpec,
    `IMF.AsymptoticPolytopeBounds,
    `IMF.HardwareFusedDequantSpec,
    `IMF.EpistemicSoundnessSpec,
    `AdamsSpectralSequenceProof,
    `ArtinInductionTheoremProof,
    `ArtinReesLemmaProof,
    `AtiyahSingerProof,
    `BlochKatoConjectureProof,
    `BochnerWeitzenbockProof,
    `BottPeriodicityProof,
    `BrauerInductionTheoremProof,
    `BurnsidePaQbProof,
    `CasimirInvariantProof,
    `ChernWeilInvarianceProof,
    `ChevalleyWarningTheoremProof,
    `ChromaticConvergenceProof,
    `CliffordRepresentationTheoremProof,
    `CobordismTheoremProof,
    `ComplexBottPeriodicityProof,
    `ContinuousCrossingBounds,
    `DeRhamCohomologyProof,
    `DiracIndexTheoremProof,
    `DonaldsonThomasProof,
    `DualQuaternionLieBracketProof,
    `FittingNilpotentTheoremProof,
    `FrobeniusKernelTheoremProof,
    `GaussBonnetChernProof,
    `GeodesicCompletenessProof,
    `GoerssHopkinsObstructionProof,
    `GromovWittenAxiomsProof,
    `GrossHopkinsDualityProof,
    `GrothendieckEtaleDualityProof,
    `GrothendieckRiemannRochProof,
    `GrushkoTheoremProof,
    `GyroassociativeBracketProof,
    `HadamardCurvatureBoundProof,
    `HallSolvableSubgroupsProof,
    `HardLefschetzProof,
    `HilbertNullstellensatzProof,
    `HirschPlotkinRadicalProof,
    `HirzebruchRiemannRochProof,
    `HitchinIntegrableProof,
    `HodgeDecompositionProof,
    `HodgeIndexProof,
    `HodgeIndexTheoremProof,
    `HurewiczTheoremProof,
    `JordanHolderTheoremProof,
    `KodairaSpencerProof,
    `KodairaVanishingProof,
    `KrullSchmidtTheoremProof,
    `KrullsIntersectionTheoremProof,
    `KunnethFormulaProof,
    `KuroshSubgroupTheoremProof,
    `LefschetzHyperplaneProof,
    `MalcevSolvableTheoremProof,
    `MaschkeSemisimplicityProof,
    `MaurerCartanEquationProof,
    `MetricCompatibilityProof,
    `MorseIndexTheoremProof,
    `MotivicAdamsNovikovProof,
    `MotivicAdamsSpectralSequenceProof,
    `MotivicBaumConnesProof,
    `MotivicBeilinsonLichtenbaumProof,
    `MotivicFarrellJonesProof,
    `MotivicHopfInvariantProof,
    `MotivicHopkinsMahowaldProof,
    `MotivicLandweberExactProof,
    `MotivicMahowaldUncertaintyProof,
    `MotivicMoravaETheoryProof,
    `MotivicMoravaKTheoryProof,
    `MotivicNilpotenceProof,
    `MotivicNovikovConjectureProof,
    `MotivicPeriodicityProof,
    `MotivicQuillenLichtenbaumProof,
    `MotivicRavenelConjecturesProof,
    `MotivicSpin8TrialityProof,
    `MotivicSteenrodAlgebraProof,
    `MotivicTateConjectureProof,
    `MotivicTodaBracketProof,
    `MotivicWoodTheoremProof,
    `NakayamasLemmaProof,
    `NarasimhanSeshadriProof,
    `NielsenSchreierTheoremProof,
    `NoetherCoadjointOrbitProof,
    `NovikovAdditivityProof,
    `OrthoplexVolumeConservationProof,
    `PoincareDualityProof,
    `PolytopeBarycentric,
    `PontryaginGeodesicControlProof,
    `QuillenMetricProof,
    `RecursiveSelfImprovementETH,
    `SchreierSimsAlgorithmProof,
    `SchurZassenhausProof,
    `SchurZassenhausTheoremProof,
    `SchursLemmaProof,
    `SeibergWittenProof,
    `SerreDualityProof,
    `SerreSpectralSequenceProof,
    `SerresCriterionNormalityProof,
    `SymplecticFixedPointProof,
    `SymplecticPhaseVolumeProof,
    `ThomIsomorphismProof,
    `TitsAlternativeProof,
    `UhlenbeckCompactnessProof,
    `VerlindeFormulaProof,
    `WedderburnArtinTheoremProof,
    `WhiteheadTheoremProof,
    `ZariskiMainTheoremProof
  ]
