"""
Omni-64 Master Polytope Expert Registry (IMF).

Complete 64-Domain Topology incorporating:
- Quantum Mathematics & Physics: Hilbert space density matrices, von Neumann entropy, Lindblad master equation, decoherence, tensor networks.
- Chaos Theory & Non-Linear Dynamics: Strange attractors, Lyapunov exponents, Poincaré maps, Feigenbaum constants.
- Game Theory & Mechanism Design: Minimax, Nash equilibria, Shapley coalitions, extensive-form games.
- Multilingual NLP: Cross-lingual grammatical and semantic alignment across global language families.
- Cyber Security & Reverse Engineering: ROP exploitation, binary CFG recovery, sanitizers, side-channel mitigation.
- Deep Mathematics: Differential geometry, Lie algebras, Algebraic topology, Category theory, Galois theory, Elliptic curves.
- Systems, Firmware & Assembly: C, C++, Zig, Rust, Linux Kernel, eBPF, MMIO drivers, x86-64 AVX2, ARM64.
- Accelerators & Differentiable: JAX, Triton, CUDA, Julia, Quantum circuits (Qiskit).
- Molecular Biology & Genomics: Watson-Crick DNA, Splice junctions, Codon ORFs, AlphaFold structural proteomics.
- Formal Logic & Verification: Lean 4, Coq, TLA+, SMT/Z3, HoTT path induction.
"""

from typing import Dict, List, Tuple
import random


