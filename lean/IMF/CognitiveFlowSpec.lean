import Lean

namespace IMF

/-- 5 discrete phases of the cognitive flow state machine. -/
inductive CognitivePhase : Type
  | setup     : CognitivePhase
  | struggle  : CognitivePhase
  | release   : CognitivePhase
  | flow      : CognitivePhase
  | recovery  : CognitivePhase
  deriving DecidableEq, Repr

/-- Order relation on cognitive phases reflecting the canonical progression. -/
def phaseRank : CognitivePhase → Nat
  | .setup    => 0
  | .struggle => 1
  | .release  => 2
  | .flow     => 3
  | .recovery => 4

/-- Strict forward monotonic step in the canonical flow loop. -/
def isValidCanonicalTransition (p₁ p₂ : CognitivePhase) : Prop :=
  phaseRank p₂ = phaseRank p₁ + 1

/-- State representation tracking current phase and friction/bottleneck status. -/
structure CognitiveState where
  phase : CognitivePhase
  frictionLevel : Nat
  taskClarity : Nat
  deriving DecidableEq, Repr

/-- Troubleshooting bottleneck classification. -/
inductive Bottleneck : Type
  | anxiousFrozen
  | boredRestless
  | foggySluggish
  | distracted
  | none
  deriving DecidableEq, Repr

/-- Diagnostic function mapping state metrics to bottleneck types. -/
def diagnoseBottleneck (s : CognitiveState) : Bottleneck :=
  if s.taskClarity < 3 then Bottleneck.anxiousFrozen
  else if s.frictionLevel == 0 then Bottleneck.boredRestless
  else if s.frictionLevel > 8 then Bottleneck.foggySluggish
  else Bottleneck.none

/-- Applying diagnostic fix restores task clarity and bounds friction. -/
def applyDiagnosticFix (s : CognitiveState) (b : Bottleneck) : CognitiveState :=
  match b with
  | Bottleneck.anxiousFrozen => { s with taskClarity := 10, frictionLevel := 2 }
  | Bottleneck.boredRestless => { s with frictionLevel := 5 }
  | Bottleneck.foggySluggish => { s with frictionLevel := 3 }
  | Bottleneck.distracted    => { s with taskClarity := 8, frictionLevel := 2 }
  | Bottleneck.none          => s

/-- Theorem: Canonical flow progression strictly increases phase rank. -/
theorem canonical_transition_strict_monotonic (p₁ p₂ : CognitivePhase)
    (h : isValidCanonicalTransition p₁ p₂) :
    phaseRank p₁ < phaseRank p₂ := by
  dsimp [isValidCanonicalTransition] at h
  rw [h]
  exact Nat.lt_succ_self (phaseRank p₁)

/-- Theorem: Applying fix to an anxious/frozen state guarantees high clarity (≥ 8). -/
theorem anxious_fix_guarantees_clarity (s : CognitiveState) :
    (applyDiagnosticFix s Bottleneck.anxiousFrozen).taskClarity ≥ 8 := by
  dsimp [applyDiagnosticFix]
  decide

/-- Theorem: Applying fix to a foggy state bounds friction strictly below critical threshold (10). -/
theorem foggy_fix_bounds_friction (s : CognitiveState) :
    (applyDiagnosticFix s Bottleneck.foggySluggish).frictionLevel < 10 := by
  dsimp [applyDiagnosticFix]
  decide

end IMF
