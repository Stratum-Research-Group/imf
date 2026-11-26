import Mathlib
import Pilot.LieJacobiBCH

open Matrix

/-!
# Pilot Formalization: Killing Form & Adjoint Invariance

Proves symmetry and adjoint-bracket invariance for the trace-form (Killing form)
on matrix Lie algebras:
B([X, Y], Z) = B(X, [Y, Z]).
-/

def killing_form {n : ℕ} (X Y : Matrix (Fin n) (Fin n) ℝ) : ℝ :=
  trace (X * Y)

theorem killing_form_symm {n : ℕ} (X Y : Matrix (Fin n) (Fin n) ℝ) :
    killing_form X Y = killing_form Y X := by
  unfold killing_form
  exact trace_mul_comm X Y

theorem killing_form_bracket_invariant {n : ℕ} (X Y Z : Matrix (Fin n) (Fin n) ℝ) :
    killing_form (bracket X Y) Z = killing_form X (bracket Y Z) := by
  unfold killing_form bracket
  simp only [sub_mul, mul_sub, trace_sub, mul_assoc]
  congr 1
  rw [trace_mul_comm Y (X * Z)]
  rw [mul_assoc]

#print axioms killing_form_symm
#print axioms killing_form_bracket_invariant
