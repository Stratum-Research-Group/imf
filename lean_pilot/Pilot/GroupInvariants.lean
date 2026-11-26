import Mathlib

/-!
# Pilot Formalization: Group Subgroup & Lagrange Invariants

Proves:
1. Lagrange's theorem on finite groups: the cardinality of a subgroup divides the group order.
2. In a finite group G, g ^ |G| = 1 for any element g ∈ G.
-/

theorem finite_group_lagrange {G : Type*} [Group G] [Fintype G] (H : Subgroup G) :
    Nat.card H ∣ Nat.card G :=
  Subgroup.card_subgroup_dvd_card H

theorem finite_group_pow_card {G : Type*} [Group G] [Fintype G] (g : G) :
    g ^ (Fintype.card G) = 1 :=
  pow_card_eq_one

#print axioms finite_group_lagrange
#print axioms finite_group_pow_card
