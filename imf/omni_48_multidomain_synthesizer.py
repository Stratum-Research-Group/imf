"""
Expanded 48-Domain Omni-Polytope Expert Registry.

Enriched with deep, rigorous mathematical fields:
1. Differential Geometry & Lie Algebras: Connection forms, Riemann curvature tensor, Cartan structure equations.
2. Algebraic Topology & Homology: Simplicial homology, Betti numbers, Mayer-Vietoris sequence, boundary operator.
3. Category Theory & Topos Theory: Monoidal categories, Adjoint functors, Yoneda lemma, Sheaves.
4. Abstract Algebra & Galois Theory: Group actions, Sylow theorems, Galois correspondence, cyclotomic fields.
5. Complex Analysis & Riemann Surfaces: Cauchy residue theorem, conformal mappings, Weierstrass elliptic functions.
6. Number Theory & Cryptography: Modular arithmetic, quadratic reciprocity, elliptic curve point addition.
7. Numerical Analysis & Optimization: Runge-Kutta 4th order, BFGS quasi-Newton, Lanczos iteration, Cholesky decomposition.
8. Functional Analysis & Operator Theory: Hilbert space spectral theorem, Fourier transform, Sobolev norms.
9. Probability Theory & Stochastic Calculus: Itô's lemma, Ornstein-Uhlenbeck process, Fokker-Planck equation.
10. Low-Level Systems: C, C++, Zig, Rust, Linux Kernel, eBPF, Firmware MMIO, Hardware Drivers.
11. Architecture & ISAs: x86-64 (AVX2/512), ARM64, RISC-V.
12. Accelerators & Differentiable: JAX, Triton, CUDA, PyTorch, OpenCL.
13. Molecular Biology & Genomics: Watson-Crick DNA, Splice donor/acceptor, Codon ORFs, AlphaFold pLDDT.
14. Physical & Chemical Sciences: Cheminformatics, General Relativity, Quantum Circuits, Navier-Stokes.
15. Programming Languages: Julia, Go, Swift, Haskell, OCaml, Perl, Lua, Bash, SQL, HTML5.
16. Formal Logic & Verification: Lean 4, Coq, TLA+.
"""

from typing import Dict, List, Tuple
import random


OMNI_48_EXPERT_DOMAINS: List[str] = [
    # Systems & Hardware (1-8)
    "c_systems",              # 0
    "cpp_modern",             # 1
    "zig_systems",            # 2
    "rust_systems",           # 3
    "linux_kernel_ebpf",      # 4
    "hardware_firmware",      # 5
    "assembly_x86_64",        # 6
    "assembly_arm_riscv",     # 7
    # Accelerators & Languages (9-16)
    "jax_accelerators",       # 8
    "triton_gpu",             # 9
    "cuda_kernels",           # 10
    "julia_computing",        # 11
    "go_concurrency",         # 12
    "swift_systems",          # 13
    "haskell_pure",           # 14
    "ocaml_types",            # 15
    # Scripting & Web (17-20)
    "perl_text",              # 16
    "lua_runtime",            # 17
    "bash_posix",             # 18
    "web_html5",              # 19
    # Natural Sciences (21-26)
    "genomics_dna",           # 20
    "splice_transcriptome",   # 21
    "proteomics_structural",  # 22
    "cheminformatics",        # 23
    "astrophysics_relativity", # 24
    "quantum_computing",      # 25
    "fluid_dynamics_pde",     # 26
    "sql_relational",         # 27
    # Formal Proofs & Logic (29-32)
    "lean4_proofs",           # 28
    "coq_formal",             # 29
    "tla_plus_verification",  # 30
    "cryptography_security",  # 31
    # Deep Mathematics Fields (33-48)
    "diff_geometry_lie",      # 32: Riemann curvature, Christoffel symbols, Lie brackets
    "algebraic_topology",     # 33: Simplicial homology, boundary operator, Betti numbers
    "category_theory",        # 34: Functors, natural transformations, Yoneda lemma
    "abstract_algebra",       # 35: Groups, rings, Galois field extensions
    "complex_analysis",       # 36: Contour integration, Cauchy residue, conformal mapping
    "algebraic_number_theory",# 37: Quadratic reciprocity, ideal class group, elliptic curves
    "functional_analysis",    # 38: Hilbert spaces, Banach spaces, spectral theorem
    "numerical_optimization", # 39: Runge-Kutta, BFGS, conjugate gradient, Lanczos
    "stochastic_calculus",    # 40: Itô lemma, Brownian motion, Fokker-Planck
    "symplectic_geometry",    # 41: Hamiltonian vector fields, Poisson brackets
    "combinatorics_graph",    # 42: Ramsey theory, spectral graph theory, Tutte polynomial
    "information_theory",     # 43: Shannon entropy, Kullback-Leibler, channel capacity
    "pde_elliptic_hyperbolic",# 44: Heat kernel, Wave equation d'Alembertian, Laplace-Beltrami
    "measure_ergodic_theory", # 45: Lebesgue integration, Radon-Nikodym, measure-preserving maps
    "linear_algebra_tensors", # 46: Tensor contraction, Singular Value Decomposition, Kronecker
    "symbolic_math_cot",      # 47: Multi-step arithmetic with <thought> execution registers
]


