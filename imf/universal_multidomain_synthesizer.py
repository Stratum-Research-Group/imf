"""
Comprehensive Multi-Domain Expert Synthesizer for IMF (Interaction Model Foundations).

Expanded Domain Expert Centroids:
1. Systems & Low-Level: C, C++, Zig, Linux Kernel & Drivers, Hardware/Firmware Register Interfaces.
2. Assembly & ISA: x86-64 NASM/GAS (AVX2/AVX-512, SysV ABI) and ARM64 / RISC-V asm.
3. Accelerators & Differentiable Computing: JAX (vmap, pjit, grad, lax.scan), Triton, CUDA.
4. Systems Languages & Safe Runtimes: Rust (borrow checker, lifetime invariants, atomics), Go (goroutines, channels).
5. Web, Text & Scripting: HTML5 / DOM semantics, Perl 5/7 (regex automata, stream filters), Bash POSIX.
6. Genomics & Molecular Biology:
   - Watson-Crick double-strand DNA/RNA reverse complementation.
   - 6-Frame codon translation and Open Reading Frames (ORFs).
   - Eukaryotic splice junction boundaries (canonical donor GT, acceptor AG, branch sites).
   - Transcription factor binding site (TFBS) consensus motifs (TATA-box, E-box, Sp1, NF-kB).
7. Formal Proofs & Logic: Lean 4 interactive theorem proving tactics (omega, Nat.mul_add, induction).
8. Symbolic Mathematics: Multi-step arithmetic and algebra with explicit <thought> registers.
"""

from typing import Dict, List, Tuple
import random


