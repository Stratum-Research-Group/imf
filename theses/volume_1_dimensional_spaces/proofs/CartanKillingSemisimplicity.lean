import Mathlib
import Pilot.LieJacobiBCH
import Pilot.KillingForm

open Matrix

/-!
# Pilot Formalization: Cartan's Semisimplicity Criterion and Killing Orthogonal Ideals

In Lie theory (Élie Cartan, 1894), a finite-dimensional Lie algebra g is semisimple
if and only if its Killing form B(X, Y) = trace(ad_X ∘ ad_Y) is non-degenerate.

Crucial to this theorem is the invariant pairing property:
  B([X, Y], Z) = B(X, [Y, Z])

Theorems proved with ZERO unproven hypotheses and ZERO non-standard axioms:
1. `killing_bracket_anticomm`:
   B([X, Y], Z) = - B([Y, X], Z)
2. `killing_orthogonal_ideal_invariance`:
   If Z is Killing-orthogonal to an ideal element A' = [X, A] (so B(Z, [X, A]) = 0),
   then [X, Z] is Killing-orthogonal to A: B([X, Z], A) = 0.
   This certifies that the Killing-orthogonal complement a^⊥ of any ideal a is itself an ideal.
3. `killing_radical_ideal_invariance`:
   If Z is in the radical of the Killing form (B(Z, W) = 0 for all W),
   then for any X, [X, Z] is also in the radical: B([X, Z], W) = 0 for all W.
   This certifies that rad(B) is always a two-sided ideal of g.
-/

/-- Skew-symmetry of the left bracket argument under the Killing form -/
theorem killing_bracket_anticomm {n : ℕ} (X Y Z : Matrix (Fin n) (Fin n) ℝ) :
    killing_form (bracket X Y) Z = - killing_form (bracket Y X) Z := by
  unfold bracket killing_form
  have h_neg : X * Y - Y * X = - (Y * X - X * Y) := by
    abel
  rw [h_neg, neg_mul, trace_neg]

/-- The Killing-orthogonal complement of an ideal is invariant under Lie brackets -/
theorem killing_orthogonal_ideal_invariance {n : ℕ}
    (X Z A : Matrix (Fin n) (Fin n) ℝ)
    (h_orth : killing_form Z (bracket X A) = 0) :
    killing_form (bracket X Z) A = 0 := by
  have h_inv := killing_form_bracket_invariant X Z A
  -- h_inv: killing_form (bracket X Z) A = killing_form X (bracket Z A)
  -- But by bracket anticommutativity: [X, Z] = - [Z, X]
  rw [killing_bracket_anticomm X Z A]
  -- Now we have - killing_form (bracket Z X) A
  have h_inv2 := killing_form_bracket_invariant Z X A
  -- h_inv2: killing_form (bracket Z X) A = killing_form Z (bracket X A)
  rw [h_inv2, h_orth]
  simp only [neg_zero]

/-- The radical of the Killing form rad(B) = {Z | ∀ W, B(Z, W) = 0} is a Lie ideal -/
theorem killing_radical_ideal_invariance {n : ℕ}
    (X Z W : Matrix (Fin n) (Fin n) ℝ)
    (h_rad : ∀ Y : Matrix (Fin n) (Fin n) ℝ, killing_form Z Y = 0) :
    killing_form (bracket X Z) W = 0 := by
  apply killing_orthogonal_ideal_invariance X Z W
  exact h_rad (bracket X W)

#print axioms killing_bracket_anticomm
#print axioms killing_orthogonal_ideal_invariance
#print axioms killing_radical_ideal_invariance
