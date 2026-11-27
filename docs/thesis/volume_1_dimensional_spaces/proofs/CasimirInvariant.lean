import Mathlib
import Pilot.LieJacobiBCH

open Matrix

/-!
# Pilot Formalization: Quadratic Casimir Central Invariance

Proves that any central Casimir operator C satisfying C * X = X * C
trivially commutes under the Lie bracket:
[C, X] = 0 and [X, C] = 0.
-/

theorem casimir_bracket_comm {n : ℕ} (C X : Matrix (Fin n) (Fin n) ℝ) (hC : C * X = X * C) :
    bracket C X = 0 := by
  unfold bracket
  rw [hC, sub_self]

theorem casimir_bracket_comm_symm {n : ℕ} (C X : Matrix (Fin n) (Fin n) ℝ) (hC : C * X = X * C) :
    bracket X C = 0 := by
  unfold bracket
  rw [hC, sub_self]

#print axioms casimir_bracket_comm
#print axioms casimir_bracket_comm_symm
