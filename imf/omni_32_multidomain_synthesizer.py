"""
Omni-Polytope Expert Registry: 32 Specialized Geometric Domain Centroids.

Covers:
1. Low-Level Systems & Firmware: C, C++, Zig, Rust, Linux Kernel, eBPF, Firmware MMIO, Hardware Drivers.
2. Architecture & ISAs: x86-64 (AVX2/AVX-512), ARM64 AArch64, RISC-V.
3. Accelerators & Differentiable: JAX, Triton, CUDA, PyTorch, OpenCL.
4. Scientific & Physical:
   - Genomics & Transcriptomics (Watson-Crick RC, Splice sites, Codons)
   - Structural Biology & Proteomics (AlphaFold pLDDT, Ramachandran angles)
   - Chemistry & Cheminformatics (SMILES, Lipinski, PAINS alerts)
   - Astrophysics & General Relativity (Schwarzschild tensors, Geodesics)
   - Quantum Computing (Qiskit circuits, Hadamard, CNOT, Statevectors)
   - Fluid Dynamics & PDEs (Navier-Stokes, Lattice Boltzmann)
5. Languages & Environments:
   - Julia (Multiple dispatch, SIMD loops)
   - Go (Goroutines, channels, defer)
   - Swift (Protocols, ARC, value types)
   - Haskell (Monads, lazy evaluation, category theory)
   - OCaml (Algebraic data types, pattern matching)
   - Perl (Regex stream processing, FASTA parsing)
   - Lua / Neovim API (Metatables, coroutines)
   - Bash & Shell (POSIX, trap, pipelines)
   - SQL & Relational Databases (CTEs, Window functions, ACID)
   - HTML5 & Web Standards (Semantic DOM, ARIA accessibility)
6. Formal Logic, Verification & Math:
   - Lean 4 (Interactive tactics, inductive proofs)
   - Coq / Gallina (Calculus of inductive constructions)
   - TLA+ (State-machine temporal specification)
   - Cryptography (Constant-time, ChaCha20, Ed25519)
   - Symbolic Math & Algebra (Multi-step CoT arithmetic)
   - Category Theory (Functors, natural transformations, monoids)
"""

from typing import Dict, List, Tuple
import random


OMNI_32_EXPERT_DOMAINS: List[str] = [
    "c_systems",             # 0: C17 POSIX epoll, lock-free queues
    "cpp_modern",            # 1: C++20 concepts, PMR allocators, RAII
    "zig_systems",           # 2: Zig 0.13 memory allocations & slices
    "rust_systems",          # 3: Rust borrow checker, atomics, Send/Sync
    "linux_kernel_ebpf",     # 4: Linux Kernel drivers & eBPF XDP
    "hardware_firmware",     # 5: MMIO UART, SPI/I2C, GPIO registers
    "assembly_x86_64",       # 6: x86-64 NASM/GAS AVX2/AVX-512
    "assembly_arm_riscv",    # 7: ARM64 AArch64 & RISC-V CSRs
    "jax_accelerators",      # 8: JAX vmap, lax.scan, Cayley Lie step
    "triton_gpu",            # 9: Triton JIT block pointers & autotune
    "cuda_kernels",          # 10: CUDA C++ warp shuffles & shared memory
    "genomics_dna",          # 11: Watson-Crick reverse complement, CpG
    "splice_transcriptome",  # 12: Eukaryotic splice donor/acceptor junctions
    "proteomics_structural", # 13: 6-Frame codon ORFs & AlphaFold pLDDT
    "cheminformatics",       # 14: SMILES, Lipinski Rule of 5, SMARTS
    "astrophysics_relativity",# 15: Schwarzschild metric, Geodesic tensors
    "quantum_computing",     # 16: Qiskit quantum circuits, Bell states
    "fluid_dynamics_pde",    # 17: Navier-Stokes & Lattice Boltzmann
    "julia_computing",       # 18: Julia multiple dispatch & @simd
    "go_concurrency",        # 19: Go channels, goroutines, select
    "swift_systems",         # 20: Swift protocols, ARC, value semantics
    "haskell_pure",          # 21: Haskell monads & lazy evaluation
    "ocaml_types",           # 22: OCaml algebraic data types & matching
    "perl_text",             # 23: Perl 5 regex stream automata
    "lua_runtime",           # 24: Lua metatables & Neovim API
    "bash_posix",            # 25: POSIX shell, set -euo pipefail
    "sql_relational",        # 26: SQL recursive CTEs & window functions
    "web_html5",             # 27: HTML5 semantic DOM & ARIA telemetry
    "lean4_proofs",          # 28: Lean 4 formal tactics & induction
    "coq_formal",            # 29: Coq Gallina inductive specifications
    "cryptography_security", # 30: Constant-time comparison & Ed25519
    "symbolic_math_cot",     # 31: Multi-step arithmetic <thought> traces
]


