import Mathlib

open Matrix

/-!
# Pilot Formalization: Symplectic Bilinear Form Skew-Symmetry & Alternation

For any skew-symmetric structure matrix J with Jᵀ = -J:
1. ω(x, y) = -ω(y, x) (skew-symmetry)
2. ω(x, x) = 0 (alternating property)
-/

def symplectic_form {n : ℕ} (J : Matrix (Fin n) (Fin n) ℝ) (x y : Fin n → ℝ) : ℝ :=
  x ⬝ᵥ (J *ᵥ y)

theorem symplectic_skew_symm {n : ℕ} (J : Matrix (Fin n) (Fin n) ℝ) (hJ : Jᵀ = -J)
    (x y : Fin n → ℝ) : symplectic_form J x y = - symplectic_form J y x := by
  unfold symplectic_form
  rw [dotProduct_mulVec, ← mulVec_transpose, hJ]
  simp only [neg_mulVec, dotProduct_neg, dotProduct_comm]

theorem symplectic_alternating {n : ℕ} (J : Matrix (Fin n) (Fin n) ℝ) (hJ : Jᵀ = -J)
    (x : Fin n → ℝ) : symplectic_form J x x = 0 := by
  have h := symplectic_skew_symm J hJ x x
  linarith

#print axioms symplectic_skew_symm
#print axioms symplectic_alternating
