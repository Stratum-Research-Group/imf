/-
  ContinuousCrossingBounds.lean
  Self-contained Lean 4 formalization.
  Grounds operator orthogonality and trace energy conservation in pure Lean 4 core.
-/

namespace IMF.Proof

/-- 
  Matrix sector representation over integer ring (Fin d → Fin d → Int).
-/
def MatrixSector (d : Nat) := Fin d → Fin d → Int

def transpose {d : Nat} (M : MatrixSector d) : MatrixSector d :=
  fun i j => M j i

def add {d : Nat} (A B : MatrixSector d) : MatrixSector d :=
  fun i j => A i j + B i j

def sub {d : Nat} (A B : MatrixSector d) : MatrixSector d :=
  fun i j => A i j - B i j

def symSector2 {d : Nat} (M : MatrixSector d) : MatrixSector d :=
  add M (transpose M)

def antiSector2 {d : Nat} (M : MatrixSector d) : MatrixSector d :=
  sub M (transpose M)

/--
  Theorem: Diagonal element of the antisymmetric sector is zero.
-/
theorem anti_sector_diag_zero {d : Nat} (M : MatrixSector d) (i : Fin d) :
    antiSector2 M i i = 0 := by
  dsimp [antiSector2, sub, transpose]
  show M i i - M i i = 0
  omega

/--
  Theorem: Direct energy conservation on diagonal.
  For all self-interacting coordinates, total projection is purely symmetric:
  2M(i, i) = 2S(i, i).
-/
theorem self_energy_purely_symmetric {d : Nat} (M : MatrixSector d) (i : Fin d) :
    symSector2 M i i = 2 * M i i := by
  dsimp [symSector2, add, transpose]
  show M i i + M i i = 2 * M i i
  omega

/--
  Theorem: Pointwise Frobenius inner product of Symmetric and Antisymmetric sectors
  cancels to zero across symmetric coordinate pairs:
  (2S_ij * 2A_ij) + (2S_ji * 2A_ji) = 0.
-/
theorem sym_anti_pointwise_orthogonal {d : Nat} (M : MatrixSector d) (i j : Fin d) :
    (symSector2 M i j * antiSector2 M i j) + (symSector2 M j i * antiSector2 M j i) = 0 := by
  dsimp [symSector2, antiSector2, add, sub, transpose]
  show (M i j + M j i) * (M i j - M j i) + (M j i + M i j) * (M j i - M i j) = 0
  have h_comm : M j i + M i j = M i j + M j i := by omega
  rw [h_comm]
  have h_distrib : (M i j + M j i) * (M i j - M j i) + (M i j + M j i) * (M j i - M i j) =
                   (M i j + M j i) * ((M i j - M j i) + (M j i - M i j)) := by
    rw [← Int.mul_add]
  rw [h_distrib]
  have h_cancel : (M i j - M j i) + (M j i - M i j) = 0 := by omega
  rw [h_cancel]
  rw [Int.mul_zero]

/--
  Theorem: Bilinear Energy Partition (Continuous Degen Identity analogue).
  For any pair (i, j), (2S_ij)^2 + (2A_ij)^2 = 2 * ((M_ij)^2 + (M_ji)^2).
-/
theorem bilinear_energy_partition {d : Nat} (M : MatrixSector d) (i j : Fin d) :
    (symSector2 M i j * symSector2 M i j) + (antiSector2 M i j * antiSector2 M i j) =
    2 * (M i j * M i j + M j i * M j i) := by
  dsimp [symSector2, antiSector2, add, sub, transpose]
  show (M i j + M j i) * (M i j + M j i) + (M i j - M j i) * (M i j - M j i) =
       2 * (M i j * M i j + M j i * M j i)
  have h1 : (M i j + M j i) * (M i j + M j i) = 
            M i j * M i j + 2 * (M i j * M j i) + M j i * M j i := by
    rw [Int.add_mul, Int.mul_add, Int.mul_add]
    have h_cross : M j i * M i j = M i j * M j i := by rw [Int.mul_comm]
    rw [h_cross]
    omega
  have h2 : (M i j - M j i) * (M i j - M j i) =
            M i j * M i j - 2 * (M i j * M j i) + M j i * M j i := by
    rw [Int.sub_mul, Int.mul_sub, Int.mul_sub]
    have h_cross : M j i * M i j = M i j * M j i := by rw [Int.mul_comm]
    rw [h_cross]
    omega
  rw [h1, h2]
  omega

end IMF.Proof
