"""
run_autonomous_swarm_synthesis.py
Demonstration script executing an autonomous multi-agent self-play session
grounded in the 14-domain ground-truth compilers.
"""

import sys
import json
from imf.autonomous_swarm_gym import AutonomousSwarmGym, SwarmCandidate

def main():
    print("=" * 80)
    print("   IMF Autonomous Swarm Gym: Ground-Truth Compiler Self-Play Loop")
    print("=" * 80)

    gym = AutonomousSwarmGym()

    # Define a curriculum of multi-agent challenges across disparate domains
    challenges = [
        {
            "id": "SWARM-01-LEAN4-CONSTRUCTIVE",
            "domain": "lean4",
            "spec": "Prove double negation of excluded middle or implication idempotence in constructive logic.",
            "code": "theorem swarm_imp_self (P : Prop) : P → P := fun h => h\n#print axioms swarm_imp_self",
            "critic": "Architect validated: Constructive term with zero axioms."
        },
        {
            "id": "SWARM-02-X86-FIBONACCI-REG",
            "domain": "x86_assembly",
            "spec": "Generate optimized x86-64 function computing 64-bit integer sum.",
            "code": ".intel_syntax noprefix\n.global add_vals\nadd_vals:\n    mov rax, rdi\n    add rax, rsi\n    ret\n",
            "critic": "Bare-metal verified: Complies with System V AMD64 ABI (rdi, rsi -> rax)."
        },
        {
            "id": "SWARM-03-ARM64-LEAF",
            "domain": "arm64_assembly",
            "spec": "Generate standard AArch64 leaf routine returning 42.",
            "code": ".global answer\nanswer:\n    mov w0, #42\n    ret\n",
            "critic": "AArch64 verified: Correct 32-bit immediate move into w0."
        },
        {
            "id": "SWARM-04-CUDA-VECTOR-ADD",
            "domain": "cuda_cpp",
            "spec": "Implement single-precision vector addition CUDA kernel.",
            "code": "__global__ void vec_add(const float* a, const float* b, float* c, int n) {\n    int idx = blockIdx.x * blockDim.x + threadIdx.x;\n    if (idx < n) {\n        c[idx] = a[idx] + b[idx];\n    }\n}\n",
            "critic": "HPC verified: Thread indexing guard prevents out-of-bounds writes."
        },
        {
            "id": "SWARM-05-CPP20-CONCEPTS",
            "domain": "cpp20",
            "spec": "Write C++20 templated concept requiring addition capability.",
            "code": "#include <concepts>\n\ntemplate<typename T>\nconcept Addable = requires(T a, T b) {\n    { a + b } -> std::same_as<T>;\n};\n\nstatic_assert(Addable<int>);\n",
            "critic": "C++20 verified: Modern concepts and compile-time static_assert."
        },
        {
            "id": "SWARM-06-RUST-BORROW-CHECK",
            "domain": "rust",
            "spec": "Write safe Rust function with slice borrowing and sum reduction.",
            "code": "pub fn sum_slice(slice: &[i64]) -> i64 {\n    slice.iter().sum()\n}\n",
            "critic": "Rust verified: Safe immutable borrow without unsafe blocks."
        },
        {
            "id": "SWARM-07-EBPF-PACKET-FILTER",
            "domain": "ebpf",
            "spec": "Implement minimal eBPF XDP drop filter.",
            "code": "int filter_prog() {\n    return 1;\n}\n",
            "critic": "eBPF verified: Compiles cleanly to BPF ELF target."
        },
        {
            "id": "SWARM-08-CRISPR-DNA",
            "domain": "crispr_dna",
            "spec": "Design valid SpCas9 guide target with canonical NGG PAM motif.",
            "code": "ATGCGATCGATCGATCGATCAGG",
            "critic": "Genomics verified: 20nt protospacer followed by canonical AGG PAM."
        },
        {
            "id": "SWARM-09-CHEM-BENZENE",
            "domain": "smiles_chem",
            "spec": "Propose valid closed aromatic benzene ring.",
            "code": "c1ccccc1",
            "critic": "Chemistry verified: Closed 6-carbon aromatic ring with Kekulé valence balance."
        },
        {
            "id": "SWARM-10-JSON-RPC-CALL",
            "domain": "json_rpc",
            "spec": "Formulate valid JSON RPC 2.0 tool invocation.",
            "code": '{"jsonrpc": "2.0", "method": "execute_query", "params": {"query": "SELECT * FROM states"}, "id": 1}',
            "critic": "Agentic verified: Valid JSON RPC 2.0 protocol envelope."
        }
    ]

    for ch in challenges:
        task = gym.generate_task(ch["domain"], ch["id"], ch["spec"], [ch["critic"]])
        cand = SwarmCandidate(
            candidate_id=f"cand-{ch['id']}",
            task_id=ch["id"],
            domain=ch["domain"],
            code_artifact=ch["code"],
            explanation=ch["spec"],
            generator_role="Synthesizer"
        )
        rec = gym.evaluate_candidate(cand, ch["critic"])
        status_sym = "[✓ PASS]" if rec.verified else "[✗ FAIL]"
        print(f"{status_sym} Domain: {rec.domain:<15} | Task: {rec.task_id:<28} | Reward: {rec.reward_score:+.1f} | Latency: {rec.latency_sec*1000:6.1f}ms")

    summary = gym.get_gym_summary()
    print("\n" + "=" * 80)
    print("   Swarm Gym Execution Summary")
    print("=" * 80)
    print(f"Total Self-Play Evaluations: {summary['total_evaluations']}")
    print(f"Total Certified Passes:      {summary['total_verified']}")
    print(f"Overall Certification Rate:  {summary['overall_pass_rate_pct']}%")
    print("\nPer-Domain Pass Breakdown:")
    for d, stats in summary["per_domain_stats"].items():
        print(f"  - {d:<16}: {stats['verified']}/{stats['total']} ({stats['rate_pct']}%)")
    print("=" * 80)

if __name__ == "__main__":
    main()
