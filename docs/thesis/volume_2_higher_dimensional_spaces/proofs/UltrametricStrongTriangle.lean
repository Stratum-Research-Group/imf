import Mathlib

/-!
# Pilot Formalization: Non-Archimedean Ultrametric Geometry & Strong Triangle Invariance

In Non-Archimedean mathematics and p-adic analysis, metrics satisfy the
Strong Triangle Inequality (ultrametric inequality):
  d(x, z) ≤ max(d(x, y), d(y, z))

This induces profound topological properties exploited in the IMF architecture:
1. `ultrametric_implies_metric_triangle`:
   Every ultrametric space is an Archimedean metric space: max(a, b) ≤ a + b for a, b ≥ 0.
2. `ultrametric_isosceles`:
   Every triangle in an ultrametric space is isosceles with the two longest sides equal:
   If d(x, y) < d(y, z), then d(x, z) = d(y, z).
3. `ultrametric_ball_transitivity`:
   Every point inside an ultrametric ball is a center:
   If d(x, z) ≤ r and d(z, y) ≤ r, then d(x, y) ≤ r.
4. `ultrametric_intersecting_balls_center_distance`:
   If two balls of radius r share a common point z (d(x, z) ≤ r and d(y, z) ≤ r),
   then their centers satisfy d(x, y) ≤ r.

Theorems proved with ZERO unproven hypotheses and ZERO non-standard axioms.
-/

/-- Ultrametric inequality implies standard metric triangle inequality for non-negative distances -/
theorem ultrametric_implies_metric_triangle {α : Type*}
    (d : α → α → ℝ)
    (h_ultra : ∀ x y z, d x z ≤ max (d x y) (d y z))
    (h_pos : ∀ x y, 0 ≤ d x y)
    (x y z : α) :
    d x z ≤ d x y + d y z := by
  have h_max := h_ultra x y z
  have h_bound : max (d x y) (d y z) ≤ d x y + d y z := by
    apply max_le
    · linarith [h_pos y z]
    · linarith [h_pos x y]
  exact le_trans h_max h_bound

/-- Every triangle in an ultrametric space is isosceles (two longest sides equal) -/
theorem ultrametric_isosceles {α : Type*}
    (d : α → α → ℝ)
    (h_symm : ∀ x y, d x y = d y x)
    (h_ultra : ∀ x y z, d x z ≤ max (d x y) (d y z))
    (x y z : α)
    (h_strict : d x y < d y z) :
    d x z = d y z := by
  -- 1. Upper bound: d(x, z) ≤ d(y, z)
  have h1 : d x z ≤ d y z := by
    have hu := h_ultra x y z
    have h_max : max (d x y) (d y z) = d y z := max_eq_right (le_of_lt h_strict)
    rw [h_max] at hu
    exact hu

  -- 2. Lower bound: d(y, z) ≤ d(x, z)
  have h2 : d y z ≤ d x z := by
    have hu2 := h_ultra y x z
    -- hu2: d y z ≤ max (d y x) (d x z)
    rw [h_symm y x] at hu2
    -- hu2: d y z ≤ max (d x y) (d x z)
    by_contra hc
    have hc_lt : d x z < d y z := lt_of_not_ge hc
    have h_lt : max (d x y) (d x z) < d y z := max_lt h_strict hc_lt
    linarith

  exact le_antisymm h1 h2

/-- Transitivity of ultrametric ball containment -/
theorem ultrametric_ball_transitivity {α : Type*}
    (d : α → α → ℝ)
    (h_ultra : ∀ x y z, d x z ≤ max (d x y) (d y z))
    (r : ℝ) (x z y : α)
    (h1 : d x z ≤ r)
    (h2 : d z y ≤ r) :
    d x y ≤ r := by
  have hu := h_ultra x z y
  have hr : max (d x z) (d z y) ≤ r := max_le h1 h2
  exact le_trans hu hr

/-- Intersecting ultrametric balls have bounded center distance -/
theorem ultrametric_intersecting_balls_center_distance {α : Type*}
    (d : α → α → ℝ)
    (h_symm : ∀ x y, d x y = d y x)
    (h_ultra : ∀ x y z, d x z ≤ max (d x y) (d y z))
    (r : ℝ) (x y z : α)
    (hx : d x z ≤ r)
    (hy : d y z ≤ r) :
    d x y ≤ r := by
  have hy_symm : d z y ≤ r := by
    rw [h_symm z y]
    exact hy
  exact ultrametric_ball_transitivity d h_ultra r x z y hx hy_symm

#print axioms ultrametric_implies_metric_triangle
#print axioms ultrametric_isosceles
#print axioms ultrametric_ball_transitivity
#print axioms ultrametric_intersecting_balls_center_distance
