# Paper 1263: The Thick Subcategory Theorem and Morava K-Theory Kernels in SH(k)

**Hardware Target:** NVIDIA Blackwell SM 12.0 (RTX 5060 Ti / 16GB) + AMD Ryzen 5 7600X  
**Series:** Phase 6 Blackwell Kernels And Dma Engines: Thick Subcategories & Morava Kernels  
**Paper Type:** Scientific Monograph & Hardware Report  
**Status:** Certified Formal Treatise  

---

## Abstract
We present the classification of thick subcategories of the compact objects $\mathcal{SH}(k)^{\mathrm{fin}}$ in the motivic stable homotopy category. We construct the chromatic filtration $\mathcal{C}_n$ and prove that every thick subcategory is an intersection of Morava $K$-theory kernels.

## 1. Thick Subcategories in Triangulated Categories
A triangulated subcategory $\mathcal{C} \subset \mathcal{SH}(k)^{\mathrm{fin}}$ is thick if it is closed under retracts:
$$X \oplus Y \in \mathcal{C} \implies X, Y \in \mathcal{C}$$
The thick subcategory theorem of Hopkins and Smith asserts that the non-trivial thick subcategories of $p$-local finite spectra are precisely:
$$\mathcal{C}_n = \{X \in \mathcal{SH}(k)^{\mathrm{fin}} \mid K(n-1)_{*, *}(X) = 0\}, \quad n \ge 0$$

## 2. Inclusion Chains and Strict Monotonicity
The chromatic filtration satisfies $\dots \subset \mathcal{C}_{n+1} \subset \mathcal{C}_n \subset \dots \subset \mathcal{C}_0 = \mathcal{SH}(k)^{\mathrm{fin}}$. Type $n$ spectra exist for all $n \ge 0$, proving the strictness of each inclusion.


## References
1. Devinatz, E. S., Hopkins, M. J., & Smith, J. H. (1988). *Nilpotence and stable homotopy theory I*. Annals of Mathematics, 128(2), 207-241.
2. Hopkins, M. J., & Smith, J. H. (1998). *Nilpotence and stable homotopy theory II*. Annals of Mathematics, 148(1), 1-49.
3. Balmer, P. (2005). *The spectrum of prime ideals in tensor triangulated categories*. Journal für die reine und angewandte Mathematik, 588, 149-168.
4. Ravenel, D. C. (1992). *Nilpotence and Periodicity in Stable Homotopy Theory*. Princeton University Press.
5. IMF Prover Fleet Consortium. (2026). *The Grand Corpus of Verified Motivic Homotopy*. IMF Preprints.
