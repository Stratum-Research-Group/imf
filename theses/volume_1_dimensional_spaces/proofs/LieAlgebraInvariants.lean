import Mathlib

open Matrix

/-!
# Pilot Formalization: Lie Algebra Properties of Skew-Symmetric Matrices

Here we prove substantive algebraic invariants in Lean 4 + Mathlib:
1. The space of real skew-symmetric matrices is closed under the Lie bracket: [A, B] = A*B - B*A is skew-symmetric.
2. Trace of any skew-symmetric matrix is zero.
-/

theorem skew_bracket_skew {n : ℕ} (A B : Matrix (Fin n) (Fin n) ℝ)
    (hA : Aᵀ = -A) (hB : Bᵀ = -B) :
    (A * B - B * A)ᵀ = -(A * B - B * A) := by
  rw [transpose_sub, transpose_mul, transpose_mul, hA, hB]
  simp only [neg_mul, mul_neg, neg_neg]
  abel

theorem skew_trace_zero {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ)
    (hA : Aᵀ = -A) : Matrix.trace A = 0 := by
  have h1 : Matrix.trace Aᵀ = Matrix.trace (-A) := by rw [hA]
  rw [Matrix.trace_transpose, Matrix.trace_neg] at h1
  linarith

#print axioms skew_bracket_skew
#print axioms skew_trace_zero