class OmniPolytopeDomainSynthesizer:
    def __init__(self, seed: int = 42):
        random.seed(seed)

    def sample_by_index(self, idx: int) -> Tuple[str, str]:
        domain_name = OMNI_32_EXPERT_DOMAINS[idx]

        if idx == 0:  # c_systems
            return ("// C17 POSIX epoll\n#include <sys/epoll.h>\nint set_nb(int fd) { return fcntl(fd, F_SETFL, O_NONBLOCK); }\n", domain_name)
        elif idx == 1:  # cpp_modern
            return ("// C++20 Concepts\ntemplate <std::integral T> T add(T a, T b) noexcept { return a + b; }\n", domain_name)
        elif idx == 2:  # zig_systems
            return ("// Zig 0.13\nconst std = @import(\"std\");\npub fn slice(buf: []u8) []u8 { return buf[0..]; }\n", domain_name)
        elif idx == 3:  # rust_systems
            return ("// Rust Systems\npub fn atomic_inc(val: &std::sync::atomic::AtomicUsize) { val.fetch_add(1, std::sync::atomic::Ordering::SeqCst); }\n", domain_name)
        elif idx == 4:  # linux_kernel_ebpf
            return ("// Linux eBPF\nSEC(\"xdp\") int drop(struct xdp_md *ctx) { return XDP_DROP; }\nchar _lic[] SEC(\"license\") = \"GPL\";\n", domain_name)
        elif idx == 5:  # hardware_firmware
            return ("// Firmware MMIO\n#define UART_RHR (*(volatile uint8_t*)0x10000000)\nvoid putc(char c) { UART_RHR = (uint8_t)c; }\n", domain_name)
        elif idx == 6:  # assembly_x86_64
            return ("// x86-64 AVX2\n.globl vec_dot\nvec_dot:\n  vmovups (%rdi), %ymm0\n  vfmadd231ps (%rsi), %ymm0, %ymm1\n  ret\n", domain_name)
        elif idx == 7:  # assembly_arm_riscv
            return ("// ARM64 AArch64 Spinlock\n.globl lock\nlock:\n  ldaxr w1, [x0]\n  cbnz w1, lock\n  stxr w2, w1, [x0]\n  ret\n", domain_name)
        elif idx == 8:  # jax_accelerators
            return ("# JAX Differentiable Lie step\nimport jax.numpy as jnp\nfrom jax import jit, vmap\n@jit\ndef cayley(h, A): return jnp.dot(jnp.linalg.inv(jnp.eye(A.shape[0]) + A), h)\n", domain_name)
        elif idx == 9:  # triton_gpu
            return ("# Triton GPU kernel\nimport triton\nimport triton.language as tl\n@triton.jit\ndef add_k(x_ptr, y_ptr, n): pid = tl.program_id(0); tl.store(y_ptr + pid, tl.load(x_ptr + pid))\n", domain_name)
        elif idx == 10: # cuda_kernels
            return ("// CUDA C++ Warp Shuffle\n__device__ float warp_sum(float val) {\n  for (int o = 16; o > 0; o /= 2) val += __shfl_down_sync(0xffffffff, val, o);\n  return val;\n}\n", domain_name)
        elif idx == 11: # genomics_dna
            return ("; FASTA Watson-Crick DNA\n>chr1:100-140\nATGCGATCGATCGATCGATCGATCGATCGATCGA\n; Reverse Complement:\nTCGATCGATCGATCGATCGATCGATCGATCGCAT\n", domain_name)
        elif idx == 12: # splice_transcriptome
            return ("; Eukaryotic Splice Junction\n>donor_acceptor_motif\nAGGTAAGT ... TTTCTAG\n// 5' GT donor, 3' AG acceptor\n", domain_name)
        elif idx == 13: # proteomics_structural
            return ("// AlphaFold Structural Proteomics\n# Residue pLDDT Confidence: >90 (Very High), 70-90 (Confident), <50 (Disordered)\nPHI = -60.0; PSI = -45.0  # Alpha-helix Ramachandran backbone\n", domain_name)
        elif idx == 14: # cheminformatics
            return ("# SMILES Cheminformatics\nSMILES = 'CC(=O)Oc1ccccc1C(=O)O'  # Aspirin\nMW = 180.16; LogP = 1.19; HBD = 1; HBA = 4\n", domain_name)
        elif idx == 15: # astrophysics_relativity
            return ("# General Relativity\n# Schwarzschild radius: r_s = 2GM / c^2\nr_s = (2.0 * 6.6743e-11 * 1.989e30) / (299792458 ** 2)\n", domain_name)
        elif idx == 16: # quantum_computing
            return ("# Quantum Computing: Bell State |Phi+>\nfrom qiskit import QuantumCircuit\nqc = QuantumCircuit(2)\nqc.h(0)\nqc.cx(0, 1)\n", domain_name)
        elif idx == 17: # fluid_dynamics_pde
            return ("# Navier-Stokes PDE: du/dt + (u.grad)u = -grad(p)/rho + nu*laplace(u)\n# Incompressible velocity divergence: div(u) = 0\n", domain_name)
        elif idx == 18: # julia_computing
            return ("# Julia High-Performance Computing\nfunction axpy!(a::Float64, x::Vector{Float64}, y::Vector{Float64})\n    @simd for i in eachindex(x) @inbounds y[i] += a * x[i] end\nend\n", domain_name)
        elif idx == 19: # go_concurrency
            return ("// Go Concurrency\nfunc worker(ch <-chan int, out chan<- int) {\n    for val := range ch { out <- val * 2 }\n}\n", domain_name)
        elif idx == 20: # swift_systems
            return ("// Swift Protocol-Oriented\nprotocol Computable { associatedtype Output; func compute() -> Output }\n", domain_name)
        elif idx == 21: # haskell_pure
            return ("-- Haskell Pure Functional\nquicksort :: (Ord a) => [a] -> [a]\nquicksort [] = []\nquicksort (x:xs) = quicksort [y | y <- xs, y <= x] ++ [x] ++ quicksort [y | y <- xs, y > x]\n", domain_name)
        elif idx == 22: # ocaml_types
            return ("(* OCaml Algebraic Data Types *)\ntype 'a tree = Leaf | Node of 'a * 'a tree * 'a tree\nlet rec depth = function Leaf -> 0 | Node (_, l, r) -> 1 + max (depth l) (depth r)\n", domain_name)
        elif idx == 23: # perl_text
            return ("#!/usr/bin/env perl\nwhile (<>) { chomp; if (/^>(\\S+)/) { print \"Header: $1\\n\"; } }\n", domain_name)
        elif idx == 24: # lua_runtime
            return ("-- Lua Metatable Class Pattern\nlocal Vector = {}\nVector.__index = Vector\nfunction Vector.new(x, y) return setmetatable({x=x, y=y}, Vector) end\n", domain_name)
        elif idx == 25: # bash_posix
            return ("#!/usr/bin/env bash\nset -euo pipefail\ntrap 'echo Error on line $LINENO >&2' ERR\n", domain_name)
        elif idx == 26: # sql_relational
            return ("-- SQL Recursive CTE\nWITH RECURSIVE Hierarchy AS (\n  SELECT id, parent_id FROM nodes WHERE parent_id IS NULL\n  UNION ALL\n  SELECT n.id, n.parent_id FROM nodes n JOIN Hierarchy h ON n.parent_id = h.id\n) SELECT * FROM Hierarchy;\n", domain_name)
        elif idx == 27: # web_html5
            return ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\"></head><body><main role=\"main\"><h1>IMF</h1></main></body></html>\n", domain_name)
        elif idx == 28: # lean4_proofs
            return ("theorem add_comm_id (n m : Nat) : n + m = m + n := by\n  omega\n", domain_name)
        elif idx == 29: # coq_formal
            return ("(* Coq Gallina *)\nTheorem plus_n_O : forall n : nat, n = n + 0.\nProof. intros n. rewrite <- plus_n_O_first. reflexivity. Qed.\n", domain_name)
        elif idx == 30: # cryptography_security
            return ("// Constant-Time Comparison\nint ct_eq(const uint8_t *a, const uint8_t *b, size_t n) {\n  uint8_t d = 0; for (size_t i=0; i<n; ++i) d |= (a[i] ^ b[i]); return d == 0;\n}\n", domain_name)
        else:          # symbolic_math_cot
            return ("Question: Compute 45 * 12 - 30.\n<thought>\nStep 1: 45 * 12 = 540.\nStep 2: 540 - 30 = 510.\n</thought>\nAnswer: 510\n", domain_name)

    def generate_corpus(self, num_samples: int = 6400) -> List[Tuple[str, str]]:
        samples = []
        for i in range(num_samples):
            idx = i % len(OMNI_32_EXPERT_DOMAINS)
            samples.append(self.sample_by_index(idx))
        random.shuffle(samples)
        return samples
