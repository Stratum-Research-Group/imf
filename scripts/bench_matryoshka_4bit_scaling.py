#!/usr/bin/env python3
"""
scripts/bench_matryoshka_4bit_scaling.py
Measures parameter reconstruction cosine fidelity and relative error for 8-dimensional blocks
under:
  (a) 16 logarithmic radial energy levels r_k = r0 * exp(k * delta_rho)
  (b) Conway-Sloane fast E8 nearest lattice point quantizer in R^8
  (c) Reconstructed w_hat = r_hat * u_hat
Compares real lattice quantizer against uniform random direction baseline across 10,000 blocks.
"""

import numpy as np
import json
import os
import sys

def closest_d8(x: np.ndarray) -> np.ndarray:
    """Finds nearest point in D8 checkerboard lattice using Conway-Sloane (1982) O(d) algorithm."""
    f = np.round(x)
    diff = np.abs(x - f)
    s = int(np.sum(f)) % 2
    if s != 0:
        worst = np.argmax(diff)
        if x[worst] >= f[worst]:
            f[worst] += 1
        else:
            f[worst] -= 1
    return f

def closest_e8(x: np.ndarray) -> np.ndarray:
    """Finds nearest point in E8 lattice: E8 = D8 U (D8 + 1/2*1)."""
    p0 = closest_d8(x)
    p1 = closest_d8(x - 0.5) + 0.5
    if np.sum((x - p0)**2) <= np.sum((x - p1)**2):
        return p0
    else:
        return p1

def run_matryoshka_benchmark(N_blocks: int = 10_000, seed: int = 42, use_random: bool = False):
    np.random.seed(seed)
    
    r_min, r_max = 0.5, 5.0
    K = 16
    radial_levels = np.array([r_min * np.exp(k * np.log(r_max / r_min) / (K - 1)) for k in range(K)])
    
    cosines = []
    rel_errs = []
    
    for _ in range(N_blocks):
        w = np.random.randn(8)
        norm = np.linalg.norm(w)
        if norm == 0:
            continue
            
        # 1. Nearest radial shell
        best_k = np.argmin(np.abs(radial_levels - norm))
        r_hat = radial_levels[best_k]
        
        # 2. Directional quantizer
        if use_random:
            rand_vec = np.random.randn(8)
            u_hat = rand_vec / np.linalg.norm(rand_vec)
        else:
            # Scale target vector to intermediate lattice density
            x = w / (norm / 4.0)
            q = closest_e8(x)
            q_norm = np.linalg.norm(q)
            if q_norm > 0:
                u_hat = q / q_norm
            else:
                u_hat = w / norm
                
        # 3. Reconstruct
        w_hat = r_hat * u_hat
        cos_sim = float(np.dot(w, w_hat) / (norm * np.linalg.norm(w_hat)))
        rel_err = float(np.linalg.norm(w - w_hat) / norm)
        
        cosines.append(cos_sim)
        rel_errs.append(rel_err)
        
    cos_arr = np.array(cosines)
    rel_arr = np.array(rel_errs)
    
    return {
        "N_blocks": N_blocks,
        "mean_cosine_fidelity": round(float(np.mean(cos_arr)), 5),
        "min_cosine_fidelity": round(float(np.min(cos_arr)), 5),
        "p1_cosine_fidelity": round(float(np.percentile(cos_arr, 1)), 5),
        "pct_gte_99_8": round(float(np.mean(cos_arr >= 0.998) * 100), 2),
        "mean_relative_norm_error": round(float(np.mean(rel_arr)), 5),
        "status": "measured, synthetic Gaussian blocks with Conway-Sloane E8 lattice quantizer"
    }

def main():
    # Enforce non-circularity test: real quantizer must diverge from random
    real_test = run_matryoshka_benchmark(1000, 42, use_random=False)
    rand_test = run_matryoshka_benchmark(1000, 42, use_random=True)
    
    delta = abs(real_test["mean_cosine_fidelity"] - rand_test["mean_cosine_fidelity"])
    if delta < 0.5:
        print(f"[-] ERROR: Non-circularity test failed: delta={delta}")
        sys.exit(1)
    print(f"[✓] Non-circularity test passed: real {real_test['mean_cosine_fidelity']} vs random {rand_test['mean_cosine_fidelity']} (delta={delta:.4f})")
    
    # Full benchmark
    results = run_matryoshka_benchmark(10_000, 42, use_random=False)
    
    out_dir = "benchmark_results"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "matryoshka_4bit_scaling.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[+] Benchmark written to {out_path}:")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
