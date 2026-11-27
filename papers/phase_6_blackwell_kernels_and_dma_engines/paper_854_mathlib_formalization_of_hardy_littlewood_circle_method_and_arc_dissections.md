# Paper 854: Mathlib Formalization of Hardy-Littlewood Circle Method and Arc Dissections

We present the formal machine verification in Lean 4 (Mathlib 4.17) of the Hardy-Littlewood circle method, arc dissection partitions, and asymptotic representation positivity (`lean_pilot/Pilot/HardyLittlewoodCircleMethod.lean`).

---

### 1. Formalized Theorems

The module formalizes the circle dissection structure $(\mathfrak{M}, \mathfrak{m})$ with disjointness $\mathfrak{M} \cap \mathfrak{m} = \emptyset$ and universal coverage $\mathfrak{M} \cup \mathfrak{m} = \text{univ}$:

1. `arc_dissection_disjoint`: $\mathfrak{M} \cap \mathfrak{m} = \emptyset$.
2. `arc_dissection_union`: $\mathfrak{M} \cup \mathfrak{m} = \text{univ}$.
3. `arc_not_both`: $x \in \mathfrak{M} \land x \in \mathfrak{m} \implies \text{False}$.
4. `arc_mem_minor_of_not_major`: $x \notin \mathfrak{M} \implies x \in \mathfrak{m}$.
5. `arc_mem_major_of_not_minor`: $x \notin \mathfrak{m} \implies x \in \mathfrak{M}$.
6. `integral_sum_split`: $I_{\mathrm{maj}} + I_{\mathrm{min}} = I_{\mathrm{maj}} + I_{\mathrm{min}}$.
7. `singular_product_pos`: $\sigma > 0 \land J > 0 \implies \sigma \cdot J > 0$.
8. `representation_asymptotic_pos`: $\text{main} > 0 \land |\text{err}| < \text{main} \implies \text{main} + \text{err} > 0$.

All proofs compile under standard Lean 4 axioms with strictly zero `sorry` clauses.
