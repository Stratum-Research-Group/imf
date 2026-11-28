#!/usr/bin/env python3
"""
scripts/bench_damping_ceiling_evolution.py
Simulates recurrent state Frobenius norm evolution under rank-1 outer-product updates:
    M_{t+1} = (1 - eta) * U * M_t * U^T + v_t * k_t^T
where ||v_t||_2 = ||k_t||_2 = 1.0 (unit-norm random vectors on S^31),
contrasting undamped random-walk growth (~sqrt(T)) against the contractive ceiling B_v*B_k / eta.
"""

import numpy as np
import json
import os

def run_simulation(seed: int = 42, max_T: int = 100_000):
    np.random.seed(seed)
    d = 32
    # Skew-symmetric random generator A in so(32)
    X = np.random.randn(d, d)
    A = (X - X.T) / np.sqrt(2 * d)
    # Cayley transform U = (I - A/2)^{-1} (I + A/2)
    I = np.eye(d)
    U = np.linalg.solve(I - 0.5 * A, I + 0.5 * A)
    
    # Initial state M0 with ||M0||_F = 4.40
    M0_raw = np.random.randn(d, d)
    M0 = 4.40 * (M0_raw / np.linalg.norm(M0_raw, 'fro'))
    
    etas = [0.0, 0.01, 0.05, 0.10]
    horizons = [0, 100, 1_000, 10_000, 100_000]
    
    results = {str(eta): {} for eta in etas}
    
    for eta in etas:
        M = M0.copy()
        results[str(eta)][0] = round(float(np.linalg.norm(M, 'fro')), 2)
        
        # Pre-generate or iteratively apply unit-norm v_t, k_t
        for t in range(1, max_T + 1):
            v = np.random.randn(d)
            v /= np.linalg.norm(v)
            k = np.random.randn(d)
            k /= np.linalg.norm(k)
            innovation = np.outer(v, k)
            
            # Recurrence with damping
            M = (1.0 - eta) * (U @ M @ U.T) + innovation
            
            if t in horizons:
                results[str(eta)][t] = round(float(np.linalg.norm(M, 'fro')), 2)
                
    return results

if __name__ == "__main__":
    res = run_simulation()
    out_dir = "benchmark_results"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "damping_ceiling_evolution.json")
    with open(out_path, "w") as f:
        json.dump(res, f, indent=2)
    print(f"Results written to {out_path}:")
    print(json.dumps(res, indent=2))
