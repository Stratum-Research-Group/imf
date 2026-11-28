#!/usr/bin/env python3
"""
scripts/bench_levy_concentration.py
Measures equatorial inner-product concentration of independent uniform unit vectors on S^{d-1}
across N=100,000 trials, and computes exact analytical Lévy upper bounds 2*exp(-d*eps^2/2).
"""

import numpy as np
import json
import os

def run_bench(seed: int = 42, N: int = 100_000, eps: float = 0.25):
    np.random.seed(seed)
    dimensions = [8, 24, 128, 1024]
    results = []
    
    for d in dimensions:
        u = np.random.randn(N, d)
        v = np.random.randn(N, d)
        u /= np.linalg.norm(u, axis=1, keepdims=True)
        v /= np.linalg.norm(v, axis=1, keepdims=True)
        
        dots = np.abs(np.sum(u * v, axis=1))
        
        std_theory = 1.0 / np.sqrt(d)
        max_dot = float(np.max(dots))
        prob_exceed = float(np.mean(dots >= eps))
        levy_bound = float(2.0 * np.exp(-d * (eps ** 2) / 2.0))
        
        results.append({
            "dimension": d,
            "std_theory": round(std_theory, 5),
            "max_dot": round(max_dot, 4),
            "prob_exceed": round(prob_exceed, 4),
            "levy_bound": levy_bound
        })
        print(f"d={d:4d} | Std: {std_theory:.4f} | Max: {max_dot:.4f} | P(|cos|>=0.25): {prob_exceed:.4f} | Levy: {levy_bound:.4e}")
        
    out_dir = "benchmark_results"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "levy_concentration.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    return results

if __name__ == "__main__":
    run_bench()
