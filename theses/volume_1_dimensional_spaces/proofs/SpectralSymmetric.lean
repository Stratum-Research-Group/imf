import Mathlib

open Matrix

/-!
# Pilot Formalization: Symmetry and Bilinear Orthogonality Invariants
-/

theorem symmetric_transpose_eq {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ) (hA : Aᵀ = A) :
    A = Aᵀ := hA.symm

theorem symmetric_bilinear_comm {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ) (hA : Aᵀ = A)
    (x y : Fin n → ℝ) : x ⬝ᵥ (A *ᵥ y) = y ⬝ᵥ (A *ᵥ x) := by
  rw [dotProduct_mulVec, ← mulVec_transpose, hA, dotProduct_comm]

#print axioms symmetric_transpose_eq
#print axioms symmetric_bilinear_comm
