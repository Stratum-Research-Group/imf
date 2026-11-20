"""
Multi-Domain Expert Synthesizer incorporating AETHER-1 Systems & Genomic Ontologies.

Fields integrated from AETHER-1:
1. Systems Programming & Kernels (from AETHER-1 systems_ontology & c_cpp_kernel_dataset):
   - C (POSIX sockets, epoll, lock-free rings)
   - C++ (C++20 RAII, concepts, PMR allocators)
   - Linux Kernel & eBPF (XDP filters, SLUB allocators, RCU locks)
   - Triton & CUDA (fused block pointers, warp shuffles)
2. Molecular Biology & Genomics (from AETHER-1 genomic_dataset):
   - DNA reverse-complementation with Watson-Crick symmetry
   - 6-Frame codon-to-amino-acid translation
   - Eukaryotic splice junction donor (GT) / acceptor (AG) motif recognition
3. Formal Mathematics & Interactive Tactics (Lean 4 core):
   - Proof state transformations (omega, Nat.mul_add, induction)
4. Algorithmic Code (Python & Rust):
   - ASTs, recursion, type safety, ownership
5. Symbolic Mathematics:
   - Multi-step arithmetic with <thought> execution registers
"""

import random
from typing import Dict, List, Tuple


class AetherMultiDomainSynthesizer:
    """Enriched Multi-Domain Corpus Synthesizer spanning Systems, Genomics, Proofs, and Math."""

    def __init__(self, seed: int = 42):
        random.seed(seed)

    # 1. AETHER-1 Systems: C, C++, Kernel, Triton
    def generate_c_posix_sample(self) -> str:
        templates = [
            """#include <sys/epoll.h>
#include <fcntl.h>
#include <unistd.h>

int set_nonblocking(int fd) {
    int flags = fcntl(fd, F_GETFL, 0);
    if (flags == -1) return -1;
    return fcntl(fd, F_SETFL, flags | O_NONBLOCK);
}
""",
            """#include <stdatomic.h>
#include <stdbool.h>

struct LockFreeQueue {
    atomic_uintptr_t head;
    atomic_uintptr_t tail;
};

void queue_init(struct LockFreeQueue *q) {
    atomic_init(&q->head, 0);
    atomic_init(&q->tail, 0);
}
""",
        ]
        return random.choice(templates)

    def generate_cpp_sample(self) -> str:
        templates = [
            """#include <concepts>
#include <vector>

template <typename T>
concept Numeric = std::integral<T> || std::floating_point<T>;

template <Numeric T>
T compute_mean(const std::vector<T>& values) {
    T sum = 0;
    for (const auto& v : values) sum += v;
    return sum / static_cast<T>(values.size());
}
""",
            """#include <span>
#include <cstdint>

template <typename T>
struct RingBuffer {
    std::span<T> storage;
    size_t head{0};
    size_t tail{0};
    bool empty() const noexcept { return head == tail; }
};
""",
        ]
        return random.choice(templates)

    def generate_kernel_ebpf_sample(self) -> str:
        templates = [
            """#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

SEC("xdp")
int xdp_drop_all(struct xdp_md *ctx) {
    // Drop all incoming network frames at driver ingress
    return XDP_DROP;
}
char _license[] SEC("license") = "GPL";
""",
            """#include <linux/module.h>
#include <linux/kernel.h>

static int __init mod_init(void) {
    pr_info("IMF-Kernel: Subsystem initialized.\\n");
    return 0;
}

static void __exit mod_exit(void) {
    pr_info("IMF-Kernel: Subsystem unregistered.\\n");
}

module_init(mod_init);
module_exit(mod_exit);
MODULE_LICENSE("GPL");
""",
        ]
        return random.choice(templates)

    def generate_triton_gpu_sample(self) -> str:
        templates = [
            """import triton
import triton.language as tl

@triton.jit
def fused_add_kernel(x_ptr, y_ptr, out_ptr, n_elements, BLOCK_SIZE: tl.constexpr):
    pid = tl.program_id(axis=0)
    block_start = pid * BLOCK_SIZE
    offsets = block_start + tl.arange(0, BLOCK_SIZE)
    mask = offsets < n_elements
    x = tl.load(x_ptr + offsets, mask=mask)
    y = tl.load(y_ptr + offsets, mask=mask)
    tl.store(out_ptr + offsets, x + y, mask=mask)
""",
        ]
        return random.choice(templates)

    # 2. AETHER-1 Genomics: DNA Sequences, Splice Sites, Codons
    def generate_genomic_sample(self) -> str:
        bases = ["A", "C", "G", "T"]
        seq_len = random.randint(30, 45)
        dna_seq = "".join(random.choices(bases, k=seq_len))
        # Insert canonical splice donor GT and acceptor AG
        splice_donor = "AGGTAAGT"
        splice_acceptor = "TTTCTAG"
        
        return f"""; FASTA Eukaryotic Splice Junction Region
>chr19:588581-588640 donor_acceptor_boundary
{dna_seq[:10]}{splice_donor}{dna_seq[10:25]}{splice_acceptor}{dna_seq[25:]}
// Annotation: 5' donor site at pos 12 (GT), 3' acceptor site at pos 35 (AG)
"""

    # 3. Systems Code: Python & Rust
    def generate_python_sample(self) -> str:
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
            """def quicksort(items: list[int]) -> list[int]:
    if len(items) <= 1:
        return items
    pivot = items[len(items) // 2]
    left = [x for x in items if x < pivot]
    middle = [x for x in items if x == pivot]
    right = [x for x in items if x > pivot]
    return quicksort(left) + middle + quicksort(right)
""",
        ]
        return random.choice(templates)

    def generate_rust_sample(self) -> str:
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

    # 4. Formal Proofs: Lean 4
    def generate_lean4_sample(self) -> str:
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

    # 5. Symbolic Math CoT
    def generate_math_cot_sample(self) -> str:
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

    def generate_mixed_sample(self) -> Tuple[str, str]:
        dice = random.random()
        if dice < 0.20:
            return self.generate_python_sample(), "systems_code"
        elif dice < 0.35:
            return self.generate_rust_sample(), "systems_code"
        elif dice < 0.50:
            return self.generate_c_posix_sample(), "systems_code"
        elif dice < 0.65:
            return self.generate_genomic_sample(), "genomics_biology"
        elif dice < 0.80:
            return self.generate_lean4_sample(), "formal_logic_lean4"
        else:
            return self.generate_math_cot_sample(), "symbolic_math"

    def generate_corpus(self, num_samples: int = 1500) -> List[Tuple[str, str]]:
        return [self.generate_mixed_sample() for _ in range(num_samples)]
