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
