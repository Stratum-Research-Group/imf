"""
Benchmark Master Synthesizer: 96 Universal Specialized Expert Manifolds.
Expands the 64-domain ontology to 96 by integrating:
1. FineWeb-Edu Pedagogical Textbook chapters (STEM proofs, derivations, derivations).
2. Python Algorithmic AST (LeetCode hard, strict static typing, dynamic programming, tree traversals).
3. Multi-Turn Agentic Tool Calls (JSON tool use, function execution loops, error recovery).
4. GSM8K / SVAMP Multi-Step Chain-of-Thought Arithmetic.
5. SWE-bench Git Diffs, Patch Generation, and System Triage.
6. ARC-AGI Discrete Geometric Inductive Reasoning & Grid Transformations.
7. HumanEval / MultiPL-E Polyglot Implementations.
8. MMLU-Pro / Big-Bench Hard Complex Premise Disambiguation.
"""

from typing import Dict, List, Tuple
import random
import json

from imf.omni_64_multidomain_synthesizer import OMNI_64_EXPERT_DOMAINS, Omni64DomainSynthesizer
from imf.agentic_tool_corpus_synthesizer import AgenticToolAndEduSynthesizer

# 32 Additional Benchmark-Focused Expert Domains (64 + 32 = 96 Universal Domains)
BENCHMARK_32_ADDITIONAL_DOMAINS: List[str] = [
    # Family A: FineWeb-Edu Pedagogical Foundations (64-67)
    "fineweb_edu_stem_pedagogy",        # High-school & collegiate STEM pedagogy, concept breakdown
    "fineweb_edu_formal_proofs",        # Step-by-step rigorous derivations, lemmas, and corollaries
    "fineweb_edu_historical_philosophy", # Epistemology, historical dialectic reasoning, scientific method
    "fineweb_edu_linguistics_grammar",  # Transformational grammar, Chomsky hierarchy, semantic parsing

    # Family B: Python Algorithmic AST & Advanced Data Structures (68-71)
    "python_algorithmic_dp",            # Dynamic programming, memoization, DAG state spaces
    "python_algorithmic_graph_trees",   # Min-cut/max-flow, LCA, tree decomposition, topological order
    "python_ast_static_typing",         # Python 3.12+ Generics, Protocols, TypeVar, AST visitors
    "python_concurrency_asyncio",       # Coroutines, event loop scheduling, task cancelation semantics

    # Family C: Agentic Multi-Turn Tool Use & Function Calling (72-75)
    "agentic_tool_json_dispatch",       # Strict JSON schema formatting, function name selection
    "agentic_tool_execution_loop",      # State machines, observation absorption, error retry strategy
    "agentic_bash_terminal_triage",     # CLI debugging, ps/grep/kill, stdout/stderr triage
    "agentic_repo_codebase_search",     # AST ripgrep, symbol cross-referencing, multi-file inspection

    # Family D: GSM8K & Multi-Step Quantitative Reasoning (76-79)
    "gsm8k_arithmetic_cot",             # Word problem multi-step arithmetic, units conversion
    "olympiad_combinatorics",           # Generating functions, inclusion-exclusion, Ramsey theory
    "applied_linear_algebra_svd",       # PCA, low-rank factorization, condition numbers, QR/Cholesky
    "probability_markov_martingales",   # Stopping times, optional stopping theorem, Doob's inequality

    # Family E: SWE-bench Software Engineering & Patching (80-83)
    "swe_bench_git_diff_patch",         # Unified diff parsing, hunk application, conflict resolution
    "swe_bench_test_regression_audit",  # Pytest/cargo test fixture diagnosis, mock isolation
    "swe_bench_api_backward_compat",    # Deprecation warnings, semver enforcement, breaking changes
    "swe_bench_sanitizer_stack_trace",  # ASan/UBSan backtrace demangling, memory leak pinpointing

    # Family F: ARC-AGI Inductive Geometry & Spatial Invariance (84-87)
    "arc_agi_grid_transformations",     # 2D discrete grid rotation, reflection, scaling, gravity
    "arc_agi_color_topology_masks",     # Connected component labeling, flood fill, topological enclosure
    "arc_agi_pattern_continuation",     # Periodicity detection, symmetry group identification
    "arc_agi_symbolic_prior_rules",     # Object permanence, spatial containment, contact dynamics

    # Family G: Polyglot MultiPL-E & Verified Compilation (88-91)
    "multiple_polyglot_go_goroutines",  # Go concurrency, channels, select blocks, mutex locks
    "multiple_polyglot_typescript",     # TypeScript conditional types, mapped types, discriminated unions
    "multiple_polyglot_ocaml_fp",       # Algebraic data types, pattern matching, monadic bind
    "multiple_polyglot_sql_analytics",  # Window functions, CTEs, recursive queries, partition indexing

    # Family H: MMLU-Pro & High-Precision Deductive Logic (92-95)
    "mmlu_pro_medical_clinical_reasoning", # Clinical pathology, differential diagnosis, pharmacology
    "mmlu_pro_legal_jurisprudence",        # Statutory interpretation, constitutional law, precedent analysis
    "mmlu_pro_macro_micro_economics",     # IS-LM curves, DSGE models, game-theoretic market mechanisms
    "mmlu_pro_cognitive_epistemology",     # Multi-agent epistemic logic, modal Kripke semantics
]

BENCHMARK_96_MASTER_DOMAINS: List[str] = OMNI_64_EXPERT_DOMAINS + BENCHMARK_32_ADDITIONAL_DOMAINS


