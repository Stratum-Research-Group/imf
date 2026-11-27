import Mathlib

open Matrix

/-!
# Pilot Formalization: Pade Matrix Exponential Commutativity
-/

theorem matrix_exp_neg_cancel {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ) :
    let _ := Matrix.linftyOpNormedRing (n := Fin n) (α := ℝ)
    let _ := Matrix.linftyOpNormedAlgebra (n := Fin n) (R := ℝ) (α := ℝ)
    let _ : NormedAlgebra ℚ (Matrix (Fin n) (Fin n) ℝ) := NormedAlgebra.restrictScalars ℚ ℝ _
    NormedSpace.exp A * NormedSpace.exp (-A) = 1 := by
  let _ := Matrix.linftyOpNormedRing (n := Fin n) (α := ℝ)
  let _ := Matrix.linftyOpNormedAlgebra (n := Fin n) (R := ℝ) (α := ℝ)
  let _ : NormedAlgebra ℚ (Matrix (Fin n) (Fin n) ℝ) := NormedAlgebra.restrictScalars ℚ ℝ _
  have h := NormedSpace.exp_add_of_commute (Commute.refl A |>.neg_right)
  rw [add_neg_cancel, NormedSpace.exp_zero] at h
  exact h.symm

#print axioms matrix_exp_neg_cancel
