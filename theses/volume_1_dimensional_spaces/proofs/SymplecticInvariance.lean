import Mathlib
import Pilot.SymplecticBilinear

open Matrix

/-!
# Pilot Formalization: Symplectic Invariance under Hamiltonian Transformations

A linear map S is a symplectic transformation if Sᵀ * J * S = J.
For any such S, the symplectic bilinear form is strictly invariant:
  symplectic_form J (S *ᵥ x) (S *ᵥ y) = symplectic_form J x y
-/

theorem symplectic_transformation_invariant {n : ℕ} (J S : Matrix (Fin n) (Fin n) ℝ)
    (hS : Sᵀ * J * S = J) (x y : Fin n → ℝ) :
    (S *ᵥ x) ⬝ᵥ (J *ᵥ (S *ᵥ y)) = x ⬝ᵥ (J *ᵥ y) := by
  have h1 : (S *ᵥ x) ⬝ᵥ (J *ᵥ (S *ᵥ y)) = (J *ᵥ (S *ᵥ y)) ⬝ᵥ (S *ᵥ x) := dotProduct_comm (S *ᵥ x) (J *ᵥ (S *ᵥ y))
  have h2 : (J *ᵥ (S *ᵥ y)) ⬝ᵥ (S *ᵥ x) = ((J *ᵥ (S *ᵥ y)) ᵥ* S) ⬝ᵥ x := dotProduct_mulVec (J *ᵥ (S *ᵥ y)) S x
  have h3 : (J *ᵥ (S *ᵥ y)) ᵥ* S = Sᵀ *ᵥ (J *ᵥ (S *ᵥ y)) := (mulVec_transpose S (J *ᵥ (S *ᵥ y))).symm
  rw [h1, h2, h3, dotProduct_comm]
  rw [mulVec_mulVec y J S]
  rw [mulVec_mulVec y Sᵀ (J * S)]
  rw [← mul_assoc Sᵀ J S, hS]

theorem symplectic_form_preserved {n : ℕ} (J S : Matrix (Fin n) (Fin n) ℝ)
    (hS : Sᵀ * J * S = J) (x y : Fin n → ℝ) :
    symplectic_form J (S *ᵥ x) (S *ᵥ y) = symplectic_form J x y := by
  unfold symplectic_form
  exact symplectic_transformation_invariant J S hS x y

#print axioms symplectic_transformation_invariant
#print axioms symplectic_form_preserved
