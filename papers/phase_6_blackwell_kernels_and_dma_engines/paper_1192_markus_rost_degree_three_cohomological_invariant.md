# Paper 1192: Markus Rost's Degree-Three Cohomological Invariant: Functorial Classifications of G-Torsors

**Hardware Target:** NVIDIA Blackwell SM 12.0 (RTX 5060 Ti) + AMD Ryzen 5 7600X
**Series:** The Rost Invariant & Functorial Torsor Classifications
**Paper Type:** Technical Monograph
**Status:** Canonical Reference Treatise — Mathematical Formulation

---

## Abstract
This treatise provides a rigorous mathematical exposition of Markus Rost's universal degree 3 invariant of torsors. We analyze the construction of the Rost invariant via the motivic cohomology of classifying spaces $BG$, the computation of Rost multipliers $n_G$ for all simple Dynkin types, and the injectivity of $r_G$ for classical and exceptional groups.

## 1. The Rost Invariant via Motivic Cohomology
Let $G$ be a split simply connected simple algebraic group over a field $F$. The motivic cohomology of the classifying space $BG$ in weight 2 satisfies:
$$H_\mathcal{M}^4(BG, \mathbb{Z}(2)) \cong \mathbb{Z} \cdot \mathbf{r}_G$$
Evaluation on $G$-torsors $\xi \in H^1(F, G)$ yields the Rost invariant:
$$r_G(\xi) \in H^3(F, \mathbb{Q}/\mathbb{Z}(2))$$

## 2. The Rost Multiplier Table
The integer multiplier $n_G = \gcd(d_1, \ldots, d_k)$ is determined by the degrees of fundamental polynomial invariants:
$$\begin{array}{|c|c|c|c|c|c|c|c|}
\hline
\text{Group } G & \operatorname{SL}_n & \operatorname{Spin}_n & G_2 & F_4 & E_6 & E_7 & E_8 \\
\hline
\text{Multiplier } n_G & 1 & 2 & 2 & 3 & 6 & 12 & 60 \\
\hline
\end{array}$$
In particular, for $G_2$ and $F_4$, the Rost invariant is completely injective on isomorphism classes of torsors, giving a direct bijection between Galois cohomology and exceptional algebraic structures.
