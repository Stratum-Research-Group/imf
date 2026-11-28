#!/usr/bin/env python3
"""
scripts/bench_damping_ceiling_multiseed.py
Simulates recurrent state Frobenius norm evolution under rank-1 outer-product updates across 10 random seeds:
    M_{t+1} = (1 - eta) * U * M_t * U^T + v_t * k_t^T
where ||v_t||_2 = ||k_t||_2 = 1.0 (unit-norm random vectors on S^31).
Reports mean, min, and max across seeds for:
    eta in [0.0, 0.01, 0.05, 0.10] across horizons T in [0, 100, 1000, 10000, 100000].
"""

import numpy as np
import json
import os

def run_multiseed(seeds=range(42, 52), max_T=100_000):
    d = 32
    etas = [0.0, 0.01, 0.05, 0.10]
    horizons = [0, 100, 1_000, 10_000, 100_000]
    
    # Store runs: eta -> horizon -> list of values
    raw_data = {str(eta): {h: [] for h in horizons} for eta in etas}
    
    for seed in seeds:
        np.random.seed(seed)
        X = np.random.randn(d, d)
        A = (X - X.T) / np.sqrt(2 * d)
        I = np.eye(d)
        U = np.linalg.solve(I - 0.5 * A, I + 0.5 * A)
        
        M0_raw = np.random.randn(d, d)
        M0 = 4.40 * (M0_raw / np.linalg.norm(M0_raw, 'fro'))
        
        for eta in etas:
            M = M0.copy()
            raw_data[str(eta)][0].append(4.40)
            
            for t in range(1, max_T + 1):
                v = np.random.randn(d)
                v /= np.linalg.norm(v)
                k = np.random.randn(d)
                k /= np.linalg.norm(k)
                innovation = np.outer(v, k)
                
                M = (1.0 - eta) * (U @ M @ U.T) + innovation
                
                if t in horizons:
                    raw_data[str(eta)][t].append(float(np.linalg.norm(M, 'fro')))
                    
    stats = {}
    for eta_str in raw_data:
        stats[eta_str] = {}
        for h in horizons:
            vals = raw_data[eta_str][h]
            stats[eta_str][h] = {
                "mean": round(float(np.mean(vals)), 2),
                "min": round(float(np.min(vals)), 2),
                "max": round(float(np.max(vals)), 2)
            }
            
    out_dir = "benchmark_results"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "damping_ceiling_multiseed.json")
    with open(out_path, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"[+] Multi-seed results saved to {out_path}")
    print(json.dumps(stats, indent=2))
    return stats

if __name__ == "__main__":
    run_multiseed()
