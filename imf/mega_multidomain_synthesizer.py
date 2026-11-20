"""
Mega-Domain Expert Synthesizer for IMF (Interaction Model Foundations).

Defines 16 specialized domain expert generators:
 1. C & C++ Systems: POSIX epoll, lock-free queues, C++20 concepts, atomics
 2. Zig Systems: Allocators, slices, error unions, comptime
 3. Hardware & Firmware: MMIO UART, SPI/I2C registers, GPIO bit-banging
 4. Assembly & ISAs: x86-64 AVX2/AVX-512, ARM64 spinlocks, RISC-V CSRs
 5. JAX Differentiable Computing: vmap, pjit, grad, lax.scan, Lie algebra Cayley step
 6. HTML5 & Web: Semantic DOM, ARIA accessibility, Canvas, SVG
 7. Perl Scripting: Fast regex automata, FASTA genomic pattern extraction
 8. Genomics & Bioinformatics: Watson-Crick reverse complementation, splice junctions, codon ORFs
 9. Chemistry & Cheminformatics: SMILES representations, RDKit descriptors, reaction SMARTS
10. Astrophysics & Relativistic Physics: Geodesic metric tensors, Schwarzschild radius, Lorentz boosts
11. Cryptography & Security: Constant-time comparison, Ed25519 signatures, ChaCha20-Poly1305, ASAN/UBSAN
12. Rust Safe Systems: Ownership, borrow checker, Pin, atomics, Send/Sync
13. CUDA & Triton Kernels: Block pointers, warp shuffles, shared memory tiles
14. SQL & Relational Data: CTEs, window functions, B-tree indexes, query plans
15. Formal Logic & Lean 4: Interactive theorem proving, omega, Nat.mul_add, induction
16. Symbolic Mathematics: Multi-step arithmetic traces with <thought> execution registers
"""

from typing import Dict, List, Tuple
import random


