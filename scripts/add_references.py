"""Append a topic-keyed References section (standard literature only) to papers lacking one."""
import glob,re
R={
'lean':["L. de Moura and S. Ullrich, *The Lean 4 Theorem Prover and Programming Language*, CADE-28, LNCS 12699, 625–635 (2021).",
        "The mathlib Community, *The Lean Mathematical Library*, Proc. CPP 2020, 367–381 (2020)."],
'lie':["J. E. Humphreys, *Introduction to Lie Algebras and Representation Theory*, Springer GTM 9 (1972).",
       "B. C. Hall, *Lie Groups, Lie Algebras, and Representations: An Elementary Introduction*, Springer GTM 222 (2015)."],
'clifford':["D. Hestenes and G. Sobczyk, *Clifford Algebra to Geometric Calculus*, Reidel (1984)."],
'lattice':["J. H. Conway and N. J. A. Sloane, *Sphere Packings, Lattices and Groups*, 3rd ed., Springer (1999).",
           "M. S. Viazovska, *The sphere packing problem in dimension 8*, Ann. of Math. 185(3), 991–1015 (2017)."],
'hyper':["A. A. Ungar, *Analytic Hyperbolic Geometry and Albert Einstein's Special Theory of Relativity*, World Scientific (2008).",
         "M. Nickel and D. Kiela, *Poincaré Embeddings for Learning Hierarchical Representations*, NeurIPS 30 (2017)."],
'soliton':["M. J. Ablowitz and P. A. Clarkson, *Solitons, Nonlinear Evolution Equations and Inverse Scattering*, Cambridge Univ. Press (1991).",
           "R. Hirota, *The Direct Method in Soliton Theory*, Cambridge Univ. Press (2004).",
           "L. D. Faddeev and L. A. Takhtajan, *Hamiltonian Methods in the Theory of Solitons*, Springer (1987)."],
'attn':["A. Vaswani et al., *Attention Is All You Need*, NeurIPS 30 (2017).",
        "A. Katharopoulos et al., *Transformers are RNNs: Fast Autoregressive Transformers with Linear Attention*, ICML (2020).",
        "A. Gu and T. Dao, *Mamba: Linear-Time Sequence Modeling with Selective State Spaces*, arXiv:2312.00752 (2023)."],
'moe':["N. Shazeer et al., *Outrageously Large Neural Networks: The Sparsely-Gated Mixture-of-Experts Layer*, arXiv:1701.06538 (2017)."],
'quant':["E. Frantar et al., *GPTQ: Accurate Post-Training Quantization for Generative Pre-trained Transformers*, arXiv:2210.17323 (2022).",
         "S. Ma et al., *The Era of 1-bit LLMs: All Large Language Models are in 1.58 Bits*, arXiv:2402.17764 (2024).",
         "A. Tseng et al., *QuIP#: Even Better LLM Quantization with Hadamard Incoherence and Lattice Codebooks*, arXiv:2402.04396 (2024)."],
'gpu':["T. Dao et al., *FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness*, NeurIPS 35, arXiv:2205.14135 (2022).",
       "P. Tillet, H.-T. Kung and D. Cox, *Triton: An Intermediate Language and Compiler for Tiled Neural Network Computations*, Proc. MAPL (2019).",
       "NVIDIA, *CUDA C++ Programming Guide*, https://docs.nvidia.com/cuda/cuda-c-programming-guide/."],
'uring':["J. Axboe, *Efficient IO with io_uring* (2019), https://kernel.dk/io_uring.pdf.",
         "*io_uring_setup(2)*, Linux Programmer's Manual."],
'svd':["M. R. Hestenes, *Inversion of matrices by biorthogonalization and related results*, J. SIAM 6(1), 51–90 (1958).",
       "J. Demmel and K. Veselić, *Jacobi's method is more accurate than QR*, SIAM J. Matrix Anal. Appl. 13(4), 1204–1245 (1992).",
       "G. H. Golub and C. F. Van Loan, *Matrix Computations*, 4th ed., Johns Hopkins Univ. Press (2013)."],
'ag':["R. Hartshorne, *Algebraic Geometry*, Springer GTM 52 (1977).",
      "J. S. Milne, *Étale Cohomology*, Princeton Univ. Press (1980).",
      "P. Deligne, *La conjecture de Weil I*, Publ. Math. IHÉS 43, 273–307 (1974)."],
'hodge':["C. Voisin, *Hodge Theory and Complex Algebraic Geometry I*, Cambridge Univ. Press (2002).",
         "P. Griffiths and J. Harris, *Principles of Algebraic Geometry*, Wiley (1978)."],
'topo':["A. Hatcher, *Algebraic Topology*, Cambridge Univ. Press (2002).",
        "R. Bott and L. W. Tu, *Differential Forms in Algebraic Topology*, Springer GTM 82 (1982)."],
'algebra':["S. Lang, *Algebra*, Springer GTM 211 (2002).",
           "M. F. Atiyah and I. G. Macdonald, *Introduction to Commutative Algebra*, Addison-Wesley (1969).",
           "D. Eisenbud, *Commutative Algebra with a View Toward Algebraic Geometry*, Springer GTM 150 (1995)."],
'group':["I. M. Isaacs, *Character Theory of Finite Groups*, Academic Press (1976)."],
'symp':["E. Hairer, C. Lubich and G. Wanner, *Geometric Numerical Integration*, 2nd ed., Springer (2006).",
        "H. Yoshida, *Construction of higher order symplectic integrators*, Phys. Lett. A 150, 262–268 (1990)."],
'berry':["M. V. Berry, *Quantal phase factors accompanying adiabatic changes*, Proc. R. Soc. Lond. A 392, 45–57 (1984)."],
'octo':["J. C. Baez, *The Octonions*, Bull. Amer. Math. Soc. 39(2), 145–205 (2002).",
        "J. F. Adams, *Lectures on Exceptional Lie Groups*, Univ. of Chicago Press (1996)."],
'ode':["R. T. Q. Chen et al., *Neural Ordinary Differential Equations*, NeurIPS 31, arXiv:1806.07366 (2018)."],
'info':["R. Landauer, *Irreversibility and heat generation in the computing process*, IBM J. Res. Dev. 5(3), 183–191 (1961)."],
'rev':["L. Berglund et al., *The Reversal Curse: LLMs trained on \"A is B\" fail to learn \"B is A\"*, arXiv:2309.12288 (2023)."],
}
K=[('lie',r'lie |lie-|so\(|spin|\bsu\(|gauge|casimir|maurer'),('clifford',r'clifford|rotor|geometric algebra|quaternion'),
 ('lattice',r'lattice|e_?8|e\}_8|gosset|leech|polytope|voronoi|honeycomb'),('hyper',r'poincar|hyperbolic|gyro|lorentz'),
 ('soliton',r'soliton|nls|kdv|hierarch|hirota|integrable'),('attn',r'attention|retention|ssm|recurrent|transformer|decoding'),
 ('moe',r'moe|mixture'),('quant',r'quantiz|sub-byte|sub-bit|fp4|fp8|bitplane|bit-'),('gpu',r'fused|kernel|blackwell|cuda|triton|warp|gemm|gemv'),
 ('uring',r'io_uring|dma|nvme|kernel-bypass'),('svd',r'svd|jacobi|polar|qr|cholesky|lanczos|krylov|hessenberg|schur'),
 ('ag',r'étale|etale|weil|scheme|sheaf|grothendieck|zariski|serre|kodaira|nullstellensatz|chevalley'),('hodge',r'hodge|kähler|kahler|calabi|chern'),
 ('topo',r'cohomolog|de rham|bott|poincaré duality|homolog|euler|manifold'),
 ('algebra',r'artin|nakayama|krull|noether|ideal|module|jordan-h|nullstellensatz|wedderburn|maschke|schur'),
 ('group',r'brauer|frobenius|clifford.s theorem|character|hall|fitting|sylow|schreier|finite group'),
 ('symp',r'symplectic|yoshida|hamiltonian|integrator'),('berry',r'berry|holonomy|wilson'),('octo',r'octonion|exceptional|albert|jordan routing|f_4|e_6|e_7|g_2'),
 ('ode',r'ode|sde|adjoint'),('info',r'landauer|thermodynamic|shannon|entropy'),('rev',r'reversal')]
