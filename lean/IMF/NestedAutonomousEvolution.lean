import Init

namespace IMF.AETHER

theorem nested_cell_dim_bound_1 (n : Nat) : (n + 1) * 2 ≥ n * 2 := by
  exact Nat.mul_le_mul_right 2 (Nat.le_add_right n 1)

theorem hypercube_facet_index_valid_1 (k : Nat) (h : k < 4) :
    k ≤ 3 := Nat.le_pred_of_lt h

theorem nested_cell_dim_bound_2 (n : Nat) : (n + 2) * 2 ≥ n * 2 := by
  exact Nat.mul_le_mul_right 2 (Nat.le_add_right n 2)

theorem hypercube_facet_index_valid_2 (k : Nat) (h : k < 8) :
    k ≤ 7 := Nat.le_pred_of_lt h

theorem nested_cell_dim_bound_3 (n : Nat) : (n + 3) * 2 ≥ n * 2 := by
  exact Nat.mul_le_mul_right 2 (Nat.le_add_right n 3)

theorem hypercube_facet_index_valid_3 (k : Nat) (h : k < 16) :
    k ≤ 15 := Nat.le_pred_of_lt h

theorem nested_cell_dim_bound_4 (n : Nat) : (n + 4) * 2 ≥ n * 2 := by
  exact Nat.mul_le_mul_right 2 (Nat.le_add_right n 4)

theorem hypercube_facet_index_valid_4 (k : Nat) (h : k < 32) :
    k ≤ 31 := Nat.le_pred_of_lt h

theorem nested_cell_dim_bound_5 (n : Nat) : (n + 5) * 2 ≥ n * 2 := by
  exact Nat.mul_le_mul_right 2 (Nat.le_add_right n 5)

theorem hypercube_facet_index_valid_5 (k : Nat) (h : k < 64) :
    k ≤ 63 := Nat.le_pred_of_lt h

theorem nested_cell_dim_bound_6 (n : Nat) : (n + 6) * 2 ≥ n * 2 := by
  exact Nat.mul_le_mul_right 2 (Nat.le_add_right n 6)

theorem hypercube_facet_index_valid_6 (k : Nat) (h : k < 128) :
    k ≤ 127 := Nat.le_pred_of_lt h

theorem nested_cell_dim_bound_7 (n : Nat) : (n + 7) * 2 ≥ n * 2 := by
  exact Nat.mul_le_mul_right 2 (Nat.le_add_right n 7)

theorem hypercube_facet_index_valid_7 (k : Nat) (h : k < 256) :
    k ≤ 255 := Nat.le_pred_of_lt h

theorem nested_cell_dim_bound_8 (n : Nat) : (n + 8) * 2 ≥ n * 2 := by
  exact Nat.mul_le_mul_right 2 (Nat.le_add_right n 8)

theorem hypercube_facet_index_valid_8 (k : Nat) (h : k < 256) :
    k ≤ 255 := Nat.le_pred_of_lt h

theorem nested_cell_dim_bound_9 (n : Nat) : (n + 9) * 2 ≥ n * 2 := by
  exact Nat.mul_le_mul_right 2 (Nat.le_add_right n 9)

theorem hypercube_facet_index_valid_9 (k : Nat) (h : k < 256) :
    k ≤ 255 := Nat.le_pred_of_lt h

theorem nested_cell_dim_bound_10 (n : Nat) : (n + 10) * 2 ≥ n * 2 := by
  exact Nat.mul_le_mul_right 2 (Nat.le_add_right n 10)

theorem hypercube_facet_index_valid_10 (k : Nat) (h : k < 256) :
    k ≤ 255 := Nat.le_pred_of_lt h

end IMF.AETHER
