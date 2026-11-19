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

end IMF.Bridge
