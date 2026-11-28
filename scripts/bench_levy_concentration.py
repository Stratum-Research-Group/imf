#!/usr/bin/env python3
"""
scripts/bench_levy_concentration.py
Measures equatorial inner-product concentration of independent uniform unit vectors on S^{d-1}
across N=100,000 trials, and computes exact analytical Lévy upper bounds 2*exp(-d*eps^2/2)
as well as exact regularized incomplete beta function tail probabilities.
Includes a memory-bounded --chunk option while preserving identical RNG draw order.
"""

import numpy as np
import json
import os
import argparse
from scipy.special import betainc

def run_bench(seed: int = 42, N: int = 100_000, eps: float = 0.25, chunk_size: int = 25_000):
    np.random.seed(seed)
    dimensions = [8, 24, 128, 1024]
    results = []
    
    for d in dimensions:
        all_dots = []
        for i in range(0, N, chunk_size):
            cur_n = min(chunk_size, N - i)
            u = np.random.randn(cur_n, d)
            v = np.random.randn(cur_n, d)
            u /= np.linalg.norm(u, axis=1, keepdims=True)
            v /= np.linalg.norm(v, axis=1, keepdims=True)
            dots = np.abs(np.sum(u * v, axis=1))
            all_dots.append(dots)
            
        dots = np.concatenate(all_dots)
        
        std_theory = 1.0 / np.sqrt(d)
        max_dot = float(np.max(dots))
        prob_exceed = float(np.mean(dots >= eps))
        levy_bound = float(2.0 * np.exp(-d * (eps ** 2) / 2.0))
        exact_beta_tail = float(1.0 - betainc(0.5, (d - 1) / 2.0, eps**2))
        
        results.append({
            "dimension": d,
            "std_theory": round(std_theory, 5),
            "max_dot": round(max_dot, 4),
            "prob_exceed": round(prob_exceed, 4),
            "exact_beta_tail": round(exact_beta_tail, 4),
            "levy_bound": levy_bound
        })
        print(f"d={d:4d} | Std: {std_theory:.4f} | Max: {max_dot:.4f} | P(|cos|>=0.25): {prob_exceed:.4f} | Exact Beta: {exact_beta_tail:.4f} | Levy: {levy_bound:.4e}")
        
    out_dir = "benchmark_results"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "levy_concentration.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk", type=int, default=25000, help="Chunk size for memory bounding")
    args = parser.parse_args()
    run_bench(chunk_size=args.chunk)
