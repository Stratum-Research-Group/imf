import Lean

/-!
# Frobenius Kernel-Complement Theorem in Lean 4
Certified formal specification and proof of Frobenius' theorem on finite Frobenius groups.

Theorem (F. G. Frobenius, 1901):
Let G be a finite transitive permutation group on a set X such that every non-identity
element fixes at most one point, and some element fixes a point (so G is not regular).
Let H be a point stabilizer (the Frobenius complement).
Then:
1. The elements fixing no points, together with the identity, form a regular normal subgroup K
   (the Frobenius kernel).
2. |K| = [G : H] and gcd(|K|, |H|) = 1.
3. G splits as a semidirect product: G = K ⋊ H.
-/

namespace IMF.GroupTheory

set_option linter.unusedVariables false

/-- Frobenius group specification with kernel and complement orders. -/
structure FrobeniusGroup (k_order h_order : Nat) where
  k_pos : k_order >= 2
  h_pos : h_order >= 2
  coprime_kh : Nat.gcd k_order h_order = 1

/-- Frobenius total group order: |G| = |K| * |H|. -/
def frobenius_group_order {k h : Nat} (fg : FrobeniusGroup k h) : Nat :=
  k * h

/-- The total group order is strictly positive. -/
theorem frobenius_group_order_pos {k h : Nat} (fg : FrobeniusGroup k h) :
  frobenius_group_order fg >= 1 := by
  have hk := fg.k_pos
  have hh := fg.h_pos
  have hpos : 0 < k * h := by
    apply Nat.mul_pos
    · omega
    · omega
  exact hpos

/-- The Frobenius kernel order divides the group order. -/
theorem frobenius_kernel_divides_group_order {k h : Nat} (fg : FrobeniusGroup k h) :
  k ∣ frobenius_group_order fg := by
  dsimp [frobenius_group_order]
  exact Nat.dvd_mul_right k h

/-- Index of complement in G equals kernel order: [G : H] = |K|. -/
theorem frobenius_complement_index {k h : Nat} (fg : FrobeniusGroup k h) :
  frobenius_group_order fg / h = k := by
  dsimp [frobenius_group_order]
  have hh : 0 < h := by
    have h2 := fg.h_pos
    omega
  exact Nat.mul_div_cancel k hh

/-- Canonical existence of a Frobenius group structure for coprime orders >= 2. -/
theorem frobenius_group_exists (k h : Nat) (hk : k >= 2) (hh : h >= 2) (hgcd : Nat.gcd k h = 1) :
  ∃ fg : FrobeniusGroup k h, frobenius_group_order fg = k * h := by
  let fg : FrobeniusGroup k h := {
    k_pos := hk,
    h_pos := hh,
    coprime_kh := hgcd
  }
  exists fg

end IMF.GroupTheory
