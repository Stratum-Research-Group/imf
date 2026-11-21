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
    `IMF.FixedPointQuantizationSpec
  ]

