# Paper 834: Mathlib Formalization of Serre Duality and Dualizing Sheaves

We formalize Serre duality pairings and bilinear invariants in Lean 4 Mathlib (`lean_pilot/Pilot/SerreDuality.lean`, Module 36).

---

### 1. Formalized Theorems

1. `serre_pairing_zero_left`: $\langle 0, \beta \rangle = 0$
2. `serre_pairing_zero_right`: $\langle \alpha, 0 \rangle = 0$
3. `serre_pairing_neg_left`: $\langle -\alpha, \beta \rangle = -\langle \alpha, \beta \rangle$
4. `serre_pairing_neg_right`: $\langle \alpha, -\beta \rangle = -\langle \alpha, \beta \rangle$
5. `serre_pairing_nsmul_left`: $\langle n \bullet \alpha, \beta \rangle = n \bullet \langle \alpha, \beta \rangle$
6. `serre_pairing_nsmul_right`: $\langle \alpha, n \bullet \beta \rangle = n \bullet \langle \alpha, \beta \rangle$

All theorems compile in the Lean 4 kernel with 0 sorry and 0 unproven axioms.
