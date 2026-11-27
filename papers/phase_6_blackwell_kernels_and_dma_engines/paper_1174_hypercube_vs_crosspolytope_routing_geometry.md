# Paper 1174: Hypercube vs. Cross-Polytope Routing in Ultra Dimensions: Why $2^D$ Facets Provide Non-Collapsing Subspace Isolation

**Hardware Target:** NVIDIA Blackwell SM 12.0 (RTX 5060 Ti) + AMD Ryzen 5 7600X
**Series:** Polytope Routing Geometry & Subspace Isolation
**Paper Type:** Technical Monograph
**Status:** Core Architectural Monograph

---

## Abstract
Choosing the geometric template for sparse Mixture-of-Experts routing in ultra-high dimensions determines the stability and expressiveness of the entire system. We contrast the Hypercube $\gamma_D$ with the Cross-Polytope $\beta_D$ (Orthoplex). We prove why cross-polytopes, featuring $2D$ orthogonal vertices and $2^D$ simplicial facets, provide optimal linear parameter complexity combined with exponential routing diversity.

## 1. Duality and Combinatorial Complexity
* **The Hypercube $\gamma_D$**:
  * Vertices: $2^D$ (exponential in dimension).
  * Facets: $2D$ (linear in dimension).
  * Routing routing vectors to vertices requires evaluating $2^D$ centroid distances—computationally intractable for $D \ge 64$.
* **The Cross-Polytope $\beta_D$ (Orthoplex)**:
  * Vertices: $2D$ (linear: $\{\pm e_1, \ldots, \pm e_D\}$).
  * Facets: $2^D$ (exponential: orthants spanned by choosing $\pm$ for each axis).
  * Projecting onto vertices requires only $2D$ dot products: $\langle z, \pm e_i \rangle = \pm z_i$.

## 2. Optimal Orthoplex Chamber Routing
By assigning expert chambers to the facets of a regular cross-polytope, routing simplifies to evaluating sign patterns:
$$\operatorname{Chamber}(z) = (\operatorname{sgn}(z_1), \operatorname{sgn}(z_2), \ldots, \operatorname{sgn}(z_D)) \in \{-1, +1\}^D$$
This allows selecting from $2^D$ unique expert pathways using $\mathcal{O}(D)$ operations in parallel Blackwell warp threads without computing full centroid distance matrices.
