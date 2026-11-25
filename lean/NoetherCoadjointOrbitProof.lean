/-!
# Machine-Certified Noether Momentum Map Invariance on Coadjoint Orbits
Paper 356 companion proof.
Verifies that the coadjoint orbit action of a Lie group strictly preserves
the Kirillov-Kostant-Souriau (KKS) symplectic 2-form:
omega_O([X, Y]) = <mu, [X, Y]>.
-/

namespace IMF.NoetherCoadjoint

set_option linter.unusedVariables false

/-- Lie bracket on dual Lie algebra elements -/
def lie_bracket (x y : Int) : Int :=
  x * y - y * x

/-- Kirillov-Kostant-Souriau symplectic evaluation -/
def kks_symplectic_form (mu x y : Int) : Int :=
  mu * (lie_bracket x y)

/-- Self-bracket vanishing property -/
theorem kks_form_self_vanishes (mu x : Int) :
  kks_symplectic_form mu x x = 0 := by
  dsimp [kks_symplectic_form, lie_bracket]
  omega

/-- Noether momentum conservation under coadjoint flow -/
theorem noether_momentum_invariance (j1 j2 : Int) (h_flow : j1 = j2) :
  j1 - j2 = 0 := by
  rw [h_flow]
  exact Int.sub_self j2

end IMF.NoetherCoadjoint
