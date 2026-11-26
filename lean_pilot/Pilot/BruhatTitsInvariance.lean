import Mathlib

open Matrix

/-!
# Pilot Formalization: Bruhat-Tits Building Invariants & Affine Reflection Geometry

In the theory of Bruhat-Tits buildings B(G, K) over non-Archimedean local fields K,
apartments are affine Coxeter complexes tessellated by affine root hyperplanes.

For an affine root with normal vector α (α ⬝ᵥ α ≠ 0) and scalar offset c ∈ ℝ,
the affine hyperplane is H_{α, c} = {x | x ⬝ᵥ α = c}.
The affine reflection operator across H_{α, c} is defined by:
  s_{α, c}(x) = x - (2 * (x ⬝ᵥ α - c) / (α ⬝ᵥ α)) • α

We formally certify in Lean 4 Mathlib:
1. `affine_reflection_hyperplane_fixed`:
   If x ⬝ᵥ α = c, then s_{α, c}(x) = x (the affine wall is pointwise fixed).
2. `affine_reflection_involutive`:
   s_{α, c}(s_{α, c}(x)) = x (affine reflection is an involution: s² = 1).
3. `affine_reflection_diff`:
   s_{α, c}(x) - s_{α, c}(y) = (x - y) - (2 * ((x - y) ⬝ᵥ α) / (α ⬝ᵥ α)) • α
   (the difference vector transforms by the linear Coxeter reflection, independent of offset c).
4. `affine_reflection_isometry`:
   (affine_reflection α c x - affine_reflection α c y) ⬝ᵥ
     (affine_reflection α c x - affine_reflection α c y) =
   (x - y) ⬝ᵥ (x - y)
   (affine reflections are strict Euclidean isometries in every apartment).

All theorems certified with ZERO unproven hypotheses and ZERO non-standard axioms.
-/

/-- The affine Coxeter reflection operator associated with root α and offset c -/
noncomputable def affine_reflection {n : ℕ} (α : Fin n → ℝ) (c : ℝ) (x : Fin n → ℝ) : Fin n → ℝ :=
  x - ((2 * (x ⬝ᵥ α - c) / (α ⬝ᵥ α)) • α)

/-- The affine hyperplane is fixed pointwise under affine reflection -/
theorem affine_reflection_hyperplane_fixed {n : ℕ} (α : Fin n → ℝ) (c : ℝ) (x : Fin n → ℝ)
    (h_wall : x ⬝ᵥ α = c) :
    affine_reflection α c x = x := by
  unfold affine_reflection
  rw [h_wall]
  simp only [sub_self, mul_zero, zero_div, zero_smul, sub_zero]

/-- Affine reflection is an involution: s_{α, c}(s_{α, c}(x)) = x -/
theorem affine_reflection_involutive {n : ℕ} (α : Fin n → ℝ) (c : ℝ) (x : Fin n → ℝ)
    (hα : α ⬝ᵥ α ≠ 0) :
    affine_reflection α c (affine_reflection α c x) = x := by
  unfold affine_reflection
  have h_dot : (x - ((2 * (x ⬝ᵥ α - c) / (α ⬝ᵥ α)) • α)) ⬝ᵥ α - c = - (x ⬝ᵥ α - c) := by
    rw [sub_dotProduct, smul_dotProduct]
    simp only [smul_eq_mul]
    have h_cancel : 2 * (x ⬝ᵥ α - c) / (α ⬝ᵥ α) * (α ⬝ᵥ α) = 2 * (x ⬝ᵥ α - c) := by
      exact div_mul_cancel₀ (2 * (x ⬝ᵥ α - c)) hα
    rw [h_cancel]
    ring
  rw [h_dot]
  have h_scalar : 2 * (- (x ⬝ᵥ α - c)) / (α ⬝ᵥ α) = - (2 * (x ⬝ᵥ α - c) / (α ⬝ᵥ α)) := by
    ring
  rw [h_scalar, neg_smul, sub_neg_eq_add]
  ext i
  simp only [Pi.add_apply, Pi.sub_apply]
  ring

/-- Difference of reflected points is the linear Coxeter reflection of the difference vector -/
theorem affine_reflection_diff {n : ℕ} (α : Fin n → ℝ) (c : ℝ) (x y : Fin n → ℝ) :
    affine_reflection α c x - affine_reflection α c y =
      (x - y) - ((2 * ((x - y) ⬝ᵥ α) / (α ⬝ᵥ α)) • α) := by
  unfold affine_reflection
  ext i
  simp only [Pi.sub_apply, Pi.smul_apply, smul_eq_mul, sub_dotProduct]
  ring

/-- Affine reflections are isometries: distances between points are preserved -/
theorem affine_reflection_isometry {n : ℕ} (α : Fin n → ℝ) (c : ℝ) (x y : Fin n → ℝ)
    (hα : α ⬝ᵥ α ≠ 0) :
    (affine_reflection α c x - affine_reflection α c y) ⬝ᵥ
      (affine_reflection α c x - affine_reflection α c y) =
    (x - y) ⬝ᵥ (x - y) := by
  rw [affine_reflection_diff]
  simp only [sub_dotProduct, dotProduct_sub, smul_dotProduct, dotProduct_smul, smul_eq_mul]
  have h_cancel : 2 * (x ⬝ᵥ α - y ⬝ᵥ α) / (α ⬝ᵥ α) * (α ⬝ᵥ α) = 2 * (x ⬝ᵥ α - y ⬝ᵥ α) :=
    div_mul_cancel₀ (2 * (x ⬝ᵥ α - y ⬝ᵥ α)) hα
  rw [h_cancel]
  have h1 : α ⬝ᵥ x = x ⬝ᵥ α := dotProduct_comm α x
  have h2 : α ⬝ᵥ y = y ⬝ᵥ α := dotProduct_comm α y
  rw [h1, h2]
  ring

#print axioms affine_reflection_hyperplane_fixed
#print axioms affine_reflection_involutive
#print axioms affine_reflection_diff
#print axioms affine_reflection_isometry
