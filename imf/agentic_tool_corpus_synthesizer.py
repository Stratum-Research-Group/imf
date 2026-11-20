"""
Agentic Multi-Turn Tool Call & FineWeb-Edu Python AST Corpus Synthesizer.
Generates structured corpora targeting:
1. FineWeb-Edu style pedagogical explanations & textbook-grade mathematical proofs.
2. Python Algorithmic Code with concrete AST grammar rules, recursion, dynamic programming, and type hints.
3. Multi-Turn Agentic Tool Calls (JSON tool use, function execution loops, observation reflections).
"""

import json
import random
from typing import List, Tuple, Dict, Any

class AgenticToolAndEduSynthesizer:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def generate_fineweb_edu_sample(self) -> str:
        topics = [
            ("Singular Value Decomposition and Low-Rank Approximations",
             "Let $A \\in \\mathbb{R}^{m \\times n}$ be an arbitrary real matrix of rank $r$. "
             "The Singular Value Decomposition (SVD) guarantees the factorization $A = U \\Sigma V^T$, "
             "where $U \\in O(m)$ and $V \\in O(n)$ are orthogonal matrices containing left- and right-singular vectors, "
             "and $\\Sigma = \\mathrm{diag}(\\sigma_1, \\dots, \\sigma_r, 0, \\dots, 0)$ contains ordered singular values "
             "$\\sigma_1 \\ge \\sigma_2 \\ge \\dots \\ge \\sigma_r > 0$. By the Eckart-Young-Mirsky Theorem, the best rank-$k$ "
             "approximation under both the spectral norm $\\|\\cdot\\|_2$ and Frobenius norm $\\|\\cdot\\|_F$ is given by "
             "$A_k = \\sum_{i=1}^k \\sigma_i u_i v_i^T$. This establishes the optimal compression bound for spectral projectors."),
            
            ("Markov Decision Processes and Bellman Optimality",
             "A discrete-time Markov Decision Process (MDP) is formalized by the 5-tuple $(\\mathcal{S}, \\mathcal{A}, \\mathcal{P}, \\mathcal{R}, \\gamma)$. "
             "The state-value function $V^\\pi(s)$ satisfies the Bellman expectation equation: "
             "$V^\\pi(s) = \\sum_{a \\in \\mathcal{A}} \\pi(a|s) \\left[ \\mathcal{R}(s, a) + \\gamma \\sum_{s' \\in \\mathcal{S}} \\mathcal{P}(s'|s, a) V^\\pi(s') \\right]$. "
             "Defining the Bellman optimality operator $T^* V(s) = \\max_{a} \\left[ \\mathcal{R}(s, a) + \\gamma \\mathbb{E}[V(s')] \\right]$, "
             "we prove that $T^*$ is a $\\gamma$-contraction mapping under the infinity norm: $\\|T^* V - T^* U\\|_\\infty \\le \\gamma \\|V - U\\|_\\infty$. "
             "By Banach's Fixed-Point Theorem, value iteration converges unconditionally to the unique optimal value function $V^*$.")
        ]
        topic, body = self.rng.choice(topics)
        return f"# Educational Chapter: {topic}\n\n## Formal Exposition\n{body}\n"

    def generate_algorithmic_ast_python_sample(self) -> str:
        algorithms = [
            ("def dijkstra(graph: dict[int, list[tuple[int, int]]], start: int) -> dict[int, int]:\n"
             "    import heapq\n"
             "    distances = {node: float('inf') for node in graph}\n"
             "    distances[start] = 0\n"
             "    pq = [(0, start)]\n"
             "    while pq:\n"
             "        curr_d, curr_u = heapq.heappop(pq)\n"
             "        if curr_d > distances[curr_u]:\n"
             "            continue\n"
             "        for v, weight in graph[curr_u]:\n"
             "            dist = curr_d + weight\n"
             "            if dist < distances[v]:\n"
             "                distances[v] = dist\n"
             "                heapq.heappush(pq, (dist, v))\n"
             "    return distances"),
            
            ("def lowest_common_ancestor(root: 'TreeNode', p: 'TreeNode', q: 'TreeNode') -> 'TreeNode':\n"
             "    if not root or root == p or root == q:\n"
             "        return root\n"
             "    left = lowest_common_ancestor(root.left, p, q)\n"
             "    right = lowest_common_ancestor(root.right, p, q)\n"
             "    if left and right:\n"
             "        return root\n"
             "    return left if left else right")
        ]
        code = self.rng.choice(algorithms)
        return f"```python\n# Algorithmic Implementation with Strict Static Typing\n{code}\n```"

    def generate_agentic_tool_call_sample(self) -> str:
        user_queries = [
            ("Check system memory and kill dangling zombie workers on port 8080.",
             "inspect_process", {"port": 8080},
             {"status": "found", "pids": [40912], "cmd": "python worker.py --port 8080", "mem_rss_mb": 1420},
             "kill_process", {"pid": 40912, "signal": 9},
             {"status": "killed", "pid": 40912, "exit_code": 0},
             "Port 8080 process (PID 40912, consuming 1420MB RSS) has been terminated via SIGKILL."),
            
            ("Verify Lean 4 proof for commutativity of integer multiplication.",
             "lean4_verify", {"file": "Math/Ring.lean", "theorem": "int_mul_comm"},
             {"status": "success", "errors": 0, "goals_remaining": 0},
             "lake_build", {"target": "Math"},
             {"build_result": "success", "jobs": 4},
             "Theorem `int_mul_comm` verified successfully with zero remaining goals.")
        ]
        q, t1, a1, r1, t2, a2, r2, final_resp = self.rng.choice(user_queries)
        
        dialogue = (
            f"<turn:user>\n{q}\n</turn:user>\n"
            f"<turn:assistant>\n"
            f"<thought>Analyzing request. Calling tool `{t1}` with parameters {json.dumps(a1)}.</thought>\n"
            f"<tool_call>\n{{\"name\": \"{t1}\", \"arguments\": {json.dumps(a1)}}}\n</tool_call>\n"
            f"</turn:assistant>\n"
            f"<turn:tool_response>\n{json.dumps(r1)}\n</turn:tool_response>\n"
            f"<turn:assistant>\n"
            f"<thought>Observation received: {json.dumps(r1)}. Executing follow-up action `{t2}`.</thought>\n"
            f"<tool_call>\n{{\"name\": \"{t2}\", \"arguments\": {json.dumps(a2)}}}\n</tool_call>\n"
            f"</turn:assistant>\n"
            f"<turn:tool_response>\n{json.dumps(r2)}\n</turn:tool_response>\n"
            f"<turn:assistant>\n{final_resp}\n</turn:assistant>"
        )
        return dialogue

    def generate_corpus(self, num_samples: int = 100) -> List[Tuple[str, str]]:
        corpus = []
        generators = [
            (self.generate_fineweb_edu_sample, "fineweb_edu_pedagogy"),
            (self.generate_algorithmic_ast_python_sample, "python_algorithmic_ast"),
            (self.generate_agentic_tool_call_sample, "multi_turn_agentic_tool_calls")
        ]
        for _ in range(num_samples):
            gen_fn, tag = self.rng.choice(generators)
            corpus.append((gen_fn(), tag))
        return corpus

if __name__ == "__main__":
    synthesizer = AgenticToolAndEduSynthesizer()
    corpus = synthesizer.generate_corpus(6)
    for text, tag in corpus:
        print(f"=== TAG: {tag} ===")
        print(text[:250] + "...\n")
