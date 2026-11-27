import Mathlib

/-!
# Algebraic core of the Hodge Index Theorem (faithful, Mathlib-based)

NOT the full theorem on surfaces. This proves the linear-algebra core:
for a real symmetric bilinear form `B` with `B h h > 0` that is non-positive on `h^⊥`,
the reversed Cauchy–Schwarz inequality `B d d * B h h ≤ (B d h)^2` holds for all `d`.
The geometric input (negativity on `h^⊥` for the Néron–Severi intersection form)
is a HYPOTHESIS here, not proved.
-/
theorem hodge_index_core {V : Type*} [AddCommGroup V] [Module ℝ V]
    (B : LinearMap.BilinForm ℝ V) (hsymm : ∀ x y, B x y = B y x)
    (h : V) (hpos : 0 < B h h)
    (hneg : ∀ x, B x h = 0 → B x x ≤ 0) (d : V) :
    B d d * B h h ≤ (B d h) ^ 2 := by
  set c := B d h / B h h with hc
  have horth : B (d - c • h) h = 0 := by
    simp only [map_sub, map_smul, LinearMap.sub_apply, LinearMap.smul_apply, smul_eq_mul]
    rw [hc]; field_simp; ring
  have h1 := hneg _ horth
  have : B (d - c • h) (d - c • h) = B d d - 2 * c * B d h + c ^ 2 * B h h := by
    simp only [map_sub, map_smul, LinearMap.sub_apply, LinearMap.smul_apply, smul_eq_mul]
    rw [hsymm h d]; ring
  rw [this, hc] at h1
  have key : B d d - 2 * (B d h / B h h) * B d h + (B d h / B h h) ^ 2 * B h h
      = B d d - (B d h) ^ 2 / B h h := by field_simp; ring
  rw [key] at h1
  have := (sub_nonpos.mp h1)
  exact (le_div_iff₀ hpos).mp this

open Matrix in
theorem orthogonal_exp_skew {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ) (hA : Aᵀ = -A) :
    (NormedSpace.exp A)ᵀ * NormedSpace.exp A = 1 := by
  let _ := Matrix.linftyOpNormedRing (n := Fin n) (α := ℝ)
  let _ := Matrix.linftyOpNormedAlgebra (n := Fin n) (R := ℝ) (α := ℝ)
  let _ : NormedAlgebra ℚ (Matrix (Fin n) (Fin n) ℝ) := NormedAlgebra.restrictScalars ℚ ℝ _
  rw [← Matrix.exp_transpose, hA]
  have h := NormedSpace.exp_add_of_commute (Commute.neg_left (Commute.refl A))
  rw [neg_add_cancel, NormedSpace.exp_zero] at h
  exact h.symm

#print axioms hodge_index_core
#print axioms orthogonal_exp_skew
