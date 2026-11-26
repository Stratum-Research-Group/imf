# Paper 814: Mathlib Formalization of Arakelov Intersection Theory and Arithmetic Heights

We formalize the algebraic and geometric foundations of Arakelov intersection theory in Lean 4 Mathlib (`lean_pilot/Pilot/ArakelovIntersection.lean`, Module 34).

---

### 1. Formalized Theorems

1. `arakelov_pairing_zero_left`: $(0, D)_{\mathrm{Ar}} = 0$
2. `arakelov_pairing_zero_right`: $(D, 0)_{\mathrm{Ar}} = 0$
3. `arakelov_pairing_neg_left`: $(-D_1, D_2)_{\mathrm{Ar}} = -(D_1, D_2)_{\mathrm{Ar}}$
4. `arakelov_pairing_neg_right`: $(D_1, -D_2)_{\mathrm{Ar}} = -(D_1, D_2)_{\mathrm{Ar}}$
5. `arakelov_pairing_nsmul_left`: $(n \bullet D_1, D_2)_{\mathrm{Ar}} = n \bullet (D_1, D_2)_{\mathrm{Ar}}$
6. `arakelov_quadratic_expansion`: $(D_1 + D_2, D_1 + D_2)_{\mathrm{Ar}} = (D_1, D_1)_{\mathrm{Ar}} + 2 \bullet (D_1, D_2)_{\mathrm{Ar}} + (D_2, D_2)_{\mathrm{Ar}}$ (Faltings quadratic formula)

All theorems compile in the Lean 4 kernel with 0 sorry and 0 unproven axioms.
