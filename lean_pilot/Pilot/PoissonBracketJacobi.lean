import Mathlib

open Matrix

/-!
# Pilot Formalization: Poisson Bracket Jacobi Identity in Hamiltonian Mechanics

For symmetric Hamiltonian matrices A, B, C with symplectic structure matrix J:
The Poisson-Lie bracket is defined as:
  poisson_bracket J A B = A * J * B - B * J * A

Theorem:
  poisson_bracket J (poisson_bracket J A B) C +
  poisson_bracket J (poisson_bracket J B C) A +
  poisson_bracket J (poisson_bracket J C A) B = 0
-/

def poisson_bracket {n : ℕ} (J A B : Matrix (Fin n) (Fin n) ℝ) : Matrix (Fin n) (Fin n) ℝ :=
  A * J * B - B * J * A

theorem poisson_bracket_anticomm {n : ℕ} (J A B : Matrix (Fin n) (Fin n) ℝ) :
    poisson_bracket J A B = - poisson_bracket J B A := by
  unfold poisson_bracket
  simp only [neg_sub]

theorem poisson_bracket_jacobi {n : ℕ} (J A B C : Matrix (Fin n) (Fin n) ℝ) :
    poisson_bracket J (poisson_bracket J A B) C +
    poisson_bracket J (poisson_bracket J B C) A +
    poisson_bracket J (poisson_bracket J C A) B = 0 := by
  unfold poisson_bracket
  simp only [sub_mul, mul_sub, mul_assoc]
  abel

#print axioms poisson_bracket_anticomm
#print axioms poisson_bracket_jacobi
