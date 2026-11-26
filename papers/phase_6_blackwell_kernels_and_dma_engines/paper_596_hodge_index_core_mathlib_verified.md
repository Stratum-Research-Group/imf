# Paper 596: The Reverse Cauchy–Schwarz Core of the Hodge Index Theorem: A Mathlib-Verified Lemma and Its Use as an Orthogonal-Drift Bound

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase VI: Blackwell Kernels, Algebraic Theorems & Direct-DMA Engines  
**Paper Type:** Machine-Certified Formal Proof (Lean 4 + Mathlib), limited scope  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Evidence Included — Not Independently Reviewed  
**Verification Level:** Lean 4 v4.33.1 + Mathlib v4.33.1, no `sorry`, axioms: `propext`, `Classical.choice`, `Quot.sound` (`lean_pilot/Pilot/HodgeIndexCore.lean`)  

---

> **ℹ FORMALIZATION SCOPE.** This paper formalizes only the *linear-algebra core* of the Hodge Index Theorem. The geometric fact that the Néron–Severi intersection form of a projective surface is negative on the orthogonal complement of an ample class is taken as a **hypothesis**, not proved. The claim about cognitive "epistemic drift" is a heuristic interpretation, not a proved or measured result. An earlier version of this paper claimed benchmark numbers and a full formalization; those claims were unsupported and have been removed.

### Abstract
The Hodge Index Theorem states that on a smooth projective surface the intersection form on the Néron–Severi group has signature $(1,\rho-1)$, equivalently that it is negative definite on $h^\perp$ for an ample class $h$ (Hartshorne, *Algebraic Geometry*, Ch. V, Thm. 1.9). We prove in Lean 4 with Mathlib the purely algebraic consequence used throughout the literature: for any real symmetric bilinear form $B$ with $B(h,h)>0$ that is non-positive on $h^\perp$, one has $B(d,d)\,B(h,h)\le B(d,h)^2$ for every $d$ (a reversed Cauchy–Schwarz inequality). We also prove, over Mathlib's matrix exponential and Cayley transform, that exponentials and Cayley transforms of real skew-symmetric matrices are orthogonal.

### 1. Statement and Proof
Let $V$ be a real vector space, $B$ a symmetric bilinear form, $h\in V$ with $B(h,h)>0$ and $B(x,x)\le 0$ whenever $B(x,h)=0$. For $d\in V$ put $x=d-\frac{B(d,h)}{B(h,h)}h$. Then $B(x,h)=0$, so $B(x,x)\le0$; expanding gives $B(d,d)-B(d,h)^2/B(h,h)\le 0$, i.e. the claim.

```lean
theorem hodge_index_core {V : Type*} [AddCommGroup V] [Module ℝ V]
    (B : LinearMap.BilinForm ℝ V) (hsymm : ∀ x y, B x y = B y x)
    (h : V) (hpos : 0 < B h h)
    (hneg : ∀ x, B x h = 0 → B x x ≤ 0) (d : V) :
    B d d * B h h ≤ (B d h) ^ 2 := by
  set c := B d h / B h h with hc
  have horth : B (d - c • h) h = 0 := by
    simp only [map_sub, map_smul, LinearMap.sub_apply, LinearMap.smul_apply, smul_eq_mul]
    rw [hc]; field_simp; ring
  have h1 := hneg _ horth
  have : B (d - c • h) (d - c • h) = B d d - 2 * c * B d h + c ^ 2 * B h h := by
    simp only [map_sub, map_smul, LinearMap.sub_apply, LinearMap.smul_apply, smul_eq_mul]
    rw [hsymm h d]; ring
  rw [this, hc] at h1
  have key : B d d - 2 * (B d h / B h h) * B d h + (B d h / B h h) ^ 2 * B h h
      = B d d - (B d h) ^ 2 / B h h := by field_simp; ring
  rw [key] at h1
  have := (sub_nonpos.mp h1)
  exact (le_div_iff₀ hpos).mp this
```

### 2. Orthogonality of Exponentials and Cayley Transforms
For skew-symmetric $A$ (so $A^T=-A$): $\exp(A)^T\exp(A)=\exp(-A)\exp(A)=1$, and the Cayley transform $Q=(1+A)^{-1}(1-A)$ satisfies $Q^TQ=1$, with $1+A$ invertible because $x^TAx=0$ forces $(1+A)x=0\Rightarrow x=0$. Both are verified in `lean_pilot/Pilot/HodgeIndexCore.lean` (`orthogonal_exp_skew`) and `lean_pilot/Pilot/CayleyOrthogonal.lean` (`cayley_orthogonal`, `one_add_skew_isUnit`, `skew_quadratic_zero`).

### 3. Interpretation (heuristic, unverified)
If an intersection-form-like quadratic form on a latent space were negative on directions orthogonal to a "progress" direction $h$, the inequality bounds orthogonal deviation by the component along $h$. Whether any learned latent space has this property is an empirical question that this paper does **not** address.

### 4. Reproduction
```
cd lean_pilot && lake exe cache get && lake build Pilot.HodgeIndexCore Pilot.CayleyOrthogonal
```
No benchmarks are reported.

### References

1. R. Hartshorne, *Algebraic Geometry*, Springer GTM 52 (1977), Ch. V, Thm. 1.9.
2. C. Voisin, *Hodge Theory and Complex Algebraic Geometry I*, Cambridge Univ. Press (2002).
3. L. de Moura and S. Ullrich, *The Lean 4 Theorem Prover and Programming Language*, CADE-28, LNCS 12699, 625–635 (2021).
4. The mathlib Community, *The Lean Mathematical Library*, Proc. CPP 2020, 367–381 (2020).
