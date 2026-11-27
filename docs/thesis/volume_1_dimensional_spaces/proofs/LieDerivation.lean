import Mathlib

open Matrix

/-!
# Pilot Formalization: Derivations on Real Matrix Algebras & Commutator Invariance

Proves that the commutator adjoint map ad_X(Y) = [X, Y] is a derivation on matrix algebras:
ad_X(Y * Z) = ad_X(Y) * Z + Y * ad_X(Z).
-/

def ad {n : ℕ} (X Y : Matrix (Fin n) (Fin n) ℝ) : Matrix (Fin n) (Fin n) ℝ :=
  X * Y - Y * X

theorem ad_derivation {n : ℕ} (X Y Z : Matrix (Fin n) (Fin n) ℝ) :
    ad X (Y * Z) = ad X Y * Z + Y * ad X Z := by
  unfold ad
  simp only [mul_sub, sub_mul, mul_assoc]
  abel

#print axioms ad_derivation
