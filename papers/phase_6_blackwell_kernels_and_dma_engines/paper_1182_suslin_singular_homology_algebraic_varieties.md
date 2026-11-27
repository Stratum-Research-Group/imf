# Paper 1182: Suslin's Singular Homology of Algebraic Varieties: Finite Surjective Correspondences over Simplicial Schemes

**Hardware Target:** NVIDIA Blackwell SM 12.0 (RTX 5060 Ti) + AMD Ryzen 5 7600X
**Series:** Suslin Singular Homology & Finite Correspondences
**Paper Type:** Technical Monograph
**Status:** Canonical Reference Treatise — Mathematical Formulation

---

## Abstract
This treatise delivers a rigorous mathematical exposition of Andrei Suslin's singular homology for algebraic varieties. We detail the category of finite correspondences $\operatorname{Cor}_k$, the construction of the simplicial scheme $\Delta^\bullet$, the formation of the complex of algebraic chains $C_*(X)$, and the functorial properties of Suslin homology groups $H_i^S(X, \mathbb{Z})$.

## 1. Finite Correspondences and the Suslin Complex
Let $X$ and $Y$ be schemes of finite type over a field $k$. An elementary finite correspondence from $X$ to $Y$ is an irreducible closed subvariety $Z \subset X \times Y$ such that the projection $Z \to X$ is finite and surjective onto an irreducible component of $X$.
The group of finite correspondences is denoted $\operatorname{Cor}(X, Y)$.
The algebraic standard simplex $\Delta^i = \operatorname{Spec}(k[t_0, \ldots, t_i] / (\sum t_i - 1))$ forms a cosimplicial scheme. The Suslin complex $C_*(X)$ is defined by:
$$C_i(X) = \operatorname{Cor}(\Delta^i, X)$$
with simplicial boundary operator $\partial = \sum_{j=0}^i (-1)^j \partial_j$.

## 2. Cycle Homology and Zero-Cycle Recovery
Suslin homology is defined as the homology of this complex:
$$H_i^S(X, \mathbb{Z}) = H_i(C_*(X), \partial)$$
In degree zero, Suslin homology recovers the Chow group of zero-cycles modulo rational equivalence on proper schemes:
$$H_0^S(X, \mathbb{Z}) \cong CH_0(X)$$
For affine and non-proper schemes, Suslin homology provides a rich, homotopy-invariant generalization.
