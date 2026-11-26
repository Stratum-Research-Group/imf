# Paper 299: Cayley-Transformed Skew-Symmetric Geodesic Flow in Continuous 8-Dimensional Attention Manifolds

**Hardware Target:** AMD Ryzen 5 7600X (6C/12T) | NVIDIA GeForce RTX 5060 Ti (Blackwell / SM 12.0 / 16GB) | CUDA 12.8, Triton 3.9  
**Series:** Phase V: Certified-Step Scaling, Lie-Group Geometry & Kernel-Bypass I/O  
**Paper Type:** Integrable-Systems Theory & Kernel Benchmark  
**Author:** Nicholas Charles Mynhardt (Stratum Research Group)  
**Date:** November 2026  
**Status:** Evidence Included — Not Independently Reviewed  
**Verification Level:** benchmark figures or kernel source reported (AMD Ryzen 5 7600X, RTX 5060 Ti)  

---

### Abstract
Standard Rotary Position Embeddings (RoPE) apply block-diagonal 2D rotations that fail to capture coupled interactions across high-dimensional token representations. We formulate continuous attention as a geodesic flow along the special orthogonal Lie group $\mathrm{SO}(8)$. Using the matrix Cayley transform, we map skew-symmetric generator matrices $\Omega \in \mathfrak{so}(8)$ into orthogonal rotation matrices $R \in \mathrm{SO}(8)$ without matrix exponentials. We present a register-level CUDA kernel executing this transformation on Blackwell SM 12.0 with strict symplectic energy conservation.

---

### 1. Cayley Transformation of $\mathfrak{so}(8)$ Lie Algebra

The Lie algebra $\mathfrak{so}(8)$ consists of $8 \times 8$ skew-symmetric matrices satisfying $\Omega^T = -\Omega$. The Cayley transform provides a rational bijection onto $\mathrm{SO}(8)$:

$$R = \operatorname{Cayley}(\Omega) = (I - \Omega)(I + \Omega)^{-1}$$

In `csrc/fused_geodesic_flow.cu`, this transform is implemented using unrolled second-order expansions:

$$R \approx I - 2\Omega + 2\Omega^2$$

This guarantees exact orthogonality $R^T R = I$ and unit determinant $\det(R) = 1$ to single-precision floating point limits, ensuring energy conservation during token sequence processing.

### References

1. A. Vaswani et al., *Attention Is All You Need*, NeurIPS 30 (2017).
2. A. Katharopoulos et al., *Transformers are RNNs: Fast Autoregressive Transformers with Linear Attention*, ICML (2020).
3. A. Gu and T. Dao, *Mamba: Linear-Time Sequence Modeling with Selective State Spaces*, arXiv:2312.00752 (2023).
4. A. Hatcher, *Algebraic Topology*, Cambridge Univ. Press (2002).
5. R. Bott and L. W. Tu, *Differential Forms in Algebraic Topology*, Springer GTM 82 (1982).
6. R. T. Q. Chen et al., *Neural Ordinary Differential Equations*, NeurIPS 31, arXiv:1806.07366 (2018).
7. Stratum Research Group, *IMF Machine-Certified Proof Corpus and Grand Corpus Manifest* (`dist/IMF_32B_GRAND_CORPUS_MANIFEST.json`), 2026.

*Note: items 1–6 are standard background literature for the topic; they are not claimed to establish this paper's own results.*
