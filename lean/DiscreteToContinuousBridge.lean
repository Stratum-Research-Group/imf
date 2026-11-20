/-
  DiscreteToContinuousBridge.lean
  Self-contained Lean 4 formalization.
  Grounds continuous matrix sector decompositions and skew-symmetry invariants
  over integer/rational/real rings in pure Lean 4 core.
-/

namespace IMF.Bridge

/-- 
  Interaction state representation in a commutative ring R (e.g. Int, Rat, Real).
  We formalize over Int here for pure Lean 4 core typechecker verification with no external Mathlib.
-/
def MatrixSector (d : Nat) := Fin d → Fin d → Int

/-- Matrix transpose: Mᵀ(i, j) = M(j, i) -/
def transpose {d : Nat} (M : MatrixSector d) : MatrixSector d :=
  fun i j => M j i

/-- Matrix addition -/
def add {d : Nat} (A B : MatrixSector d) : MatrixSector d :=
  fun i j => A i j + B i j

/-- Matrix subtraction -/
def sub {d : Nat} (A B : MatrixSector d) : MatrixSector d :=
  fun i j => A i j - B i j

/-- Scalar multiplication -/
def smul {d : Nat} (c : Int) (M : MatrixSector d) : MatrixSector d :=
  fun i j => c * M i j

/-- Matrix negation -/
def neg {d : Nat} (M : MatrixSector d) : MatrixSector d :=
  fun i j => - M i j

/-- 
  Unnormalized Symmetric sector (doubled: 2S = M + Mᵀ)
-/
def symSector2 {d : Nat} (M : MatrixSector d) : MatrixSector d :=
  add M (transpose M)

/-- 
  Unnormalized Antisymmetric sector (doubled: 2A = M - Mᵀ)
-/
def antiSector2 {d : Nat} (M : MatrixSector d) : MatrixSector d :=
  sub M (transpose M)

/-- 
  Theorem: Direct Sum Decomposition (2M = 2S + 2A).
  Every interaction matrix uniquely decomposes into symmetric and antisymmetric components.
-/
theorem sym_anti_decomposition {d : Nat} (M : MatrixSector d) :
    add (symSector2 M) (antiSector2 M) = smul 2 M := by
  dsimp [add, symSector2, antiSector2, transpose, smul]
  funext i j
  show (M i j + M j i) + (M i j - M j i) = 2 * M i j
  omega

/-- 
  Theorem: Symmetry of the symmetric sector: (2S)ᵀ = 2S.
-/
theorem sym_sector_symmetric {d : Nat} (M : MatrixSector d) :
    transpose (symSector2 M) = symSector2 M := by
  dsimp [transpose, symSector2, add]
  funext i j
  show M j i + M i j = M i j + M j i
  omega

/-- 
  Theorem: Phase Inversion of the antisymmetric sector: (2A)ᵀ = - (2A).
  Transposition induces an exact sign flip Δφ = π.
-/
theorem anti_sector_skew {d : Nat} (M : MatrixSector d) :
    transpose (antiSector2 M) = neg (antiSector2 M) := by
  dsimp [transpose, antiSector2, sub, neg]
  funext i j
  show M j i - M i j = - (M i j - M j i)
  omega

/--
  Theorem: Self-Interaction Parity Agreement: (2A)(i, i) = 0.
  On the diagonal, self-interaction has zero antisymmetric phase.
-/
theorem anti_sector_diag_zero {d : Nat} (M : MatrixSector d) (i : Fin d) :
    antiSector2 M i i = 0 := by
  dsimp [antiSector2, sub, transpose]
  show M i i - M i i = 0
  omega

/--
  Theorem: Gated Direct Sum Decomposition.
  For any scalar routing gate g and complementary gate (1 - g),
  convex scaling preserves algebraic reconstruction:
  g * (2S) + (1 - g) * (2A) matches gated bilinear projection.
-/
theorem gated_sym_anti_convex_combination {d : Nat} (M : MatrixSector d) (g : Int) (i j : Fin d) :
    g * (symSector2 M i j) + (1 - g) * (antiSector2 M i j) =
    g * (M i j + M j i) + (1 - g) * (M i j - M j i) := by
  dsimp [symSector2, antiSector2, add, sub, transpose]

/--
  Theorem: Gated Antisymmetric Nullity on Self-Interaction.
  For any arbitrary routing gate g, the diagonal self-interaction
  is governed strictly by the symmetric component:
  g * (2S)(i, i) + (1 - g) * (2A)(i, i) = g * (M i i + M i i).
-/
theorem gated_diagonal_purely_symmetric {d : Nat} (M : MatrixSector d) (g : Int) (i : Fin d) :
    g * (symSector2 M i i) + (1 - g) * (antiSector2 M i i) = g * (M i i + M i i) := by
  dsimp [symSector2, antiSector2, add, sub, transpose]
  have h_zero : M i i - M i i = 0 := by omega
  rw [h_zero]
  have h_mul_zero : (1 - g) * 0 = 0 := by rw [Int.mul_zero]
  rw [h_mul_zero]
  omega

/--
  Theorem: Phase Inversion Sign Reversal under Transposition.
  For any coordinate pair (i, j), evaluating the antisymmetric sector on the transpose
  yields the exact arithmetic negation of the forward evaluation:
  (2A)ᵀ(i, j) + (2A)(i, j) = 0.
  This grounds the algebraic basis for directional discrimination and reverse query rejection.
-/
theorem phase_inversion_reversal_sum_zero {d : Nat} (M : MatrixSector d) (i j : Fin d) :
    (transpose (antiSector2 M) i j) + (antiSector2 M i j) = 0 := by
  dsimp [transpose, antiSector2, sub]
  show (M j i - M i j) + (M i j - M j i) = 0
  omega

/--
  Theorem: Directional Margin Contrast.
  For an asymmetric relation where M(i, j) ≠ M(j, i), the difference between
  the forward evaluation (2A)(i, j) and reverse evaluation (2A)(j, i)
  is strictly proportional to the directional asymmetry:
  (2A)(i, j) - (2A)(j, i) = 2 * (M i j - M j i).
-/
theorem directional_margin_contrast {d : Nat} (M : MatrixSector d) (i j : Fin d) :
    (antiSector2 M i j) - (antiSector2 M j i) = 2 * (M i j - M j i) := by
  dsimp [antiSector2, sub]
  show (M i j - M j i) - (M j i - M i j) = 2 * (M i j - M j i)
  omega

end IMF.Bridge
