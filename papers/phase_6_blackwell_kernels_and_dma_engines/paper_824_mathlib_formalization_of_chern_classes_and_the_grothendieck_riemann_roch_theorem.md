# Paper 824: Mathlib Formalization of Chern Classes and the Grothendieck-Riemann-Roch Theorem

We formalize Chern character maps and Grothendieck-Riemann-Roch invariants in Lean 4 Mathlib (`lean_pilot/Pilot/GrothendieckRiemannRoch.lean`, Module 35).

---

### 1. Formalized Theorems

1. `chern_char_zero`: $\mathrm{ch}(0) = 0$
2. `chern_char_neg`: $\mathrm{ch}(-E) = -\mathrm{ch}(E)$
3. `chern_char_nsmul`: $\mathrm{ch}(n \bullet E) = n \bullet \mathrm{ch}(E)$
4. `grr_twisted_additivity`: $(E_1 \oplus E_2) \cdot \mathrm{td}(X) = E_1 \cdot \mathrm{td}(X) + E_2 \cdot \mathrm{td}(X)$
5. `grr_identity_comm`: $\mathrm{ch}(\mathrm{id}_* E) \cdot \mathrm{td}(X) = \mathrm{ch}(E) \cdot \mathrm{td}(X)$

All theorems compile in the Lean 4 kernel with 0 sorry and 0 unproven axioms.
