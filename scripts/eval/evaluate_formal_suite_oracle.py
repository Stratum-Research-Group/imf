"""
evaluate_formal_suite_oracle.py
Autonomous Benchmark for the Expanded 18-Theorem Formal Lean 4 Suite.
Uses pure Lean 4 core (#print axioms) with strict zero-axiom / core-axiom reflection gating.
Runs entirely on CPU via Lean 4 compiler binary without GPU interference.
"""

import time
from imf.formal_theorem_suite import FORMAL_LEAN4_THEOREM_SUITE
from imf.eth_lean_recursive_improver import ETHLeanRecursiveImprover

def run_suite_evaluation():
    print("=" * 80)
    print("  IMF Formal Lean 4 Verification Suite: Multi-Domain Ground-Truth Oracle")
    print("=" * 80)
    print(f"Total Theorems in Benchmark: {len(FORMAL_LEAN4_THEOREM_SUITE)}")
    
    oracle = ETHLeanRecursiveImprover(lean_bin="lean")
    
    results = []
    t_start = time.perf_counter()
    
    for idx, item in enumerate(FORMAL_LEAN4_THEOREM_SUITE, start=1):
        name = item["name"]
        header = item["header"]
        candidates = item["candidates"]
        domain = item["domain"]
        
        t0 = time.perf_counter()
        passed = False
        winning_cand = None
        attempt = 0
        winning_msg = ""
        
        for cand in candidates:
            attempt += 1
            code = f"{header}\n{cand}\n\n#print axioms {name}\n"
            ok, msg = oracle.verify_lean_snippet(code)
            if ok:
                passed = True
                winning_cand = cand.strip()
                winning_msg = msg.strip()
                break
                
        latency = time.perf_counter() - t0
        results.append({
            "index": idx,
            "domain": domain,
            "name": name,
            "passed": passed,
            "attempts": attempt,
            "latency": latency,
            "tactic": winning_cand,
            "compiler_msg": winning_msg
        })
        status_icon = "✓" if passed else "✗"
        print(f"[{status_icon}] ({idx:2d}/{len(FORMAL_LEAN4_THEOREM_SUITE)}) [{domain:<32}] {name:<32} -> {winning_cand or 'FAILED'} ({latency:.3f}s)")

    total_time = time.perf_counter() - t_start
    n_passed = sum(1 for r in results if r["passed"])
    
    print("\n" + "=" * 80)
    print("SUMMARY BY DOMAIN")
    print("=" * 80)
    domains = {}
    for r in results:
        d = r["domain"]
        if d not in domains:
            domains[d] = {"total": 0, "passed": 0}
        domains[d]["total"] += 1
        if r["passed"]:
            domains[d]["passed"] += 1
            
    for d, stats in domains.items():
        rate = stats["passed"] / stats["total"] * 100
        print(f"• {d:<38} : {stats['passed']}/{stats['total']} ({rate:.1f}%)")
        
    print("-" * 80)
    print(f"Final Score: {n_passed}/{len(results)} ({n_passed/len(results)*100:.1f}%) Verified Under Pure Lean 4 Core!")
    print(f"Total Execution Time: {total_time:.2f}s | Average Latency: {total_time/len(results):.3f}s/theorem")
    print("=" * 80)

if __name__ == "__main__":
    run_suite_evaluation()
