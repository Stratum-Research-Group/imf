#!/usr/bin/env python3
"""
scripts/bench_matryoshka_4bit_scaling.py
Measures parameter reconstruction cosine fidelity across all four PLQ regimes
(PLQ-1.58, PLQ-1.00, PLQ-0.75, PLQ-0.58) over 10,000 synthetic Gaussian 8D blocks.

Regimes evaluated:
  1. PLQ-1.58: 4-bit radial shell (16 logarithmic levels) + Conway-Sloane fast E8 nearest lattice point quantizer in R^8.
  2. PLQ-1.00: 4-bit radial shell + 240 Gosset root codebook (8-bit directional index).
  3. PLQ-0.75: 4-bit radial shell + 64 Pruned root codebook (6-bit directional index).
  4. PLQ-0.58: 4-bit radial shell + 16 Orthant sector codebook (4-bit directional index).

Includes a non-circularity test verifying that the real lattice quantizer diverges from a uniform random baseline.
"""

import numpy as np
import json
import os
import sys
import itertools

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

def generate_e8_roots_np() -> np.ndarray:
    """Constructs the canonical 240 root vectors of E8 normalized to unit hypersphere."""
    roots = []
    for idx in itertools.combinations(range(8), 2):
        for s0, s1 in [(1.0, 1.0), (1.0, -1.0), (-1.0, 1.0), (-1.0, -1.0)]:
            vec = [0.0] * 8
            vec[idx[0]] = s0
            vec[idx[1]] = s1
            roots.append(vec)
    for signs in itertools.product([0.5, -0.5], repeat=8):
        if sum(1 for s in signs if s < 0) % 2 == 0:
            roots.append(list(signs))
    R = np.array(roots)
    return R / np.linalg.norm(R, axis=-1, keepdims=True)

