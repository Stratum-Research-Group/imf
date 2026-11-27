import Mathlib

open Matrix

/-!
# Pilot Formalization: Commutator Nilpotency & Solvability Invariants

Proves that for commuting matrices A and B, their commutator bracket is strictly zero:
[A, B] = A*B - B*A = 0.
-/

theorem commuting_bracket_zero {n : ℕ} (A B : Matrix (Fin n) (Fin n) ℝ)
    (hcomm : A * B = B * A) : A * B - B * A = 0 := by
  rw [hcomm, sub_self]

#print axioms commuting_bracket_zero
