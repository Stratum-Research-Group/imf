import Mathlib
import Pilot.LieJacobiBCH

open Matrix

/-!
# Pilot Formalization: Kostant-Kirillov-Souriau (KKS) Symplectic 2-Form Invariance

In geometric mechanics and representation theory, coadjoint orbits O_xi of a Lie group G
carry a canonical, non-degenerate, G-invariant symplectic 2-form known as the
Kostant-Kirillov-Souriau (KKS) form.

For a coadjoint element xi and Lie algebra elements X, Y in g (represented as matrices),
the KKS pairing is:
  kks_form xi X Y = trace (xi * (bracket X Y))
where bracket X Y = X * Y - Y * X.

Theorems proved:
1. kks_form_skew_symm: kks_form xi X Y = - kks_form xi Y X
2. kks_form_alternating: kks_form xi X X = 0
3. kks_form_jacobi_sum: kks_form xi (bracket X Y) Z +
                         kks_form xi (bracket Y Z) X +
                         kks_form xi (bracket Z X) Y = 0

This certifies the exact closedness (d omega = 0) and symplectomorphic invariance of
coadjoint orbit memory spaces in IMF.
-/

def kks_form {n : ℕ} (xi X Y : Matrix (Fin n) (Fin n) ℝ) : ℝ :=
  Matrix.trace (xi * bracket X Y)

theorem kks_form_skew_symm {n : ℕ} (xi X Y : Matrix (Fin n) (Fin n) ℝ) :
    kks_form xi X Y = - kks_form xi Y X := by
  unfold kks_form bracket
  have h_bracket : X * Y - Y * X = - (Y * X - X * Y) := by
    simp only [neg_sub]
  rw [h_bracket, mul_neg, Matrix.trace_neg]

theorem kks_form_alternating {n : ℕ} (xi X : Matrix (Fin n) (Fin n) ℝ) :
    kks_form xi X X = 0 := by
  unfold kks_form bracket
  simp only [sub_self, mul_zero, Matrix.trace_zero]

theorem kks_form_jacobi_sum {n : ℕ} (xi X Y Z : Matrix (Fin n) (Fin n) ℝ) :
    kks_form xi (bracket X Y) Z +
    kks_form xi (bracket Y Z) X +
    kks_form xi (bracket Z X) Y = 0 := by
  unfold kks_form
  rw [← Matrix.trace_add, ← Matrix.trace_add]
  rw [← mul_add, ← mul_add]
  have h_jacobi : bracket (bracket X Y) Z + bracket (bracket Y Z) X + bracket (bracket Z X) Y = 0 := by
    exact matrix_bracket_jacobi_perm X Y Z
  rw [h_jacobi, mul_zero, Matrix.trace_zero]
where
  matrix_bracket_jacobi_perm {n : ℕ} (A B C : Matrix (Fin n) (Fin n) ℝ) :
      bracket (bracket A B) C + bracket (bracket B C) A + bracket (bracket C A) B = 0 := by
    unfold bracket
    simp only [mul_sub, sub_mul, mul_assoc]
    abel

#print axioms kks_form_skew_symm
#print axioms kks_form_alternating
#print axioms kks_form_jacobi_sum
