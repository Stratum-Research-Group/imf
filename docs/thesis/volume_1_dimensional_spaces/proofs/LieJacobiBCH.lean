import Mathlib

open Matrix

/-!
# Pilot Formalization: Jacobi Identity & Trace Invariance in Skew-Symmetric Lie Algebras
-/

def bracket {n : ℕ} (A B : Matrix (Fin n) (Fin n) ℝ) : Matrix (Fin n) (Fin n) ℝ :=
  A * B - B * A

theorem matrix_bracket_jacobi {n : ℕ} (A B C : Matrix (Fin n) (Fin n) ℝ) :
    bracket A (bracket B C) + bracket B (bracket C A) + bracket C (bracket A B) = 0 := by
  unfold bracket
  simp only [mul_sub, sub_mul, mul_assoc]
  abel

theorem skew_bracket_trace_zero {n : ℕ} (A B : Matrix (Fin n) (Fin n) ℝ) :
    Matrix.trace (bracket A B) = 0 := by
  unfold bracket
  rw [Matrix.trace_sub, Matrix.trace_mul_comm]
  ring

#print axioms matrix_bracket_jacobi
#print axioms skew_bracket_trace_zero
