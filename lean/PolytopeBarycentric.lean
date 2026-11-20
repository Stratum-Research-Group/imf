/-
  PolytopeBarycentric.lean
  Self-contained Lean 4 formalization of Higher-Dimensional Polytope Landmark Connectors (HDPLC).
  Formalizes:
  1. Regular Simplex Barycentric Normalization: Partition of unity over natural scalings.
  2. Convex Combination Non-negativity & Boundedness: All coordinates bounded within [0, Total].
  3. Orthoplex Antipodal Symmetry: Involution property (f ∘ f = id) over 2D antipodal coordinate axes.
-/

namespace IMF.Polytope

/--
  Regular D-Simplex vertex count: K = D + 1.
-/
def SimplexVertices (D : Nat) : Nat := D + 1

/--
  Regular D-Orthoplex (Cross-Polytope) vertex count: K = 2 * D.
-/
def OrthoplexVertices (D : Nat) : Nat := 2 * D

/--
  Non-negative barycentric weights over K coordinates summing to Total.
  Modeled over Nat (or scaled fixed-point rationals) for constructive proofs in pure Lean 4 core.
-/
structure DiscreteBarycentric (K : Nat) (Total : Nat) where
  coords : Fin K → Nat
  sum_eq : (List.finRange K).foldl (fun acc i => acc + coords i) 0 = Total

/--
  Auxiliary lemma: list fold addition lower bound.
  For any list L and accumulator acc, acc ≤ L.foldl (· + f ·) acc.
-/
theorem foldl_add_ge {α : Type} (L : List α) (f : α → Nat) (acc : Nat) :
    acc ≤ L.foldl (fun a x => a + f x) acc := by
  induction L generalizing acc with
  | nil => exact Nat.le_refl acc
  | cons x xs ih =>
    dsimp [List.foldl]
    have h1 : acc ≤ acc + f x := Nat.le_add_right acc (f x)
    have h2 : acc + f x ≤ xs.foldl (fun a y => a + f y) (acc + f x) := ih (acc + f x)
    exact Nat.le_trans h1 h2

/--
  Auxiliary lemma: membership in list fold addition.
  If j ∈ L, then f j ≤ L.foldl (· + f ·) acc.
-/
theorem le_foldl_of_mem {α : Type} [DecidableEq α] {L : List α} {j : α} (hj : j ∈ L)
    (f : α → Nat) (acc : Nat) :
    f j ≤ L.foldl (fun a x => a + f x) acc := by
  induction L generalizing acc with
  | nil => contradiction
  | cons head tail ih =>
    cases hj with
    | head =>
      dsimp [List.foldl]
      have h1 : f j ≤ acc + f j := Nat.le_add_left (f j) acc
      have h2 : acc + f j ≤ tail.foldl (fun a y => a + f y) (acc + f j) := foldl_add_ge tail f (acc + f j)
      exact Nat.le_trans h1 h2
    | tail _ hmem =>
      dsimp [List.foldl]
      exact ih hmem (acc + f head)

/--
  Theorem: Every barycentric coordinate in a non-negative partition of unity is bounded by the total sum.
  If Σ w_i = Total, then for any coordinate j, w_j ≤ Total.
-/
theorem coord_le_total_of_sum {K Total : Nat} (b : DiscreteBarycentric K Total) (j : Fin K) :
    b.coords j ≤ Total := by
  have hj : j ∈ List.finRange K := List.mem_finRange j
  have hle := le_foldl_of_mem hj b.coords 0
  rw [b.sum_eq] at hle
  exact hle

/--
  Normalized unit bound corollary:
  When Total = 1, each barycentric coordinate w_j is in {0, 1}.
-/
theorem coord_le_one_of_unit_sum {K : Nat} (b : DiscreteBarycentric K 1) (j : Fin K) :
    b.coords j ≤ 1 :=
  coord_le_total_of_sum b j

/--
  Antipodal permutation index on the 2D orthoplex vertices:
  Maps vertex k ∈ [0, 2D) to (k + D) % 2D.
-/
def antipodalIdx (D : Nat) (k : Nat) : Nat :=
  (k + D) % (2 * D)

/--
  Theorem: Antipodal axis mapping is an exact involution:
  (k + D + D) % 2D = (k + 2D) % 2D = k % 2D.
  For any valid index k < 2D, antipodalIdx(antipodalIdx(k)) = k.
-/
theorem antipodal_involution (D : Nat) (hD : 0 < D) (k : Nat) (hk : k < 2 * D) :
    antipodalIdx D (antipodalIdx D k) = k := by
  dsimp [antipodalIdx]
  have hpos : 0 < 2 * D := by omega
  rw [Nat.add_mod]
  rw [Nat.mod_mod]
  rw [← Nat.add_mod]
  have h_add : k + D + D = k + (2 * D) := by omega
  rw [h_add]
  rw [Nat.add_mod_right]
  exact Nat.mod_eq_of_lt hk

end IMF.Polytope