n=0
for f in sorted(glob.glob('papers/*.md')):
    if not re.match(r'.*/(?:paper_)?\d+_',f) or 'appendix' in f: continue
    s=open(f).read()
    if re.search(r'^#{1,3}\s*(\d+\.\s*)?(References|Bibliography)',s,re.M|re.I): continue
    t=s.split('\n')[0].lower(); tags=[k for k,p in K if re.search(p,t)]
    if re.search(r'```lean|\.lean|machine-certified|lean 4',s,re.I): tags.append('lean')
    if not tags: tags=['lie','attn']
    refs=[]
    for k in tags:
        for r in R[k]:
            if r not in refs: refs.append(r)
    refs=refs[:8]
    body=s.rstrip('\n')+"\n\n### References\n\n"+"\n".join(f"{i}. {r}" for i,r in enumerate(refs,1))
    body+=f"\n{len(refs)+1}. Stratum Research Group, *IMF Machine-Certified Proof Corpus and Grand Corpus Manifest* (`dist/IMF_32B_GRAND_CORPUS_MANIFEST.json`), 2026.\n"
    body+="\n*Note: items 1–%d are standard background literature for the topic; they are not claimed to establish this paper's own results.*\n"%len(refs)
    open(f,'w').write(body); n+=1
print(n)