class UniversalMultiDomainSynthesizer:
    def __init__(self, seed: int = 42):
        random.seed(seed)

    # 1. C & C++
    def sample_c(self) -> str:
        templates = [
            """// C17: Lock-free atomic ring buffer
#include <stdatomic.h>
#include <stddef.h>

struct RingBuf {
    atomic_size_t head;
    atomic_size_t tail;
    size_t capacity;
    int *data;
};

void ring_init(struct RingBuf *r, int *buf, size_t cap) {
    atomic_init(&r->head, 0);
    atomic_init(&r->tail, 0);
    r->capacity = cap;
    r->data = buf;
}
""",
            """// C17: Non-blocking POSIX socket multiplexer
#include <sys/epoll.h>
#include <fcntl.h>

int set_nonblocking(int fd) {
    int flags = fcntl(fd, F_GETFL, 0);
    if (flags == -1) return -1;
    return fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}
""",
        ]
        return random.choice(templates)

    def sample_cpp(self) -> str:
        templates = [
            """// C++20: Concepts and RAII resource manager
#include <concepts>
#include <span>
#include <vector>

template <typename T>
concept Numerical = std::integral<T> || std::floating_point<T>;

template <Numerical T>
T parallel_accumulate(std::span<const T> values) {
    T total = 0;
    for (const auto& elem : values) {
        total += elem;
    }
    return total;
}
""",
        ]
        return random.choice(templates)

    # 2. Zig
    def sample_zig(self) -> str:
        templates = [
            """// Zig 0.13: Safe memory allocator and slice operations
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
""",
        ]
        return random.choice(templates)

    # 3. Hardware & Firmware Register Interfaces
    def sample_hardware_firmware(self) -> str:
        templates = [
            """// Firmware: Memory-mapped I/O (MMIO) UART Driver
#include <stdint.h>

#define UART0_BASE   0x10000000
#define UART_RHR     (*(volatile uint8_t*)(UART0_BASE + 0x00))
#define UART_LSR     (*(volatile uint8_t*)(UART0_BASE + 0x05))
#define UART_LSR_THRE 0x20

void uart_putc(char c) {
    while ((UART_LSR & UART_LSR_THRE) == 0) {
        // Wait until transmitter holding register is empty
    }
    UART_RHR = (uint8_t)c;
}
""",
            """// Firmware: SPI Peripheral Control Register Setup
#define SPI_CR1_BASE 0x40013000
#define SPI_CR1      (*(volatile uint32_t*)(SPI_CR1_BASE))
#define SPI_ENABLE   (1 << 6)
#define SPI_MASTER   (1 << 2)

void spi_init_master(void) {
    SPI_CR1 |= (SPI_ENABLE | SPI_MASTER);
}
""",
        ]
        return random.choice(templates)

    # 4. Assembly (x86-64 / ARM64)
    def sample_assembly(self) -> str:
        templates = [
            """// x86-64 AT&T Assembly: Vectorized dot product (AVX2)
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
""",
            """// ARM64 AArch64 Assembly: Fast spinlock acquire
.globl spinlock_lock
spinlock_lock:
    mov w1, #1
.L_spin:
    ldaxr w2, [x0]
    cbnz w2, .L_spin
    stxr w3, w1, [x0]
    cbnz w3, .L_spin
    dmb ish
    ret
""",
        ]
        return random.choice(templates)

    # 5. JAX Differentiable Computing
    def sample_jax(self) -> str:
        templates = [
            """# JAX: Vectorized Lie group trajectory step using vmap and lax.scan
import jax
import jax.numpy as jnp
from jax import grad, jit, vmap

@jit
def cayley_step(h, A):
    # h: [D], A: [D, D] in so(D)
    d = A.shape[0]
    eye = jnp.eye(d)
    U = jnp.linalg.solve(eye + A, eye - A)
    return jnp.dot(U, h)

@jit
def batch_trajectory(states, generators):
    return vmap(cayley_step, in_axes=(0, 0))(states, generators)
""",
            """# JAX: Functional value-and-grad optimization step
import jax
import jax.numpy as jnp

def cross_entropy_loss(weights, x, y):
    logits = jnp.dot(x, weights)
    log_probs = logits - jax.nn.logsumexp(logits)
    return -jnp.mean(log_probs * y)

grad_fn = jax.jit(jax.value_and_grad(cross_entropy_loss))
""",
        ]
        return random.choice(templates)

    # 6. HTML5 & Semantic Web
    def sample_html(self) -> str:
        templates = [
            """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IMF Virtual Polytope Monitor</title>
</head>
<body>
    <main role="main">
        <section aria-label="Expert Telemetry">
            <h1>Polytope Mixture-of-Experts</h1>
            <meter id="disp-gauge" min="0" max="1" value="0.85">85%</meter>
        </section>
    </main>
</body>
</html>
""",
        ]
        return random.choice(templates)

    # 7. Perl 5/7
    def sample_perl(self) -> str:
        templates = [
            """#!/usr/bin/env perl
use strict;
use warnings;

sub parse_fasta_splice_sites {
    my ($file) = @_;
    open(my $fh, '<', $file) or die "Cannot open $file: $!";
    my $header = '';
    my $seq = '';
    while (my $line = <$fh>) {
        chomp $line;
        if ($line =~ /^>(.*)/) {
            $header = $1;
        } else {
            $seq .= uc($line);
        }
    }
    close $fh;
    # Regex find canonical donor GT splice junctions
    while ($seq =~ /(?=([ACGT]{3}GT[ACGT]{3}))/g) {
        print "Donor candidate at $-[0]: $1\\n";
    }
}
""",
        ]
        return random.choice(templates)

    # 8. Genomics & Molecular Biology
    def sample_genomics(self) -> str:
        bases = ["A", "C", "G", "T"]
        seq_len = random.randint(32, 48)
        raw_dna = "".join(random.choices(bases, k=seq_len))
        # Insert donor GT and acceptor AG motifs
        full_dna = f"{raw_dna[:12]}AGGTAAGT{raw_dna[12:28]}TTTCTAG{raw_dna[28:]}"
        # Reverse complement
        trans = str.maketrans("ACGT", "TGCA")
        rc_dna = full_dna.translate(trans)[::-1]

        return f"""; FASTA Eukaryotic Splice Domain Region
>chr19:588581-588640 forward_strand
{full_dna}
; Reverse Complement (Watson-Crick Equivariant):
>chr19:588581-588640 reverse_strand
{rc_dna}
// Motifs: Donor 5'-GT (AGGTAAGT), Acceptor 3'-AG (TTTCTAG)
"""

    # 9. Formal Logic & Lean 4
    def sample_lean4(self) -> str:
        templates = [
            """theorem add_comm_id (n m : Nat) : n + m = m + n := by
  omega

theorem mul_distrib_add (a b c : Nat) : a * (b + c) = a * b + a * c := by
  exact Nat.mul_add a b c

theorem le_transitive (a b c : Nat) (h1 : a ≤ b) (h2 : b ≤ c) : a ≤ c := by
  exact Nat.le_trans h1 h2
""",
            """theorem double_neg_elim (p : Prop) (h : ¬¬p) (em : p ∨ ¬p) : p := by
  cases em with
  | inl hp => exact hp
  | inr hnp => contradiction
""",
        ]
        return random.choice(templates)

    # 10. Python & Rust Systems
    def sample_python(self) -> str:
        templates = [
            """def binary_search(arr: list[int], target: int) -> int:
    low, high = 0, len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
""",
        ]
        return random.choice(templates)

    def sample_rust(self) -> str:
        templates = [
            """pub fn fibonacci(n: u32) -> u64 {
    let mut a: u64 = 0;
    let mut b: u64 = 1;
    for _ in 0..n {
        let temp = a + b;
        a = b;
        b = temp;
    }
    a
}
""",
            """pub struct Stack<T> {
    elements: Vec<T>,
}

impl<T> Stack<T> {
    pub fn new() -> Self {
        Stack { elements: Vec::new() }
    }
    pub fn push(&mut self, item: T) {
        self.elements.push(item);
    }
    pub fn pop(&mut self) -> Option<T> {
        self.elements.pop()
    }
}
""",
        ]
        return random.choice(templates)

    # 11. Symbolic Math CoT
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
        if dice < 0.10:
            return self.sample_c(), "systems_c"
        elif dice < 0.20:
            return self.sample_cpp(), "systems_cpp"
        elif dice < 0.30:
            return self.sample_zig(), "systems_zig"
        elif dice < 0.40:
            return self.sample_hardware_firmware(), "hardware_firmware"
        elif dice < 0.50:
            return self.sample_assembly(), "assembly_isa"
        elif dice < 0.60:
            return self.sample_jax(), "jax_accelerators"
        elif dice < 0.70:
            return self.sample_html(), "web_html"
        elif dice < 0.80:
            return self.sample_perl(), "scripting_perl"
        elif dice < 0.90:
            return self.sample_genomics(), "genomics_biology"
        elif dice < 0.95:
            return self.sample_lean4(), "formal_logic_lean4"
        else:
            return self.sample_math(), "symbolic_math"

    def generate_corpus(self, num_samples: int = 3000) -> List[Tuple[str, str]]:
        return [self.generate_sample() for _ in range(num_samples)]