class MegaDomainSynthesizer:
    def __init__(self, seed: int = 42):
        random.seed(seed)

    # 1. C & C++
    def sample_c_cpp(self) -> str:
        return """// C17 / C++20: Lock-free atomic ring buffer
#include <stdatomic.h>
#include <stddef.h>

struct LockFreeRing {
    atomic_size_t head;
    atomic_size_t tail;
    size_t capacity;
    int *buffer;
};

void ring_init(struct LockFreeRing *r, int *buf, size_t cap) {
    atomic_init(&r->head, 0);
    atomic_init(&r->tail, 0);
    r->capacity = cap;
    r->buffer = buf;
}
"""

    # 2. Zig
    def sample_zig(self) -> str:
        return """// Zig 0.13: Safe memory allocator and slice operations
const std = @import("std");

pub const StaticQueue = struct {
    items: []u32,
    head: usize = 0,
    tail: usize = 0,

    pub fn init(buffer: []u32) StaticQueue {
        return .{
            .items = buffer,
            .head = 0,
            .tail = 0,
        };
    }

    pub fn push(self: *StaticQueue, value: u32) !void {
        if (self.tail >= self.items.len) return error.QueueFull;
        self.items[self.tail] = value;
        self.tail += 1;
    }
};
"""

    # 3. Hardware & Firmware
    def sample_hardware_firmware(self) -> str:
        return """// Firmware: MMIO UART and SPI Control Registers
#include <stdint.h>

#define UART0_BASE    0x10000000
#define UART_RHR      (*(volatile uint8_t*)(UART0_BASE + 0x00))
#define UART_LSR      (*(volatile uint8_t*)(UART0_BASE + 0x05))
#define UART_LSR_THRE 0x20

void uart_putc(char c) {
    while ((UART_LSR & UART_LSR_THRE) == 0) {
        // Wait until transmitter holding register is empty
    }
    UART_RHR = (uint8_t)c;
}
"""

    # 4. Assembly & ISAs
    def sample_assembly(self) -> str:
        return """// x86-64 / ARM64 Assembly: Vectorized dot product (AVX2)
.globl vec_dot_avx2
.type vec_dot_avx2, @function
vec_dot_avx2:
    vzeroall
    vxorps %ymm0, %ymm0, %ymm0
.L_loop:
    vmovups (%rdi), %ymm1
    vmovups (%rsi), %ymm2
    vfmadd231ps %ymm2, %ymm1, %ymm0
    addq $32, %rdi
    addq $32, %rsi
    subq $8, %rdx
    jg .L_loop
    ret
"""

    # 5. JAX Differentiable Computing
    def sample_jax(self) -> str:
        return """# JAX: Vectorized Lie group trajectory step using vmap and lax.scan
import jax
import jax.numpy as jnp
from jax import grad, jit, vmap

@jit
def cayley_step(h, A):
    d = A.shape[0]
    eye = jnp.eye(d)
    U = jnp.linalg.solve(eye + A, eye - A)
    return jnp.dot(U, h)

@jit
def batch_trajectory(states, generators):
    return vmap(cayley_step, in_axes=(0, 0))(states, generators)
"""

    # 6. HTML5 & Web
    def sample_html(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>IMF Polytope Virtual Grid Monitor</title>
</head>
<body>
    <main role="main">
        <section aria-label="16-Expert Polytope Routing">
            <h1>IMF Geometric MoPE Telemetry</h1>
            <meter id="disp-gauge" min="0" max="1" value="0.94">94%</meter>
        </section>
    </main>
</body>
</html>
"""

    # 7. Perl Scripting
    def sample_perl(self) -> str:
        return """#!/usr/bin/env perl
use strict;
use warnings;

sub parse_fasta_splice_sites {
    my ($file) = @_;
    open(my $fh, '<', $file) or die "Cannot open $file: $!";
    my ($header, $seq) = ('', '');
    while (my $line = <$fh>) {
        chomp $line;
        if ($line =~ /^>(.*)/) { $header = $1; }
        else { $seq .= uc($line); }
    }
    close $fh;
    while ($seq =~ /(?=([ACGT]{3}GT[ACGT]{3}))/g) {
        print "Donor candidate at $-[0]: $1\\n";
    }
}
"""

    # 8. Genomics & Molecular Biology
    def sample_genomics(self) -> str:
        return """; FASTA Eukaryotic Splice Domain Region
>chr19:588581-588640 forward_strand
TAAGTTGCAGAGGTAAGTTCGTATCCAGGTAATTTTCTAGGATACCCATTGACCGGCCTA
; Reverse Complement (Watson-Crick Equivariant):
>chr19:588581-588640 reverse_strand
TAGGCCGGTCAATGGGTATCCTAGAAAATTACCTGGATACGAACCTTACCAACTTA
// Motifs: Donor 5'-GT (AGGTAAGT), Acceptor 3'-AG (TTTCTAG)
"""

    # 9. Chemistry & Cheminformatics
    def sample_chemistry(self) -> str:
        return """# Cheminformatics: SMILES canonicalization and Lipinski Rule of 5
# Molecule: Aspirin (acetylsalicylic acid)
SMILES = "CC(=O)Oc1ccccc1C(=O)O"
IUPAC = "2-acetoxybenzoic acid"
Molecular_Weight = 180.16  # g/mol (< 500 Da)
LogP = 1.19                # cLogP (< 5)
H_Bond_Donors = 1          # (< 5)
H_Bond_Acceptors = 4       # (< 10)
# Structural Alert Check: No PAINS toxicophores detected.
"""

    # 10. Astrophysics & Relativistic Physics
    def sample_astrophysics(self) -> str:
        return """# Relativistic Astrophysics: Schwarzschild metric & Gravitational Redshift
# ds^2 = -(1 - 2GM/rc^2) c^2 dt^2 + (1 - 2GM/rc^2)^(-1) dr^2 + r^2 dOmega^2
G = 6.67430e-11   # Gravitational constant (m^3 kg^-1 s^-2)
c = 299792458     # Speed of light (m/s)
M_sun = 1.989e30  # Solar mass (kg)

def schwarzschild_radius(mass_kg):
    return (2.0 * G * mass_kg) / (c ** 2)

r_s = schwarzschild_radius(M_sun)  # ~2953.25 meters
"""

    # 11. Cryptography & Security
    def sample_cryptography(self) -> str:
        return """// Cryptography: Constant-time byte array comparison (side-channel resistant)
#include <stdint.h>
#include <stddef.h>

int crypto_verify_constant_time(const uint8_t *a, const uint8_t *b, size_t len) {
    uint8_t diff = 0;
    for (size_t i = 0; i < len; ++i) {
        diff |= (a[i] ^ b[i]);
    }
    // Returns 0 if equal, -1 otherwise (no branching on data)
    return (1 & ((diff - 1) >> 8)) - 1;
}
"""

    # 12. Rust Safe Systems
    def sample_rust(self) -> str:
        return """pub fn fibonacci(n: u32) -> u64 {
    let mut a: u64 = 0;
    let mut b: u64 = 1;
    for _ in 0..n {
        let temp = a + b;
        a = b;
        b = temp;
    }
    a
}

pub struct Stack<T> {
    elements: Vec<T>,
}

impl<T> Stack<T> {
    pub fn new() -> Self { Stack { elements: Vec::new() } }
    pub fn push(&mut self, item: T) { self.elements.push(item); }
    pub fn pop(&mut self) -> Option<T> { self.elements.pop() }
}
"""

    # 13. CUDA & Triton GPU Kernels
    def sample_gpu_kernels(self) -> str:
        return """import triton
import triton.language as tl

@triton.jit
def fused_add_kernel(x_ptr, y_ptr, out_ptr, n_elements, BLOCK_SIZE: tl.constexpr):
    pid = tl.program_id(axis=0)
    offsets = pid * BLOCK_SIZE + tl.arange(0, BLOCK_SIZE)
    mask = offsets < n_elements
    x = tl.load(x_ptr + offsets, mask=mask)
    y = tl.load(y_ptr + offsets, mask=mask)
    tl.store(out_ptr + offsets, x + y, mask=mask)
"""

    # 14. SQL & Relational Databases
    def sample_sql(self) -> str:
        return """-- SQL: Hierarchical Common Table Expression (CTE) & Window Functions
WITH RECURSIVE CategoryTree AS (
    SELECT id, parent_id, name, 0 AS depth
    FROM categories WHERE parent_id IS NULL
    UNION ALL
    SELECT c.id, c.parent_id, c.name, ct.depth + 1
    FROM categories c
    JOIN CategoryTree ct ON c.parent_id = ct.id
)
SELECT id, name, depth,
       ROW_NUMBER() OVER (PARTITION BY depth ORDER BY name) as rank_in_tier
FROM CategoryTree;
"""

    # 15. Formal Logic & Lean 4
    def sample_lean4(self) -> str:
        return """theorem add_comm_id (n m : Nat) : n + m = m + n := by
  omega

theorem mul_distrib_add (a b c : Nat) : a * (b + c) = a * b + a * c := by
  exact Nat.mul_add a b c

theorem le_transitive (a b c : Nat) (h1 : a ≤ b) (h2 : b ≤ c) : a ≤ c := by
  exact Nat.le_trans h1 h2
"""

    # 16. Symbolic Mathematics
    def sample_math(self) -> str:
        v1 = random.randint(12, 85)
        v2 = random.randint(3, 14)
        v3 = random.randint(5, 25)
        product = v1 * v2
        final_ans = product - v3
        return f"""Question: A logistics facility stores {v1} crates on each of {v2} shelves. Later, {v3} crates are shipped out. How many crates remain in the facility?
<thought>
Step 1: Calculate the initial total number of crates stored across all shelves.
Initial crates = {v1} crates/shelf * {v2} shelves = {product} crates.
Step 2: Account for the outgoing crates shipped out from inventory.
Remaining crates = {product} - {v3} = {final_ans}.
</thought>
Answer: {final_ans}
"""

    def generate_sample(self) -> Tuple[str, str]:
        dice = random.random()
        if dice < 0.07:
            return self.sample_c_cpp(), "systems_c_cpp"
        elif dice < 0.13:
            return self.sample_zig(), "systems_zig"
        elif dice < 0.19:
            return self.sample_hardware_firmware(), "hardware_firmware"
        elif dice < 0.25:
            return self.sample_assembly(), "assembly_isa"
        elif dice < 0.31:
            return self.sample_jax(), "jax_accelerators"
        elif dice < 0.37:
            return self.sample_html(), "web_html"
        elif dice < 0.43:
            return self.sample_perl(), "scripting_perl"
        elif dice < 0.50:
            return self.sample_genomics(), "genomics_biology"
        elif dice < 0.57:
            return self.sample_chemistry(), "chemistry_cheminformatics"
        elif dice < 0.64:
            return self.sample_astrophysics(), "astrophysics_relativity"
        elif dice < 0.71:
            return self.sample_cryptography(), "cryptography_security"
        elif dice < 0.78:
            return self.sample_rust(), "systems_rust"
        elif dice < 0.84:
            return self.sample_gpu_kernels(), "gpu_kernels_triton_cuda"
        elif dice < 0.90:
            return self.sample_sql(), "sql_relational"
        elif dice < 0.95:
            return self.sample_lean4(), "formal_logic_lean4"
        else:
            return self.sample_math(), "symbolic_math"

    def generate_corpus(self, num_samples: int = 4000) -> List[Tuple[str, str]]:
        return [self.generate_sample() for _ in range(num_samples)]
