import Mathlib

open Matrix

/-!
# Pilot Formalization: Orthogonal Projectors & Idempotence
-/

theorem idempotent_sub_idempotent {n : ℕ} (P : Matrix (Fin n) (Fin n) ℝ) (hP : P * P = P) :
    (1 - P) * (1 - P) = 1 - P := by
  calc (1 - P) * (1 - P) = 1 * (1 - P) - P * (1 - P) := by rw [sub_mul]
    _ = (1 - P) - (P * 1 - P * P) := by rw [one_mul, mul_sub]
    _ = (1 - P) - (P - P) := by rw [mul_one, hP]
    _ = 1 - P := by rw [sub_self, sub_zero]

theorem projector_orthogonal_split {n : ℕ} (P : Matrix (Fin n) (Fin n) ℝ) (x : Fin n → ℝ) :
    P *ᵥ x + (1 - P) *ᵥ x = x := by
  rw [← add_mulVec, add_sub_cancel, one_mulVec]

#print axioms idempotent_sub_idempotent
#print axioms projector_orthogonal_split
