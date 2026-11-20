"""
Multi-Domain Synthesizer for IMF Reasoning & Code Pretraining.

Generates interleaved synthetic training streams across 4 core domains:
1. Systems Code & Algorithms (Python, Rust, C):
   - AST representations, control-flow graphs, sorting/search, recursion.
2. Formal Logic & Lean 4 Tactics:
   - Propositional theorems, tactic proofs (intro, exact, rw, omega, ring).
3. Symbolic Reasoning & Math (GSM8k CoT):
   - Multi-step arithmetic with explicit <thought> traces and state registers.
4. Natural Language Discourse:
   - Linguistic explanations, narrative logic, and multi-turn instruction prompts.
"""

import random
from typing import Dict, List, Tuple


class MultiDomainCorpusSynthesizer:
    def __init__(self, seed: int = 42):
        random.seed(seed)

    def generate_python_sample(self) -> str:
        templates = [
            """def binary_search(arr: list[int], target: int) -> int:
    # State tracking: low and high pointers
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
            """def depth_first_search(graph: dict[str, list[str]], start: str) -> list[str]:
    visited, stack = set(), [start]
    traversal = []
    while stack:
        node = stack.pop()
        if node not in visited:
            visited.add(node)
            traversal.append(node)
            for neighbor in reversed(graph.get(node, [])):
                if neighbor not in visited:
                    stack.append(neighbor)
    return traversal
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
            """theorem list_length_append {α : Type} (xs ys : List α) :
    (xs ++ ys).length = xs.length + ys.length := by
  induction xs with
  | nil => rfl
  | cons x rest ih =>
    simp [ih]
    omega
""",
        ]
        return random.choice(templates)

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
        """Returns (text, domain_tag)"""
        dice = random.random()
        if dice < 0.35:
            return self.generate_python_sample(), "systems_code"
        elif dice < 0.55:
            return self.generate_rust_sample(), "systems_code"
        elif dice < 0.75:
            return self.generate_lean4_sample(), "formal_logic_lean4"
        else:
            return self.generate_math_cot_sample(), "symbolic_math"

    def generate_corpus(self, num_samples: int = 1000) -> List[Tuple[str, str]]:
        return [self.generate_mixed_sample() for _ in range(num_samples)]