class BenchmarkMasterSynthesizer:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.omni64_syn = Omni64DomainSynthesizer(seed=seed)
        self.agent_edu_syn = AgenticToolAndEduSynthesizer(seed=seed)

    def generate_gsm8k_sample(self) -> str:
        templates = [
            ("Janet sells artisan sourdough loaves for $8 each and baguettes for $5 each. "
             "On Saturday, she bakes 45 loaves of sourdough and 30 baguettes. She sells 80% of the sourdough "
             "and 90% of the baguettes. How much revenue did she generate?",
             "1. Calculate sourdough loaves sold: 45 * 0.80 = 36 loaves.\n"
             "2. Sourdough revenue: 36 * $8 = $288.\n"
             "3. Calculate baguettes sold: 30 * 0.90 = 27 baguettes.\n"
             "4. Baguette revenue: 27 * $5 = $135.\n"
             "5. Total revenue: $288 + $135 = $423.\n#### 423"),
            
            ("A server cluster has 64 nodes. Each node processes 125 requests per second. "
             "If 16 nodes are taken offline for maintenance and the remaining nodes experience a 20% throughput increase, "
             "what is the total requests per second the cluster can handle?",
             "1. Initial operating nodes: 64 - 16 = 48 nodes.\n"
             "2. Boosted throughput per node: 125 * 1.20 = 150 requests/sec.\n"
             "3. Total cluster capacity: 48 * 150 = 7,200 requests/sec.\n#### 7200")
        ]
        q, ans = self.rng.choice(templates)
        return f"Question: {q}\n\nReasoning:\n{ans}"

    def generate_swe_bench_sample(self) -> str:
        diffs = [
            ("diff --git a/imf/polytope_moe.py b/imf/polytope_moe.py\n"
             "--- a/imf/polytope_moe.py\n"
             "+++ b/imf/polytope_moe.py\n"
             "@@ -112,6 +112,8 @@ class PolytopeMixtureOfExperts(nn.Module):\n"
             "-        routing_probs = torch.softmax(proj_logits, dim=-1)\n"
             "+        # Numerical stability guard against fp16 overflow\n"
             "+        proj_logits = proj_logits - proj_logits.max(dim=-1, keepdim=True).values\n"
             "+        routing_probs = torch.softmax(proj_logits, dim=-1)\n"),
            
            ("diff --git a/kernel/sched/core.c b/kernel/sched/core.c\n"
             "--- a/kernel/sched/core.c\n"
             "+++ b/kernel/sched/core.c\n"
             "@@ -452,7 +452,7 @@ void pick_next_task(struct rq *rq)\n"
             "-    if (unlikely(!rq->nr_running))\n"
             "+    if (unlikely(rq->nr_running == 0))\n"
             "         return idle_sched_class.pick_next_task(rq);\n")
        ]
        return f"# SWE-bench Verified Fix Hunk\n```diff\n{self.rng.choice(diffs)}```\n"

    def generate_arc_agi_sample(self) -> str:
        puzzles = [
            ("Input Grid (3x3):\n[[0, 1, 0],\n [1, 1, 1],\n [0, 1, 0]]\n"
             "Transformation Rule: Rotate 90 degrees clockwise and invert active values (1 -> 2).\n"
             "Output Grid (3x3):\n[[0, 2, 0],\n [2, 2, 2],\n [0, 2, 0]]"),
            
            ("Input Grid (4x4):\n[[5, 0, 0, 5],\n [0, 0, 0, 0],\n [0, 0, 0, 0],\n [5, 0, 0, 5]]\n"
             "Transformation Rule: Connect boundary corner anchor points with a diagonal cross of color 3.\n"
             "Output Grid (4x4):\n[[5, 0, 0, 5],\n [0, 3, 3, 0],\n [0, 3, 3, 0],\n [5, 0, 0, 5]]")
        ]
        return f"# ARC-AGI Inductive Spatial Task\n{self.rng.choice(puzzles)}"

    def generate_corpus(self, num_samples: int = 1000) -> List[Tuple[str, str]]:
        corpus = []
        for _ in range(num_samples):
            mode = self.rng.random()
            if mode < 0.50:
                # 50% from 64-domain omni synthesizer (Quantum, Chaos, Systems, Lean4, etc.)
                sample = self.omni64_syn.generate_corpus(1)[0]
                corpus.append(sample)
            elif mode < 0.70:
                # 20% FineWeb-Edu, Python Algorithmic AST & Agentic Tools
                sample = self.agent_edu_syn.generate_corpus(1)[0]
                corpus.append(sample)
            elif mode < 0.80:
                # 10% GSM8K / Multi-Step CoT
                corpus.append((self.generate_gsm8k_sample(), "gsm8k_arithmetic_cot"))
            elif mode < 0.90:
                # 10% SWE-bench Unified Patching
                corpus.append((self.generate_swe_bench_sample(), "swe_bench_git_diff_patch"))
            else:
                # 10% ARC-AGI Inductive Spatial Reasoning
                corpus.append((self.generate_arc_agi_sample(), "arc_agi_grid_transformations"))
        return corpus


if __name__ == "__main__":
    syn = BenchmarkMasterSynthesizer()
    c = syn.generate_corpus(5)
    print(f"[*] Generated {len(c)} master multi-domain samples. Total master domains: {len(BENCHMARK_96_MASTER_DOMAINS)}")
    for txt, tag in c:
        print(f"[{tag}] -> {txt[:100]}...\n")
