import Mathlib

open Matrix

/-!
# Pilot Formalization: Grassmann 1-Form Wedge Product Alternation

For any vector 1-forms u, v on ℝⁿ:
The exterior Grassmann 2-blade (u ∧ v) satisfies:
1. (u ∧ v) = - (v ∧ u) (anticommutativity)
2. (u ∧ u) = 0 (alternation)
-/

def grassmann_wedge {n : ℕ} (u v : Fin n → ℝ) : Matrix (Fin n) (Fin n) ℝ :=
  vecMulVec u v - vecMulVec v u

theorem grassmann_wedge_anticomm {n : ℕ} (u v : Fin n → ℝ) :
    grassmann_wedge u v = - grassmann_wedge v u := by
  unfold grassmann_wedge
  simp only [neg_sub]

theorem grassmann_wedge_alternating {n : ℕ} (u : Fin n → ℝ) :
    grassmann_wedge u u = 0 := by
  unfold grassmann_wedge
  rw [sub_self]

#print axioms grassmann_wedge_anticomm
#print axioms grassmann_wedge_alternating
