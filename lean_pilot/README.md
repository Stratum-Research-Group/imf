# lean_pilot — faithful Mathlib-based formalizations

Separate Lake project (Lean v4.33.1 + Mathlib v4.33.1). Build: `lake exe cache get && lake build`.
Axioms checked with `#print axioms`: only `propext`, `Classical.choice`, `Quot.sound`. No `sorry`.

| File | Theorem | Scope |
|:--|:--|:--|
| `Pilot/HodgeIndexCore.lean` | `hodge_index_core` | Linear-algebra core of the Hodge Index Theorem (reverse Cauchy–Schwarz for a form negative on h^⊥). Negativity on h^⊥ for the Néron–Severi form is a hypothesis, NOT proved. |
| `Pilot/HodgeIndexCore.lean` | `orthogonal_exp_skew` | exp(A)ᵀ·exp(A)=1 for real skew-symmetric A (genuine statement over Mathlib's matrix exponential). |
| `Pilot/CayleyOrthogonal.lean` | `cayley_orthogonal` (+ `one_add_skew_isUnit`, `skew_quadratic_zero`) | For real skew A: 1+A invertible and the Cayley transform is orthogonal. |

Status: pilot of 4 results (Hodge-index core, exp skew, Cayley orthogonal + lemmas). Paper 596 is rebuilt on these.