OMNI_64_EXPERT_DOMAINS: List[str] = [
    # Group 1: Quantum Mathematics & Quantum Information (0-3)
    "quantum_math_density_matrices", # Hilbert space density operators, von Neumann entropy, Lindblad master equation
    "quantum_tensor_networks",       # Matrix Product States (MPS), PEPS, entanglement entropy, Kraus operators
    "quantum_computing_circuits",    # Unitary gates, Hadamard, CNOT, Quantum Fourier Transform, stabilizer codes
    "chaos_dynamical_systems",       # Lorenz strange attractor, Lyapunov exponents, Poincaré return maps, bifurcation

    # Group 2: Game Theory, Decision Theory & Economics (4-7)
    "game_theory_nash_minimax",      # Normal-form payoff matrices, Nash equilibrium, backward induction, zero-sum
    "cooperative_games_shapley",     # Characteristic function games, Shapley value, core, nucleolus
    "mechanism_design_auctions",     # Vickrey-Clarke-Groves (VCG) mechanisms, incentive compatibility, social welfare
    "multilingual_translation_nlp",   # Cross-lingual parallel bitext alignment (EN, FR, DE, ZH, JA, RU, AR)

    # Group 3: Deep Mathematics & Geometry (8-19)
    "diff_geometry_riemann",         # Riemann curvature tensor, Christoffel connection forms, Cartan frames
    "lie_groups_algebras_so_su",     # so(d), su(2), su(3), Killing form, root lattices, adjoint representation
    "algebraic_topology_homology",   # Simplicial homology, boundary operator partial^2 = 0, Betti numbers
    "category_theory_topoi",         # Adjunctions, Monads, Yoneda lemma, Sheaves, Grothendieck topoi
    "abstract_algebra_galois",       # Sylow theorems, field extensions, Galois correspondence, cyclotomic fields
    "complex_analysis_riemann",      # Cauchy residue theorem, conformal mappings, elliptic functions
    "algebraic_number_theory",       # Quadratic reciprocity, class groups, elliptic curve group law
    "functional_analysis_hilbert",   # Self-adjoint operators, spectral decomposition theorem, Sobolev norms
    "numerical_optimization_bfgs",   # Quasi-Newton BFGS, Lanczos eigenvalue solver, conjugate gradients
    "stochastic_calculus_ito",       # Itô lemma, Brownian motion diffusions, Fokker-Planck equations
    "symplectic_geometry_hamilton",  # Symplectic 2-forms, Hamiltonian vector fields, Poisson brackets
    "extremal_combinatorics_graph",  # Graph Laplacian eigenvalues, Fiedler vector, Ramsey numbers

    # Group 4: Formal Proofs, Logic & Verification (20-27)
    "lean4_interactive_proofs",      # Lean 4 core tactics (omega, Nat.mul_add, induction, rfl)
    "coq_gallina_verification",      # Coq inductive types, Calculus of Inductive Constructions
    "tla_plus_temporal_logic",       # TLA+ concurrent state machines, safety and liveness invariants
    "smt_z3_bitvectors",             # SMT-LIB QF_BV bit-vector equivalence and satisfiability
    "first_order_resolution_logic",  # Predicate calculus, Herbrand theorem, resolution refutation
    "modal_intuitionistic_logic",    # Kripke semantics, S4/S5 modal operators, Curry-Howard correspondence
    "type_theory_hott",              # Dependent types, Martin-Löf type theory, Univalence axiom
    "proof_cut_search_factorization",# ETH cut uncrossing, bidirectional meet-in-the-middle verification

    # Group 5: Cyber Security, Reverse Engineering & Vulnerability Analysis (28-35)
    "binary_exploitation_rop",       # Return-Oriented Programming (ROP) gadget chains, canary/ASLR bypass
    "reverse_engineering_cfg",       # Control-flow graph recovery, disassembly, decompilation patterns
    "memory_safety_auditing",        # Use-After-Free (UAF), double-free, heap metadata corruption detection
    "sanitizers_asan_ubsan",         # AddressSanitizer shadow memory poisoning, UndefinedBehaviorSanitizer
    "cryptography_protocols",        # Constant-time comparison, Ed25519 digital signatures, ChaCha20-Poly1305
    "network_security_pcap",         # TCP 3-way handshake analysis, TLS 1.3 cryptographic handshakes
    "web_security_xss_sqli",         # Cross-Site Scripting (XSS) context escaping, SQL injection AST filters
    "sidechannel_timing_defense",    # Cache-timing attack mitigation, constant-time arithmetic, memory zeroize

    # Group 6: Systems, Low-Level, Hardware & Firmware (36-47)
    "c_systems_posix",               # C17 non-blocking sockets, epoll event loops, atomic ring buffers
    "cpp_modern_concepts",           # C++20 concepts, PMR memory resources, ranges, move semantics
    "zig_systems_memory",            # Zig 0.13 custom allocators, explicit slices, comptime evaluation
    "rust_safe_systems",             # Rust ownership, borrow checker, Pin, atomics, Send/Sync invariants
    "linux_kernel_drivers",          # Linux kernel char devices, SLUB allocators, RCU read-copy-update
    "ebpf_xdp_packet_filters",       # eBPF XDP in-kernel packet filtering, BPF ring buffers, maps
    "hardware_firmware_mmio",        # MMIO UART, SPI/I2C controllers, GPIO registers, interrupt handlers
    "assembly_x86_64_avx",           # x86-64 NASM/GAS AVX2/AVX-512 SIMD vectorization, SysV ABI
    "assembly_arm_riscv",            # ARM64 AArch64 spinlocks, RISC-V CSR control and status registers
    "operating_systems_paging",      # Virtual memory paging, CR3 page tables, TLB invalidation, scheduling
    "cuda_cpp_kernels",              # CUDA C++ warp shuffles, shared memory tiles, cooperative groups
    "triton_gpu_fused",              # Triton JIT fused kernels, block pointers, compile-time autotuning

    # Group 7: Molecular Biology, Genomics & Natural Sciences (48-55)
    "genomics_watson_crick_dna",     # Watson-Crick double-strand reverse complementation equivariance
    "splice_transcriptomics",        # Eukaryotic splice junction donor (GT) and acceptor (AG) boundaries
    "proteomics_alphafold",          # AlphaFold residue pLDDT metrics, Ramachandran dihedral angles
    "cheminformatics_molecules",     # SMILES molecular representations, Lipinski Rule of 5, PAINS alerts
    "fluid_dynamics_navier_stokes",  # Incompressible Navier-Stokes PDEs, Lattice Boltzmann methods
    "astrophysics_relativity",       # Schwarzschild metric tensor, Gravitational time dilation, Geodesics
    "information_theory_entropy",    # Shannon entropy, Kullback-Leibler divergence, mutual information
    "pde_laplace_wave",              # Laplace-Beltrami operator, heat kernel diffusion, d'Alembertian wave

    # Group 8: Multi-Language Scripting & High-Performance Computing (56-63)
    "jax_differentiable_physics",    # JAX vmap, pjit, grad, lax.scan, Lie algebra Cayley step
    "julia_simd_computing",          # Julia multiple dispatch, @simd loops, inbounds vectorization
    "go_concurrent_systems",         # Go goroutines, channels, select, concurrent worker pools
    "haskell_pure_monads",           # Haskell pure functional programming, Monad transformers, lazy eval
    "ocaml_algebraic_types",         # OCaml algebraic data types, structural pattern matching
    "perl_regex_automata",           # Perl 5 fast regex stream automata, FASTA sequence processing
    "sql_recursive_cte",             # SQL recursive Common Table Expressions, window analytical functions
    "symbolic_math_cot_traces",      # Multi-step arithmetic reasoning with explicit <thought> registers
]


