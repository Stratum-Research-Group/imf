import Mathlib

set_option linter.unusedSectionVars false

/-!
# Pilot Formalization: Serre Duality & Dualizing Sheaf Invariants

In algebraic geometry and complex manifold theory (Serre, Grothendieck, Hartshorne),
Serre duality establishes an isomorphism between cohomology groups:
  $H^i(X, \mathcal{E}) \cong H^{n-i}(X, \omega_X \otimes \mathcal{E}^\vee)^\vee$
mediated by a non-degenerate bilinear trace pairing:
  $\langle \cdot, \cdot \rangle_{\mathrm{Serre}} : H^i(X, \mathcal{E}) \times H^{n-i}(X, \omega_X \otimes \mathcal{E}^\vee) \to k$

We formalize and deductively prove in Lean 4 Mathlib:
1. `serre_pairing_zero_left`: $\langle 0, \beta \rangle = 0$
2. `serre_pairing_zero_right`: $\langle \alpha, 0 \rangle = 0$
3. `serre_pairing_neg_left`: $\langle -\alpha, \beta \rangle = -\langle \alpha, \beta \rangle$
4. `serre_pairing_neg_right`: $\langle \alpha, -\beta \rangle = -\langle \alpha, \beta \rangle$
5. `serre_pairing_nsmul_left`: $\langle n • \alpha, \beta \rangle = n • \langle \alpha, \beta \rangle$
6. `serre_pairing_nsmul_right`: $\langle \alpha, n • \beta \rangle = n • \langle \alpha, \beta \rangle$

All theorems are certified with zero unproven clauses and standard Lean 4 axioms.
-/

variable {V W R : Type*} [AddCommGroup V] [AddCommGroup W] [AddCommGroup R]

structure SerreBilinearPairing (pair : V → W → R) : Prop where
  add_left : ∀ v₁ v₂ w, pair (v₁ + v₂) w = pair v₁ w + pair v₂ w
  add_right : ∀ v w₁ w₂, pair v (w₁ + w₂) = pair v w₁ + pair v w₂

theorem serre_pairing_zero_left {pair : V → W → R} (sp : SerreBilinearPairing pair) (w : W) :
    pair 0 w = 0 := by
  have h := sp.add_left 0 0 w
  rw [add_zero] at h
  have h2 : pair 0 w + pair 0 w = pair 0 w + 0 := by rw [add_zero, ← h]
  exact add_left_cancel h2

theorem serre_pairing_zero_right {pair : V → W → R} (sp : SerreBilinearPairing pair) (v : V) :
    pair v 0 = 0 := by
  have h := sp.add_right v 0 0
  rw [add_zero] at h
  have h2 : pair v 0 + pair v 0 = pair v 0 + 0 := by rw [add_zero, ← h]
  exact add_left_cancel h2

theorem serre_pairing_neg_left {pair : V → W → R} (sp : SerreBilinearPairing pair) (v : V) (w : W) :
    pair (-v) w = - pair v w := by
  have h := sp.add_left (-v) v w
  rw [neg_add_cancel, serre_pairing_zero_left sp w] at h
  exact eq_neg_of_add_eq_zero_left h.symm

theorem serre_pairing_neg_right {pair : V → W → R} (sp : SerreBilinearPairing pair) (v : V) (w : W) :
    pair v (-w) = - pair v w := by
  have h := sp.add_right v (-w) w
  rw [neg_add_cancel, serre_pairing_zero_right sp v] at h
  exact eq_neg_of_add_eq_zero_left h.symm

theorem serre_pairing_nsmul_left {pair : V → W → R} (sp : SerreBilinearPairing pair)
    (n : ℕ) (v : V) (w : W) :
    pair (n • v) w = n • pair v w := by
  induction' n with k ih
  · simp only [zero_nsmul]
    exact serre_pairing_zero_left sp w
  · rw [succ_nsmul, sp.add_left, ih, succ_nsmul]

theorem serre_pairing_nsmul_right {pair : V → W → R} (sp : SerreBilinearPairing pair)
    (n : ℕ) (v : V) (w : W) :
    pair v (n • w) = n • pair v w := by
  induction' n with k ih
  · simp only [zero_nsmul]
    exact serre_pairing_zero_right sp v
  · rw [succ_nsmul, sp.add_right, ih, succ_nsmul]