class OmniPolytopeDomainSynthesizer:
    def __init__(self, seed: int = 42):
        random.seed(seed)

    def sample_by_index(self, idx: int) -> Tuple[str, str]:
        domain_name = OMNI_48_EXPERT_DOMAINS[idx]

        # Systems & Languages
        if idx == 0:
            return ("// C17 POSIX epoll\n#include <sys/epoll.h>\nint set_nb(int fd) { return fcntl(fd, F_SETFL, O_NONBLOCK); }\n", domain_name)
        elif idx == 1:
            return ("// C++20 Concepts\ntemplate <std::integral T> T add(T a, T b) noexcept { return a + b; }\n", domain_name)
        elif idx == 2:
            return ("// Zig 0.13 Memory\nconst std = @import(\"std\");\npub fn slice(buf: []u8) []u8 { return buf[0..]; }\n", domain_name)
        elif idx == 3:
            return ("// Rust Systems\npub fn atomic_inc(val: &std::sync::atomic::AtomicUsize) { val.fetch_add(1, std::sync::atomic::Ordering::SeqCst); }\n", domain_name)
        elif idx == 4:
            return ("// Linux eBPF\nSEC(\"xdp\") int drop(struct xdp_md *ctx) { return XDP_DROP; }\nchar _lic[] SEC(\"license\") = \"GPL\";\n", domain_name)
        elif idx == 5:
            return ("// Firmware MMIO\n#define UART_RHR (*(volatile uint8_t*)0x10000000)\nvoid putc(char c) { UART_RHR = (uint8_t)c; }\n", domain_name)
        elif idx == 6:
            return ("// x86-64 AVX2\n.globl vec_dot\nvec_dot:\n  vmovups (%rdi), %ymm0\n  vfmadd231ps (%rsi), %ymm0, %ymm1\n  ret\n", domain_name)
        elif idx == 7:
            return ("// ARM64 AArch64 Spinlock\n.globl lock\nlock:\n  ldaxr w1, [x0]\n  cbnz w1, lock\n  stxr w2, w1, [x0]\n  ret\n", domain_name)
        elif idx == 8:
            return ("# JAX Differentiable Lie step\nimport jax.numpy as jnp\nfrom jax import jit, vmap\n@jit\ndef cayley(h, A): return jnp.dot(jnp.linalg.inv(jnp.eye(A.shape[0]) + A), h)\n", domain_name)
        elif idx == 9:
            return ("# Triton GPU kernel\nimport triton\nimport triton.language as tl\n@triton.jit\ndef add_k(x_ptr, y_ptr, n): pid = tl.program_id(0); tl.store(y_ptr + pid, tl.load(x_ptr + pid))\n", domain_name)
        elif idx == 10:
            return ("// CUDA C++ Warp Shuffle\n__device__ float warp_sum(float val) {\n  for (int o = 16; o > 0; o /= 2) val += __shfl_down_sync(0xffffffff, val, o);\n  return val;\n}\n", domain_name)
        elif idx == 11:
            return ("# Julia High-Performance Computing\nfunction axpy!(a::Float64, x::Vector{Float64}, y::Vector{Float64})\n    @simd for i in eachindex(x) @inbounds y[i] += a * x[i] end\nend\n", domain_name)
        elif idx == 12:
            return ("// Go Concurrency\nfunc worker(ch <-chan int, out chan<- int) {\n    for val := range ch { out <- val * 2 }\n}\n", domain_name)
        elif idx == 13:
            return ("// Swift Protocol-Oriented\nprotocol Computable { associatedtype Output; func compute() -> Output }\n", domain_name)
        elif idx == 14:
            return ("-- Haskell Pure Functional\nquicksort :: (Ord a) => [a] -> [a]\nquicksort [] = []\nquicksort (x:xs) = quicksort [y | y <- xs, y <= x] ++ [x] ++ quicksort [y | y <- xs, y > x]\n", domain_name)
        elif idx == 15:
            return ("(* OCaml Algebraic Data Types *)\ntype 'a tree = Leaf | Node of 'a * 'a tree * 'a tree\nlet rec depth = function Leaf -> 0 | Node (_, l, r) -> 1 + max (depth l) (depth r)\n", domain_name)
        elif idx == 16:
            return ("#!/usr/bin/env perl\nwhile (<>) { chomp; if (/^>(\\S+)/) { print \"Header: $1\\n\"; } }\n", domain_name)
        elif idx == 17:
            return ("-- Lua Metatable Class Pattern\nlocal Vector = {}\nVector.__index = Vector\nfunction Vector.new(x, y) return setmetatable({x=x, y=y}, Vector) end\n", domain_name)
        elif idx == 18:
            return ("#!/usr/bin/env bash\nset -euo pipefail\ntrap 'echo Error on line $LINENO >&2' ERR\n", domain_name)
        elif idx == 19:
            return ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\"></head><body><main role=\"main\"><h1>IMF</h1></main></body></html>\n", domain_name)
        elif idx == 20:
            return ("; FASTA Watson-Crick DNA\n>chr1:100-140\nATGCGATCGATCGATCGATCGATCGATCGATCGA\n; Reverse Complement:\nTCGATCGATCGATCGATCGATCGATCGATCGCAT\n", domain_name)
        elif idx == 21:
            return ("; Eukaryotic Splice Junction\n>donor_acceptor_motif\nAGGTAAGT ... TTTCTAG\n// 5' GT donor, 3' AG acceptor\n", domain_name)
        elif idx == 22:
            return ("// AlphaFold Structural Proteomics\n# Residue pLDDT Confidence: >90 (Very High), 70-90 (Confident), <50 (Disordered)\nPHI = -60.0; PSI = -45.0  # Alpha-helix Ramachandran backbone\n", domain_name)
        elif idx == 23:
            return ("# SMILES Cheminformatics\nSMILES = 'CC(=O)Oc1ccccc1C(=O)O'  # Aspirin\nMW = 180.16; LogP = 1.19; HBD = 1; HBA = 4\n", domain_name)
        elif idx == 24:
            return ("# General Relativity\n# Schwarzschild radius: r_s = 2GM / c^2\nr_s = (2.0 * 6.6743e-11 * 1.989e30) / (299792458 ** 2)\n", domain_name)
        elif idx == 25:
            return ("# Quantum Computing: Bell State |Phi+>\nfrom qiskit import QuantumCircuit\nqc = QuantumCircuit(2)\nqc.h(0)\nqc.cx(0, 1)\n", domain_name)
        elif idx == 26:
            return ("# Navier-Stokes PDE: du/dt + (u.grad)u = -grad(p)/rho + nu*laplace(u)\n# Incompressible velocity divergence: div(u) = 0\n", domain_name)
        elif idx == 27:
            return ("-- SQL Recursive CTE\nWITH RECURSIVE Hierarchy AS (\n  SELECT id, parent_id FROM nodes WHERE parent_id IS NULL\n  UNION ALL\n  SELECT n.id, n.parent_id FROM nodes n JOIN Hierarchy h ON n.parent_id = h.id\n) SELECT * FROM Hierarchy;\n", domain_name)
        elif idx == 28:
            return ("theorem add_comm_id (n m : Nat) : n + m = m + n := by\n  omega\n", domain_name)
        elif idx == 29:
            return ("(* Coq Gallina *)\nTheorem plus_n_O : forall n : nat, n = n + 0.\nProof. intros n. rewrite <- plus_n_O_first. reflexivity. Qed.\n", domain_name)
        elif idx == 30:
            return ("(* TLA+ State Machine Specification *)\nVARIABLE state\nInit == state = \"Idle\"\nNext == state = \"Idle\" /\\ state' = \"Processing\"\nSpec == Init /\\ [][Next]_state\n", domain_name)
        elif idx == 31:
            return ("// Constant-Time Comparison\nint ct_eq(const uint8_t *a, const uint8_t *b, size_t n) {\n  uint8_t d = 0; for (size_t i=0; i<n; ++i) d |= (a[i] ^ b[i]); return d == 0;\n}\n", domain_name)

        # Deep Mathematics Fields
        elif idx == 32: # diff_geometry_lie
            return ("# Differential Geometry & Lie Algebras\n# Christoffel symbols of the second kind:\n# Gamma^k_ij = (1/2) * g^kl * (d g_jl / dx^i + d g_il / dx^j - d g_ij / dx^l)\n# Riemann Curvature Tensor: R^l_ijk = d Gamma^l_ik / dx^j - d Gamma^l_ij / dx^k + ...\n# Lie bracket: [X, Y]^k = X^i (d Y^k / dx^i) - Y^i (d X^k / dx^i)\n", domain_name)
        elif idx == 33: # algebraic_topology
            return ("# Algebraic Topology & Simplicial Homology\n# Boundary operator on k-simplex: partial_k [v0, ..., vk] = sum (-1)^i [v0, ..., hat(vi), ..., vk]\n# Fundamental nilpotence lemma: partial_{k-1} compose partial_k = 0\n# k-th Homology Group: H_k(X) = ker(partial_k) / im(partial_{k+1})\n# Betti number: b_k = rank(H_k)\n", domain_name)
        elif idx == 34: # category_theory
            return ("# Category Theory: Functors, Adjunctions & Yoneda Lemma\n# Adjunction: Hom_D(F(C), D) is naturally isomorphic to Hom_C(C, G(D))\n# Yoneda Lemma: Nat(Hom(A, -), F) is isomorphic to F(A)\n# Monoidal unit and tensor product: (X (x) Y) (x) Z ~ X (x) (Y (x) Z)\n", domain_name)
        elif idx == 35: # abstract_algebra
            return ("# Abstract Algebra & Galois Theory\n# Fundamental Theorem of Galois Theory: Subgroups of Gal(L/K) <=> Intermediate fields K <= E <= L\n# Group Action: |G| = |Orb(x)| * |Stab(x)| (Orbit-Stabilizer Theorem)\n# First Isomorphism Theorem: G / ker(phi) is isomorphic to im(phi)\n", domain_name)
        elif idx == 36: # complex_analysis
            return ("# Complex Analysis & Riemann Surfaces\n# Cauchy's Residue Theorem:\n# oint_gamma f(z) dz = 2 * pi * i * sum Residue(f, z_k)\n# Conformal Riemann Mapping Theorem: Any simply connected domain U != C is biholomorphic to unit disk D\n", domain_name)
        elif idx == 37: # algebraic_number_theory
            return ("# Algebraic Number Theory & Elliptic Curves\n# Weierstrass form: y^2 = x^3 + a*x + b\n# Group law on elliptic curve E(F_p): P + Q + R = 0 on chord-and-tangent line\n# Discriminant: Delta = -16 * (4*a^3 + 27*b^2) != 0\n# Quadratic Reciprocity: (p/q)(q/p) = (-1)^((p-1)/2 * (q-1)/2)\n", domain_name)
        elif idx == 38: # functional_analysis
            return ("# Functional Analysis: Hilbert Space Spectral Decomposition\n# Spectral Theorem for bounded self-adjoint operator T: T = int lambda d E(lambda)\n# Riesz Representation Theorem: For every continuous linear functional phi in H*, phi(x) = <x, y>\n# Sobolev Space norm: ||u||_{W^{k, p}} = (sum_{|alpha| <= k} ||D^alpha u||_p^p)^(1/p)\n", domain_name)
        elif idx == 39: # numerical_optimization
            return ("# Numerical Optimization: BFGS Quasi-Newton Hessian Update\n# s_k = x_{k+1} - x_k,  y_k = grad f_{k+1} - grad f_k\n# B_{k+1} = B_k + (y_k y_k^T) / (y_k^T s_k) - (B_k s_k s_k^T B_k) / (s_k^T B_k s_k)\n# Line search Wolfe conditions: Armijo sufficient decrease + curvature condition\n", domain_name)
        elif idx == 40: # stochastic_calculus
            return ("# Stochastic Calculus & Itô's Lemma\n# d X_t = mu(X_t, t) dt + sigma(X_t, t) dW_t\n# For f(X_t, t): df = (d f/dt + mu * d f/dx + (1/2)*sigma^2 * d^2 f/dx^2) dt + sigma * (d f/dx) dW_t\n# Fokker-Planck equation for probability density p(x, t): dp/dt = -d(mu*p)/dx + (1/2)*d^2(sigma^2*p)/dx^2\n", domain_name)
        elif idx == 41: # symplectic_geometry
            return ("# Symplectic Geometry & Hamiltonian Mechanics\n# Symplectic 2-form: omega = sum dp_i wedge dq^i, with d(omega) = 0 and omega^n non-degenerate\n# Hamilton's equations: dq^i/dt = dH/dp_i,  dp_i/dt = -dH/dq^i\n# Poisson bracket: {f, g} = sum (df/dq^i * dg/dp_i - df/dp_i * dg/dq^i)\n", domain_name)
        elif idx == 42: # combinatorics_graph
            return ("# Extremal Combinatorics & Spectral Graph Theory\n# Graph Laplacian: L = D - A, where D is degree matrix and A is adjacency matrix\n# Fiedler vector: eigenvector lambda_2 of L measures algebraic connectivity of graph G\n# Ramsey Theorem: R(k, l) guarantees monochromatic clique of size k or independent set of size l\n", domain_name)
        elif idx == 43: # information_theory
            return ("# Information Theory: Channel Capacity & Entropy\n# Shannon Entropy: H(X) = -sum p(x) * log2 p(x)\n# Kullback-Leibler Divergence: D_KL(P || Q) = sum P(x) * log(P(x) / Q(x))\n# Shannon Channel Capacity: C = max_{p(x)} I(X; Y) = max [ H(Y) - H(Y|X) ]\n", domain_name)
        elif idx == 44: # pde_elliptic_hyperbolic
            return ("# Partial Differential Equations: Laplace-Beltrami & Wave Equation\n# Heat kernel on Riemannian manifold (M, g): K_t(x, y) ~ (4*pi*t)^(-n/2) * exp(-d(x,y)^2 / (4t))\n# Wave equation d'Alembertian operator: Box u = (1/c^2) d^2 u / dt^2 - Delta_g u = 0\n", domain_name)
        elif idx == 45: # measure_ergodic_theory
            return ("# Measure Theory & Ergodic Dynamical Systems\n# Birkhoff Ergodic Theorem: (1/N) sum_{n=0}^{N-1} f(T^n x) -> int_X f d mu  almost everywhere\n# Radon-Nikodym Theorem: If nu is absolutely continuous w.r.t. mu, nu(A) = int_A (d nu / d mu) d mu\n", domain_name)
        elif idx == 46: # linear_algebra_tensors
            return ("# Tensor Algebra & Multilinear Algebra\n# Singular Value Decomposition: A = U * Sigma * V^T\n# Kronecker Product: (A (x) B) * (C (x) D) = (A * C) (x) (B * D)\n# Einstein Summation: T^{i_1...i_p}_{j_1...j_q} with contraction on matching indices\n", domain_name)
        else:          # 47: symbolic_math_cot
            return ("Question: Compute 45 * 12 - 30.\n<thought>\nStep 1: 45 * 12 = 540.\nStep 2: 540 - 30 = 510.\n</thought>\nAnswer: 510\n", domain_name)

    def generate_corpus(self, num_samples: int = 9600) -> List[Tuple[str, str]]:
        samples = []
        for i in range(num_samples):
            idx = i % len(OMNI_48_EXPERT_DOMAINS)
            samples.append(self.sample_by_index(idx))
        random.shuffle(samples)
        return samples
