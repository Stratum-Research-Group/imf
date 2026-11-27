import Mathlib

open Matrix

/-!
# Pilot Formalization: Projector Product Orthogonality
-/

theorem projector_orthogonal_product {n : ℕ} (P : Matrix (Fin n) (Fin n) ℝ) (hP : P * P = P) :
    P * (1 - P) = 0 := by
  rw [mul_sub, mul_one, hP, sub_self]

theorem complementary_projector_orthogonal_product {n : ℕ} (P : Matrix (Fin n) (Fin n) ℝ) (hP : P * P = P) :
    (1 - P) * P = 0 := by
  rw [sub_mul, one_mul, hP, sub_self]

#print axioms projector_orthogonal_product
#print axioms complementary_projector_orthogonal_product