def run_regimes_benchmark(N_blocks: int = 10_000, seed: int = 42):
    np.random.seed(seed)
    
    r_min, r_max = 0.5, 5.0
    K = 16
    radial_levels = np.array([r_min * np.exp(k * np.log(r_max / r_min) / (K - 1)) for k in range(K)])
    
    roots_240 = generate_e8_roots_np()
    roots_64 = roots_240[:64]
    
    orthants_256 = np.array(list(itertools.product([1.0, -1.0], repeat=8)))
    orthants_256 = orthants_256 / np.linalg.norm(orthants_256, axis=-1, keepdims=True)
    orthants_16 = orthants_256[np.random.choice(256, 16, replace=False)]
    
    # Generate 10,000 synthetic Gaussian 8D blocks
    raw_blocks = [np.random.randn(8) for _ in range(N_blocks)]
    blocks = [w for w in raw_blocks if np.linalg.norm(w) > 0]
    
    regimes = {
        "PLQ-1.58": {"cosines": [], "rel_errs": []},
        "PLQ-1.00": {"cosines": [], "rel_errs": []},
        "PLQ-0.75": {"cosines": [], "rel_errs": []},
        "PLQ-0.58": {"cosines": [], "rel_errs": []},
    }
    
    for w in blocks:
        norm = np.linalg.norm(w)
        best_k = np.argmin(np.abs(radial_levels - norm))
        r_hat = radial_levels[best_k]
        u = w / norm
        
        # 1. PLQ-1.58: Conway-Sloane E8 lattice
        x = w / (norm / 4.0)
        q = closest_e8(x)
        qn = np.linalg.norm(q)
        u_hat_158 = q / qn if qn > 0 else u
        w_hat_158 = r_hat * u_hat_158
        c158 = float(np.dot(w, w_hat_158) / (norm * np.linalg.norm(w_hat_158)))
        regimes["PLQ-1.58"]["cosines"].append(c158)
        regimes["PLQ-1.58"]["rel_errs"].append(float(np.linalg.norm(w - w_hat_158) / norm))
        
        # 2. PLQ-1.00: 240 Gosset roots
        u_hat_100 = roots_240[np.argmax(roots_240 @ u)]
        w_hat_100 = r_hat * u_hat_100
        c100 = float(np.dot(w, w_hat_100) / (norm * np.linalg.norm(w_hat_100)))
        regimes["PLQ-1.00"]["cosines"].append(c100)
        regimes["PLQ-1.00"]["rel_errs"].append(float(np.linalg.norm(w - w_hat_100) / norm))
        
        # 3. PLQ-0.75: 64 Pruned roots
        u_hat_075 = roots_64[np.argmax(roots_64 @ u)]
        w_hat_075 = r_hat * u_hat_075
        c075 = float(np.dot(w, w_hat_075) / (norm * np.linalg.norm(w_hat_075)))
        regimes["PLQ-0.75"]["cosines"].append(c075)
        regimes["PLQ-0.75"]["rel_errs"].append(float(np.linalg.norm(w - w_hat_075) / norm))
        
        # 4. PLQ-0.58: 16 Orthant sectors
        u_hat_058 = orthants_16[np.argmax(orthants_16 @ u)]
        w_hat_058 = r_hat * u_hat_058
        c058 = float(np.dot(w, w_hat_058) / (norm * np.linalg.norm(w_hat_058)))
        regimes["PLQ-0.58"]["cosines"].append(c058)
        regimes["PLQ-0.58"]["rel_errs"].append(float(np.linalg.norm(w - w_hat_058) / norm))
        
    summary = {}
    for name, data in regimes.items():
        cos_arr = np.array(data["cosines"])
        rel_arr = np.array(data["rel_errs"])
        summary[name] = {
            "mean_cosine_fidelity": round(float(np.mean(cos_arr)), 5),
            "min_cosine_fidelity": round(float(np.min(cos_arr)), 5),
            "p1_cosine_fidelity": round(float(np.percentile(cos_arr, 1)), 5),
            "pct_gte_99_8": round(float(np.mean(cos_arr >= 0.998) * 100), 2),
            "mean_relative_norm_error": round(float(np.mean(rel_arr)), 5)
        }
        
    out = {
        "N_blocks": len(blocks),
        "seed": seed,
        "status": "measured, synthetic Gaussian blocks with Conway-Sloane E8 lattice quantizer across 4 PLQ regimes",
        "regimes": summary,
        # Backward compatibility fields for single-regime queries
        "mean_cosine_fidelity": summary["PLQ-1.58"]["mean_cosine_fidelity"],
        "min_cosine_fidelity": summary["PLQ-1.58"]["min_cosine_fidelity"],
        "p1_cosine_fidelity": summary["PLQ-1.58"]["p1_cosine_fidelity"],
        "pct_gte_99_8": summary["PLQ-1.58"]["pct_gte_99_8"],
        "mean_relative_norm_error": summary["PLQ-1.58"]["mean_relative_norm_error"]
    }
    return out

def main():
    # Non-circularity test
    test_res = run_regimes_benchmark(1000, 42)
    c158 = test_res["regimes"]["PLQ-1.58"]["mean_cosine_fidelity"]
    
    # Uniform random baseline
    np.random.seed(42)
    rand_cos = []
    for _ in range(1000):
        w = np.random.randn(8)
        r = np.random.randn(8)
        rand_cos.append(np.dot(w, r) / (np.linalg.norm(w) * np.linalg.norm(r)))
    rand_mean = float(np.mean(rand_cos))
    
    delta = abs(c158 - rand_mean)
    if delta < 0.5:
        print(f"[-] ERROR: Non-circularity test failed: delta={delta}")
        sys.exit(1)
    print(f"[✓] Non-circularity test passed: real {c158} vs random {rand_mean:.4f} (delta={delta:.4f})")
    
    # Run full 10,000 blocks benchmark
    results = run_regimes_benchmark(10_000, 42)
    
    out_dir = "benchmark_results"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "matryoshka_4bit_scaling.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
        
    print(f"[+] Full 4-regime benchmark written to {out_path}:")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
