import Mathlib

open Matrix

/-!
# Pilot Formalization: Coxeter Reflection Group Invariance & Root Symmetries

In Lie algebra root systems and Coxeter groups (such as the Weyl groups of
E6, E7, E8, and Kac-Moody E10), reflections across root hyperplanes generate
the discrete symmetry group of the polytope.

For a non-zero root vector α with α ⬝ᵥ α ≠ 0, the Coxeter reflection is defined by:
  s_α(x) = x - (2 * (x ⬝ᵥ α) / (α ⬝ᵥ α)) • α

We formally certify in Lean 4 Mathlib:
1. `coxeter_reflection_root`:
   s_α(α) = -α (the root itself is reversed).
2. `coxeter_reflection_orthogonal`:
   If x ⬝ᵥ α = 0, then s_α(x) = x (the root hyperplane is pointwise fixed).
3. `coxeter_reflection_involutive`:
   s_α(s_α(x)) = x (Coxeter reflection is an involution of order 2: s_α² = 1).
4. `coxeter_reflection_isometry`:
   (s_α(x)) ⬝ᵥ (s_α(y)) = x ⬝ᵥ y (Coxeter reflections are orthogonal isometries).

Theorems proved with ZERO unproven hypotheses and ZERO non-standard axioms.
-/

/-- The Coxeter reflection operator associated with root vector α -/
noncomputable def coxeter_reflection {n : ℕ} (α x : Fin n → ℝ) : Fin n → ℝ :=
  x - ((2 * (x ⬝ᵥ α) / (α ⬝ᵥ α)) • α)

/-- Reflection of the root vector reverses its direction: s_α(α) = -α -/
theorem coxeter_reflection_root {n : ℕ} (α : Fin n → ℝ) (hα : α ⬝ᵥ α ≠ 0) :
    coxeter_reflection α α = - α := by
  unfold coxeter_reflection
  have h_div : 2 * (α ⬝ᵥ α) / (α ⬝ᵥ α) = 2 := by
    exact mul_div_cancel_right₀ 2 hα
  rw [h_div]
  ext i
  simp only [Pi.sub_apply, Pi.smul_apply, Pi.neg_apply, smul_eq_mul]
  ring

/-- The orthogonal hyperplane is fixed pointwise under Coxeter reflection -/
theorem coxeter_reflection_orthogonal {n : ℕ} (α x : Fin n → ℝ) (h_orth : x ⬝ᵥ α = 0) :
    coxeter_reflection α x = x := by
  unfold coxeter_reflection
  rw [h_orth]
  simp only [mul_zero, zero_div, zero_smul, sub_zero]

/-- Coxeter reflection is an involution: s_α(s_α(x)) = x -/
theorem coxeter_reflection_involutive {n : ℕ} (α x : Fin n → ℝ) (hα : α ⬝ᵥ α ≠ 0) :
    coxeter_reflection α (coxeter_reflection α x) = x := by
  unfold coxeter_reflection
  have h_dot : (x - ((2 * (x ⬝ᵥ α) / (α ⬝ᵥ α)) • α)) ⬝ᵥ α = - (x ⬝ᵥ α) := by
    rw [sub_dotProduct, smul_dotProduct]
    simp only [smul_eq_mul]
    have h_cancel : 2 * (x ⬝ᵥ α) / (α ⬝ᵥ α) * (α ⬝ᵥ α) = 2 * (x ⬝ᵥ α) := by
      exact div_mul_cancel₀ (2 * (x ⬝ᵥ α)) hα
    rw [h_cancel]
    ring
  rw [h_dot]
  have h_scalar : 2 * (- (x ⬝ᵥ α)) / (α ⬝ᵥ α) = - (2 * (x ⬝ᵥ α) / (α ⬝ᵥ α)) := by
    ring
  rw [h_scalar, neg_smul, sub_neg_eq_add]
  ext i
  simp only [Pi.add_apply, Pi.sub_apply]
  ring

/-- Coxeter reflections preserve Euclidean inner products (orthogonal isometries) -/
theorem coxeter_reflection_isometry {n : ℕ} (α x y : Fin n → ℝ) (hα : α ⬝ᵥ α ≠ 0) :
    (coxeter_reflection α x) ⬝ᵥ (coxeter_reflection α y) = x ⬝ᵥ y := by
  unfold coxeter_reflection
  rw [sub_dotProduct, dotProduct_sub, dotProduct_sub]
  simp only [smul_dotProduct, dotProduct_smul, smul_eq_mul]
  have h_symm : α ⬝ᵥ y = y ⬝ᵥ α := dotProduct_comm α y
  rw [h_symm]
  have h_cancel : 2 * (x ⬝ᵥ α) / (α ⬝ᵥ α) * (α ⬝ᵥ α) = 2 * (x ⬝ᵥ α) :=
    div_mul_cancel₀ (2 * (x ⬝ᵥ α)) hα
  rw [h_cancel]
  ring

#print axioms coxeter_reflection_root
#print axioms coxeter_reflection_orthogonal
#print axioms coxeter_reflection_involutive
#print axioms coxeter_reflection_isometry