class Omni64DomainSynthesizer:
    def __init__(self, seed: int = 42):
        random.seed(seed)

    def sample_by_index(self, idx: int) -> Tuple[str, str]:
        domain_name = OMNI_64_EXPERT_DOMAINS[idx]

        # Group 1: Quantum Mathematics & Chaos
        if idx == 0:
            return ("# Quantum Mathematics: Density Operators & Lindblad Master Equation\n# Density matrix: rho = sum p_i |psi_i><psi_i|, with Tr(rho) = 1, rho >= 0\n# von Neumann Entropy: S(rho) = -Tr(rho * log(rho))\n# Lindblad Dissipator: d rho / dt = -i/hbar [H, rho] + sum_k (L_k rho L_k^dagger - 1/2 {L_k^dagger L_k, rho})\n", domain_name)
        elif idx == 1:
            return ("# Quantum Tensor Networks: Matrix Product States (MPS)\n# State decomposition: |Psi> = sum A^{s_1}_1 A^{s_2}_2 ... A^{s_N}_N |s_1 ... s_N>\n# Entanglement entropy across bipartition: S_A = -sum lambda_i^2 log(lambda_i^2) from Schmidt values\n", domain_name)
        elif idx == 2:
            return ("# Quantum Circuits: Quantum Fourier Transform (QFT)\nfrom qiskit import QuantumCircuit\nqc = QuantumCircuit(3)\nqc.h(0); qc.cp(3.14159/2, 1, 0); qc.cp(3.14159/4, 2, 0)\nqc.h(1); qc.cp(3.14159/2, 2, 1); qc.h(2)\n", domain_name)
        elif idx == 3:
            return ("# Chaos Theory: Lorenz Strange Attractor\n# dx/dt = sigma*(y - x),  dy/dt = x*(rho - z) - y,  dz/dt = x*y - beta*z\n# Parameters: sigma=10.0, rho=28.0, beta=8/3\n# Maximal Lyapunov Exponent lambda > 0 proves exponential sensitivity to initial conditions.\n", domain_name)

        # Group 2: Game Theory & NLP
        elif idx == 4:
            return ("// Game Theory: 2-Player Normal-Form Game & Minimax Theorem\n// Payoff Matrix P = [[(3, 3), (0, 5)], [(5, 0), (1, 1)]] (Prisoner's Dilemma)\n// Dominant Strategy: Defect for both players; Unique Nash Equilibrium at (Defect, Defect).\n", domain_name)
        elif idx == 5:
            return ("# Cooperative Game Theory: Shapley Value Calculation\n# phi_i(v) = sum_{S subset N \\ {i}} (|S|! * (|N| - |S| - 1)! / |N|!) * (v(S u {i}) - v(S))\n# Satisfies efficiency, symmetry, linearity, and null-player axioms uniquely.\n", domain_name)
        elif idx == 6:
            return ("# Mechanism Design: Vickrey-Clarke-Groves (VCG) Auction\n# Dominant strategy incentive compatibility (truth-telling is optimal):\n# Payment p_i = max_{k != i} sum_{j != i} v_j(k) - sum_{j != i} v_j(k*)\n", domain_name)
        elif idx == 7:
            return ("// Multilingual NLP Cross-Translation & Grammatical Alignment\nEN: The continuous Lie group SSM preserves information norm without exponential forgetting.\nFR: Le modèle d'état continu du groupe de Lie préserve la norme de l'information sans oubli exponentiel.\nDE: Das kontinuierliche Lie-Gruppen-Zustandsraummodell bewahrt die Informationsnorm ohne exponentielles Vergessen.\nZH: 连续李群状态空间模型在没有指数遗忘的情况下保持信息范数。\nJA: 連続リー群状態空間モデルは、指数関数的な忘却なしに情報ノルムを保存します。\n", domain_name)

        # Group 3: Deep Mathematics
        elif idx == 8:
            return ("# Differential Geometry: Riemann Curvature Tensor\n# R^l_ijk = d Gamma^l_ik / dx^j - d Gamma^l_ij / dx^k + Gamma^l_jm Gamma^m_ik - Gamma^l_km Gamma^m_ij\n", domain_name)
        elif idx == 9:
            return ("# Lie Algebras: Cartan-Killing Form B(X, Y) = Tr(ad_X compose ad_Y)\n# Skew-symmetric generators so(d) satisfy [A, B] = A B - B A with [A, B]^T = -[A, B]\n", domain_name)
        elif idx == 10:
            return ("# Simplicial Homology: Boundary operator partial_k compose partial_{k+1} = 0\n# Betti numbers b_k = rank(ker partial_k / im partial_{k+1})\n", domain_name)
        elif idx == 11:
            return ("# Category Theory: Adjunction F -| G\n# Natural isomorphism Hom_D(F(A), B) ~ Hom_C(A, G(B))\n# Yoneda Lemma: Nat(Hom(A, -), F) is naturally isomorphic to F(A)\n", domain_name)
        elif idx == 12:
            return ("# Abstract Algebra: Galois Theory & Field Extensions\n# Galois group Gal(L/K) intermediate subfields correspond bijectively to subgroups.\n", domain_name)
        elif idx == 13:
            return ("# Complex Analysis: Cauchy Residue Theorem\n# oint_gamma f(z) dz = 2 * pi * i * sum Residue(f, z_k)\n", domain_name)
        elif idx == 14:
            return ("# Algebraic Number Theory: Elliptic Curve Group Law\n# Weierstrass equation: y^2 = x^3 + a*x + b over finite field F_p\n", domain_name)
        elif idx == 15:
            return ("# Functional Analysis: Hilbert Space Spectral Decomposition\n# Self-adjoint operator T = int lambda d E(lambda)\n", domain_name)
        elif idx == 16:
            return ("# Numerical Optimization: BFGS Quasi-Newton Update\n# B_{k+1} = B_k + (y_k y_k^T)/(y_k^T s_k) - (B_k s_k s_k^T B_k)/(s_k^T B_k s_k)\n", domain_name)
        elif idx == 17:
            return ("# Stochastic Calculus: Itô Lemma\n# df(X_t) = f'(X_t) dX_t + (1/2) f''(X_t) (dX_t)^2\n", domain_name)
        elif idx == 18:
            return ("# Symplectic Geometry: Poisson Bracket on phase space\n# {f, g} = sum (df/dq_i * dg/dp_i - df/dp_i * dg/dq_i)\n", domain_name)
        elif idx == 19:
            return ("# Spectral Graph Theory: Graph Laplacian L = D - A\n# Fiedler eigenvalue lambda_2 measures algebraic connectivity.\n", domain_name)

        # Group 4: Formal Proofs & Logic
        elif idx == 20:
            return ("theorem add_comm_id (n m : Nat) : n + m = m + n := by\n  omega\n", domain_name)
        elif idx == 21:
            return ("Theorem plus_n_O : forall n : nat, n = n + 0.\nProof. intros n. reflexivity. Qed.\n", domain_name)
        elif idx == 22:
            return ("VARIABLE state\nInit == state = \"Idle\"\nNext == state = \"Idle\" /\\ state' = \"Active\"\nSpec == Init /\\ [][Next]_state\n", domain_name)
        elif idx == 23:
            return ("; SMT-LIB QF_BV bit-vector equivalence\n(declare-const x (_ BitVec 32))\n(assert (= (bvand x #x00000000) #x00000000))\n(check-sat)\n", domain_name)
        elif idx == 24:
            return ("% First-Order Logic Resolution\nparent(X, Y) :- father(X, Y).\nancestor(X, Z) :- parent(X, Y), ancestor(Y, Z).\n", domain_name)
        elif idx == 25:
            return ("# Modal Logic: Box(p -> q) -> (Box p -> Box q)\n# Kripke frame accessibility relation R(w, w')\n", domain_name)
        elif idx == 26:
            return ("-- Homotopy Type Theory: Path Induction\n-- Identity type Id_A(x, y) as paths; Univalence: (A ~ B) ~ (A = B)\n", domain_name)
        elif idx == 27:
            return ("# ETH Proof Cut Search: Factorizing reasoning across cut m = k/2\n# Reconciling forward trajectory with backward adjoint target.\n", domain_name)

        # Group 5: Cyber Security & Reverse Engineering
        elif idx == 28:
            return ("// Binary Exploitation: ROP gadget chain setup\n// pop rdi; ret (0x4011d3) -> puts@got -> puts@plt\nvoid exploit_rop_canary_bypass(void);\n", domain_name)
        elif idx == 29:
            return ("// Reverse Engineering: Control-Flow Graph Reconstruction\n// Basic blocks partitioned by conditional jump targets and call xrefs\n", domain_name)
        elif idx == 30:
            return ("// Memory Safety Auditing: Use-After-Free (UAF) Detection\n// Detect pointer dereference after free(ptr); zeroize dangling references\n", domain_name)
        elif idx == 31:
            return ("// Sanitizers: AddressSanitizer (ASAN) Poisoning Shadow Memory\n#include <sanitizer/asan_interface.h>\nASAN_POISON_MEMORY_REGION(addr, size);\n", domain_name)
        elif idx == 32:
            return ("// Cryptography Protocols: Constant-time comparison\nint ct_memcmp(const void *a, const void *b, size_t n) {\n  const uint8_t *x=a, *y=b; uint8_t d=0;\n  for(size_t i=0; i<n; ++i) d |= (x[i] ^ y[i]);\n  return d == 0;\n}\n", domain_name)
        elif idx == 33:
            return ("// Network Security & PCAP: TCP 3-way handshake analysis\n// SYN -> SYN-ACK -> ACK verification and window scaling factor check\n", domain_name)
        elif idx == 34:
            return ("// Web Security Mitigation: Context-aware HTML entity encoding\n// Prevent Reflected XSS by escaping <, >, &, \", and ' in output sink\n", domain_name)
        elif idx == 35:
            return ("// Side-Channel Timing Defense: Secure memory wipe\nvoid secure_zero(volatile void *p, size_t n) {\n  volatile uint8_t *b = p; while (n--) *b++ = 0;\n}\n", domain_name)

        # Group 6: Systems, Low-Level, Hardware & Firmware
        elif idx == 36:
            return ("// C17 POSIX epoll\n#include <sys/epoll.h>\nint set_nb(int fd) { return fcntl(fd, F_SETFL, O_NONBLOCK); }\n", domain_name)
        elif idx == 37:
            return ("// C++20 Concepts\ntemplate <std::integral T> T add(T a, T b) noexcept { return a + b; }\n", domain_name)
        elif idx == 38:
            return ("// Zig 0.13 Allocator\nconst std = @import(\"std\");\npub fn alloc_buf(a: std.mem.Allocator, len: usize) ![]u8 { return try a.alloc(u8, len); }\n", domain_name)
        elif idx == 39:
            return ("// Rust Systems: Atomic fetch-add\npub fn inc(val: &std::sync::atomic::AtomicUsize) { val.fetch_add(1, std::sync::atomic::Ordering::SeqCst); }\n", domain_name)
        elif idx == 40:
            return ("// Linux Kernel Char Driver\n#include <linux/fs.h>\nstatic int dev_open(struct inode *i, struct file *f) { return 0; }\n", domain_name)
        elif idx == 41:
            return ("// Linux eBPF XDP\nSEC(\"xdp\") int drop_all(struct xdp_md *ctx) { return XDP_DROP; }\nchar _lic[] SEC(\"license\") = \"GPL\";\n", domain_name)
        elif idx == 42:
            return ("// Firmware MMIO Register\n#define UART_RHR (*(volatile uint8_t*)0x10000000)\nvoid uart_write(char c) { UART_RHR = (uint8_t)c; }\n", domain_name)
        elif idx == 43:
            return ("// x86-64 AVX2\n.globl vec_dot\nvec_dot:\n  vmovups (%rdi), %ymm0\n  vfmadd231ps (%rsi), %ymm0, %ymm1\n  ret\n", domain_name)
        elif idx == 44:
            return ("// ARM64 AArch64 Spinlock\n.globl spin_acquire\nspin_acquire:\n  ldaxr w1, [x0]\n  cbnz w1, spin_acquire\n  stxr w2, w1, [x0]\n  ret\n", domain_name)
        elif idx == 45:
            return ("// Operating Systems Virtual Memory Paging\n// CR3 page directory base register load and TLB invlpg instruction\n", domain_name)
        elif idx == 46:
            return ("// CUDA C++ Warp Shuffle\n__device__ float warp_sum(float val) {\n  for (int o = 16; o > 0; o /= 2) val += __shfl_down_sync(0xffffffff, val, o);\n  return val;\n}\n", domain_name)
        elif idx == 47:
            return ("# Triton GPU kernel\nimport triton\nimport triton.language as tl\n@triton.jit\ndef add_k(x_ptr, y_ptr, n): pid = tl.program_id(0); tl.store(y_ptr + pid, tl.load(x_ptr + pid))\n", domain_name)

        # Group 7: Molecular Biology & Natural Sciences
        elif idx == 48:
            return ("; FASTA Watson-Crick DNA\n>chr1:100-140\nATGCGATCGATCGATCGATCGATCGATCGATCGA\n; Reverse Complement:\nTCGATCGATCGATCGATCGATCGATCGATCGCAT\n", domain_name)
        elif idx == 49:
            return ("; Eukaryotic Splice Junction\n>donor_acceptor_motif\nAGGTAAGT ... TTTCTAG\n// 5' GT donor, 3' AG acceptor\n", domain_name)
        elif idx == 50:
            return ("// AlphaFold Structural Proteomics\n# Residue pLDDT Confidence: >90 (Very High), 70-90 (Confident), <50 (Disordered)\nPHI = -60.0; PSI = -45.0  # Alpha-helix Ramachandran backbone\n", domain_name)
        elif idx == 51:
            return ("# SMILES Cheminformatics\nSMILES = 'CC(=O)Oc1ccccc1C(=O)O'  # Aspirin\nMW = 180.16; LogP = 1.19; HBD = 1; HBA = 4\n", domain_name)
        elif idx == 52:
            return ("# Navier-Stokes Incompressible Flow\n# du/dt + (u.grad)u = -(1/rho)grad(p) + nu*laplace(u)\n", domain_name)
        elif idx == 53:
            return ("# General Relativity Schwarzschild Metric\n# ds^2 = -(1 - 2GM/rc^2) c^2 dt^2 + (1 - 2GM/rc^2)^(-1) dr^2 + r^2 dOmega^2\n", domain_name)
        elif idx == 54:
            return ("# Information Theory: Shannon Channel Capacity\n# C = max_{p(x)} I(X; Y) = max [ H(Y) - H(Y|X) ]\n", domain_name)
        elif idx == 55:
            return ("# PDEs: Wave Equation d'Alembertian Operator\n# Box u = (1/c^2) d^2 u / dt^2 - Delta u = 0\n", domain_name)

        # Group 8: Multi-Language Scripting & Computing
        elif idx == 56:
            return ("# JAX Differentiable Lie step\nimport jax.numpy as jnp\nfrom jax import jit\n@jit\ndef cayley(h, A): return jnp.dot(jnp.linalg.inv(jnp.eye(A.shape[0]) + A), h)\n", domain_name)
        elif idx == 57:
            return ("# Julia High-Performance Computing\nfunction axpy!(a::Float64, x::Vector{Float64}, y::Vector{Float64})\n    @simd for i in eachindex(x) @inbounds y[i] += a * x[i] end\nend\n", domain_name)
        elif idx == 58:
            return ("// Go Concurrency\nfunc worker(ch <-chan int, out chan<- int) {\n    for val := range ch { out <- val * 2 }\n}\n", domain_name)
        elif idx == 59:
            return ("-- Haskell Pure Functional\nquicksort :: (Ord a) => [a] -> [a]\nquicksort [] = []\nquicksort (x:xs) = quicksort [y | y <- xs, y <= x] ++ [x] ++ quicksort [y | y <- xs, y > x]\n", domain_name)
        elif idx == 60:
            return ("(* OCaml Pattern Matching *)\ntype 'a tree = Leaf | Node of 'a * 'a tree * 'a tree\nlet rec size = function Leaf -> 0 | Node (_, l, r) -> 1 + size l + size r\n", domain_name)
        elif idx == 61:
            return ("#!/usr/bin/env perl\nwhile (<>) { chomp; if (/^>(\\S+)/) { print \"Header: $1\\n\"; } }\n", domain_name)
        elif idx == 62:
            return ("-- SQL Recursive CTE\nWITH RECURSIVE H AS (\n  SELECT id, parent_id FROM nodes WHERE parent_id IS NULL\n  UNION ALL\n  SELECT n.id, n.parent_id FROM nodes n JOIN H ON n.parent_id = H.id\n) SELECT * FROM H;\n", domain_name)
        else:
            return ("Question: Compute 45 * 12 - 30.\n<thought>\nStep 1: 45 * 12 = 540.\nStep 2: 540 - 30 = 510.\n</thought>\nAnswer: 510\n", domain_name)

    def generate_corpus(self, num_samples: int = 12800) -> List[Tuple[str, str]]:
        samples = []
        for i in range(num_samples):
            idx = i % len(OMNI_64_EXPERT_DOMAINS)
            samples.append(self.sample_by_index(idx))
        random.shuffle(samples)
        return samples
