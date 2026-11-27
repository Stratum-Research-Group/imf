import Mathlib

/-!
# Pilot Formalization: Tate Bilinear Pairing & Isogeny Arithmetic Invariants

In arithmetic geometry and cryptanalytic lattice theory, the Tate pairing (and Weil pairing)
defines a non-degenerate bilinear map from the torsion points of an elliptic curve or abelian variety
to the roots of unity in an extension field:
  e : E[r] × E[r] → μ_r

The pairing satisfies the fundamental axioms of bi-additivity:
  e(P₁ + P₂, Q) = e(P₁, Q) * e(P₂, Q)
  e(P, Q₁ + Q₂) = e(P, Q₁) * e(P, Q₂)

From these core relations, we deductively prove:
1. `tate_pairing_zero_left`: e(0, Q) = 1
2. `tate_pairing_zero_right`: e(P, 0) = 1
3. `tate_pairing_neg_left`: e(-P, Q) = (e(P, Q))⁻¹
4. `tate_pairing_neg_right`: e(P, -Q) = (e(P, Q))⁻¹
5. `tate_pairing_nsmul_left`: e(n • P, Q) = e(P, Q)^n for all n ∈ ℕ
6. `tate_pairing_nsmul_right`: e(P, n • Q) = e(P, Q)^n for all n ∈ ℕ
7. `tate_pairing_bilinear_nsmul`: e(a • P, b • Q) = (e(P, Q))^(a * b)

All theorems are certified with zero unproven clauses and standard Mathlib axioms.
-/

variable {G₁ G₂ : Type*} [AddCommGroup G₁] [AddCommGroup G₂]
variable {G_T : Type*} [CommGroup G_T]

structure BilinearPairing (e : G₁ → G₂ → G_T) : Prop where
  add_left : ∀ P₁ P₂ Q, e (P₁ + P₂) Q = e P₁ Q * e P₂ Q
  add_right : ∀ P Q₁ Q₂, e P (Q₁ + Q₂) = e P Q₁ * e P Q₂

theorem tate_pairing_zero_left {e : G₁ → G₂ → G_T} (bp : BilinearPairing e) (Q : G₂) :
    e 0 Q = 1 := by
  have h := bp.add_left 0 0 Q
  rw [add_zero] at h
  have h2 : e 0 Q * e 0 Q = e 0 Q * 1 := by rw [mul_one, ← h]
  exact mul_left_cancel h2

theorem tate_pairing_zero_right {e : G₁ → G₂ → G_T} (bp : BilinearPairing e) (P : G₁) :
    e P 0 = 1 := by
  have h := bp.add_right P 0 0
  rw [add_zero] at h
  have h2 : e P 0 * e P 0 = e P 0 * 1 := by rw [mul_one, ← h]
  exact mul_left_cancel h2

theorem tate_pairing_neg_left {e : G₁ → G₂ → G_T} (bp : BilinearPairing e) (P : G₁) (Q : G₂) :
    e (-P) Q = (e P Q)⁻¹ := by
  have h := bp.add_left (-P) P Q
  rw [neg_add_cancel, tate_pairing_zero_left bp Q] at h
  exact eq_inv_of_mul_eq_one_left h.symm

theorem tate_pairing_neg_right {e : G₁ → G₂ → G_T} (bp : BilinearPairing e) (P : G₁) (Q : G₂) :
    e P (-Q) = (e P Q)⁻¹ := by
  have h := bp.add_right P (-Q) Q
  rw [neg_add_cancel, tate_pairing_zero_right bp P] at h
  exact eq_inv_of_mul_eq_one_left h.symm

theorem tate_pairing_nsmul_left {e : G₁ → G₂ → G_T} (bp : BilinearPairing e) (P : G₁) (Q : G₂) (n : ℕ) :
    e (n • P) Q = (e P Q) ^ n := by
  induction' n with k ih
  · simp only [zero_smul, pow_zero]
    exact tate_pairing_zero_left bp Q
  · rw [succ_nsmul, bp.add_left, ih, pow_succ, mul_comm]

theorem tate_pairing_nsmul_right {e : G₁ → G₂ → G_T} (bp : BilinearPairing e) (P : G₁) (Q : G₂) (n : ℕ) :
    e P (n • Q) = (e P Q) ^ n := by
  induction' n with k ih
  · simp only [zero_smul, pow_zero]
    exact tate_pairing_zero_right bp P
  · rw [succ_nsmul, bp.add_right, ih, pow_succ, mul_comm]

theorem tate_pairing_bilinear_nsmul {e : G₁ → G₂ → G_T} (bp : BilinearPairing e) (P : G₁) (Q : G₂) (a b : ℕ) :
    e (a • P) (b • Q) = (e P Q) ^ (a * b) := by
  rw [tate_pairing_nsmul_left bp, tate_pairing_nsmul_right bp, ← pow_mul, mul_comm b a]
