import Mathlib
import Pilot.PoissonBracketJacobi

open Matrix

/-!
# Pilot Formalization: Symplectic Gradient Vector Field Commutation

For a symplectic structure matrix J and observable Hamiltonians A and B:
The Hamiltonian vector fields are represented by:
  X_A = J * A
  X_B = J * B

The operator commutator (bracket) of the vector fields is:
  vf_bracket X_A X_B = X_A * X_B - X_B * X_A

Theorem:
  vf_bracket (J * A) (J * B) = J * (poisson_bracket J A B)
where poisson_bracket J A B = A * J * B - B * J * A.

This certifies that the Lie algebra homomorphism between Poisson brackets of Hamiltonians
and Lie commutators of Hamiltonian vector fields holds strictly without gauge anomaly.
-/

def vf_bracket {n : ℕ} (X Y : Matrix (Fin n) (Fin n) ℝ) : Matrix (Fin n) (Fin n) ℝ :=
  X * Y - Y * X

theorem symplectic_vector_field_commutation {n : ℕ} (J A B : Matrix (Fin n) (Fin n) ℝ) :
    vf_bracket (J * A) (J * B) = J * (poisson_bracket J A B) := by
  unfold vf_bracket poisson_bracket
  simp only [mul_sub, mul_assoc]

theorem vf_bracket_anticomm {n : ℕ} (X Y : Matrix (Fin n) (Fin n) ℝ) :
    vf_bracket X Y = - vf_bracket Y X := by
  unfold vf_bracket
  simp only [neg_sub]

#print axioms symplectic_vector_field_commutation
#print axioms vf_bracket_anticomm
