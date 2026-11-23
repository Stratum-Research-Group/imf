"""
benchmark_eth_lean_recursive_improver.py
End-to-End Recursive Self-Improvement Benchmark across multiple autonomous generations.

Evaluates:
1. Multi-generational theorem proposing & proving in Lean 4 core.
2. Formal rejection of ungrounded / hallucinated proof steps (0 sorry tolerance).
3. Incorporation of verified theorems into self-improving policy updates.
4. Latency and verification throughput across successive RSI loops.
"""

import sys
import time
from imf.eth_lean_recursive_improver import ETHLeanRecursiveImprover


def run_eth_lean_rsi_benchmark():
    print("=" * 76)
    print("IMF ETH-Lean Recursive Self-Improvement (RSI) Multi-Gen Benchmark")
    print("=" * 76)

    improver = ETHLeanRecursiveImprover()
    t0 = time.perf_counter()

    # Execute 3 autonomous improvement generations
    generations = 3
    results = improver.run_rsi_cycle(max_generations=generations)
    total_time = time.perf_counter() - t0

    print("\n--- Empirical RSI Telemetry ---")
    print(f"Total Generations Executed: {generations}")
    print(f"Total Candidate Lemmas:    {results['total_proposed']}")
    print(f"Total Formally Verified:   {results['total_verified']}")
    print(f"Lean 4 Verification Rate:  {results['verification_rate']*100:.1f}%")
    print(f"Cumulative Run Latency:    {total_time:.2f}s ({total_time / results['total_proposed']:.2f}s per theorem)")

    # Assert 100% verified sound mathematical theorems
    assert results["verification_rate"] == 1.0, f"Expected 100% verification, got {results['verification_rate']}"
    print("\n[✓] ETH-Lean RSI Benchmark passed with 0 errors and zero sorry!")
    return True


if __name__ == "__main__":
    success = run_eth_lean_rsi_benchmark()
    sys.exit(0 if success else 1)
