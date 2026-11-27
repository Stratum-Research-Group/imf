import Mathlib

open Matrix

/-!
# Cayley transform of a real skew-symmetric matrix is orthogonal (faithful, Mathlib-based)
-/

theorem skew_quadratic_zero {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ) (hA : Aᵀ = -A)
    (x : Fin n → ℝ) : x ⬝ᵥ (A *ᵥ x) = 0 := by
  have h1 : x ⬝ᵥ (A *ᵥ x) = (Aᵀ *ᵥ x) ⬝ᵥ x := by
    rw [dotProduct_mulVec, ← mulVec_transpose]
  have h2 : (Aᵀ *ᵥ x) ⬝ᵥ x = - (x ⬝ᵥ (A *ᵥ x)) := by
    rw [hA, neg_mulVec, neg_dotProduct, dotProduct_comm]
  have h3 : x ⬝ᵥ (A *ᵥ x) = - (x ⬝ᵥ (A *ᵥ x)) := h1.trans h2
  linarith

theorem one_add_skew_isUnit {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ) (hA : Aᵀ = -A) :
    IsUnit (1 + A) := by
  rw [← Matrix.mulVec_injective_iff_isUnit]
  intro x y hxy
  have hz : (1 + A) *ᵥ (x - y) = 0 := by rw [mulVec_sub, hxy, sub_self]
  set z := x - y with hzdef
  have hAz : A *ᵥ z = -z := by
    have : z + A *ᵥ z = 0 := by simpa [add_mulVec] using hz
    exact eq_neg_of_add_eq_zero_right this
  have hq := skew_quadratic_zero A hA z
  rw [hAz, dotProduct_neg, neg_eq_zero] at hq
  have : z = 0 := dotProduct_self_eq_zero.mp hq
  exact sub_eq_zero.mp this

theorem cayley_orthogonal {n : ℕ} (A : Matrix (Fin n) (Fin n) ℝ) (hA : Aᵀ = -A) :
    ((1 + A)⁻¹ * (1 - A))ᵀ * ((1 + A)⁻¹ * (1 - A)) = 1 := by
  have hu : IsUnit (1 + A) := one_add_skew_isUnit A hA
  have hA' : (-A)ᵀ = -(-A) := by simp [hA]
  have hv : IsUnit (1 + -A) := one_add_skew_isUnit (-A) (by simpa using hA')
  have hsub : (1 - A) = 1 + -A := by abel
  have hT : (1 + A)ᵀ = 1 - A := by simp [transpose_add, hA, sub_eq_add_neg]
  have hcomm : Commute (1 + A) (1 - A) := by
    show (1 + A) * (1 - A) = (1 - A) * (1 + A)
    simp only [mul_sub, sub_mul, add_mul, mul_add, one_mul, mul_one]
    abel
  have hu' : IsUnit (1 - A) := hsub ▸ hv
  have hdu : IsUnit (1 + A).det := (isUnit_iff_isUnit_det _).mp hu
  have hdv : IsUnit (1 - A).det := (isUnit_iff_isUnit_det _).mp hu'
  have hT2 : (1 - A)ᵀ = 1 + A := by simp [transpose_sub, hA]
  rw [transpose_mul, transpose_nonsing_inv, hT, hT2]
  have e1 : (1 + A)⁻¹ * (1 + A) = 1 := nonsing_inv_mul _ hdu
  have e2 : (1 - A) * (1 - A)⁻¹ = 1 := mul_nonsing_inv _ hdv
  have e3 : (1 - A)⁻¹ * (1 - A) = 1 := nonsing_inv_mul _ hdv
  have e4 : (1 + A) * (1 + A)⁻¹ = 1 := mul_nonsing_inv _ hdu
  have hc2 : (1 - A)⁻¹ * (1 + A) = (1 + A) * (1 - A)⁻¹ := by
    calc (1 - A)⁻¹ * (1 + A) = (1 - A)⁻¹ * (1 + A) * ((1 - A) * (1 - A)⁻¹) := by rw [e2, mul_one]
      _ = (1 - A)⁻¹ * ((1 + A) * (1 - A)) * (1 - A)⁻¹ := by simp only [mul_assoc]
      _ = (1 - A)⁻¹ * ((1 - A) * (1 + A)) * (1 - A)⁻¹ := by rw [hcomm.eq]
      _ = (1 + A) * (1 - A)⁻¹ := by
        rw [← mul_assoc, e3, one_mul]
  rw [← hc2, mul_assoc, ← mul_assoc (1 + A), e4, one_mul, e3]

#print axioms cayley_orthogonal
