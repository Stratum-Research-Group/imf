#!/usr/bin/env python3
"""
scripts/bench_lie_capacity_multiseed.py
Associative memory capacity benchmark for Lie Rolling KV Cache (d=32) over 10 random seeds (42-51).
Measures both raw un-rotated query accuracy and position-aware relative rotation readout accuracy.
"""
import json
import os
import numpy as np

def benchmark_capacity_multiseed():
    d = 32
    horizons = [2, 4, 8, 16, 32, 64, 128]
    trials = 100
    seeds = range(42, 52)
    
    seed_data = {N: {'raw': [], 'pos': []} for N in horizons}
    
    for seed in seeds:
        np.random.seed(seed)
        for N in horizons:
            recalls_raw = []
            recalls_pos = []
            for _ in range(trials):
                A = np.random.randn(d, d)
                A = 0.5 * (A - A.T)
                U = np.linalg.solve(np.eye(d) - 0.5 * A, np.eye(d) + 0.5 * A)

                keys = np.random.randn(N, d)
                keys /= np.linalg.norm(keys, axis=-1, keepdims=True)
                vals = np.random.randn(N, d)
                vals /= np.linalg.norm(vals, axis=-1, keepdims=True)

                M = np.zeros((d, d))
                for i in range(N):
                    k = keys[i]
                    v = vals[i]
                    W = np.outer(v, k) - np.outer(k, v)
                    M = U @ M @ U.T + W

                correct_raw = 0
                correct_pos = 0
                for i in range(N):
                    m = N - 1 - i
                    Um = np.linalg.matrix_power(U, m)

                    pred_raw = M @ keys[i]
                    sims_raw = [np.dot(pred_raw, vals[j]) for j in range(N)]
                    if np.argmax(sims_raw) == i:
                        correct_raw += 1

                    pred_pos = Um.T @ (M @ (Um @ keys[i]))
                    sims_pos = [np.dot(pred_pos, vals[j]) for j in range(N)]
                    if np.argmax(sims_pos) == i:
                        correct_pos += 1

                recalls_raw.append(correct_raw / N)
                recalls_pos.append(correct_pos / N)
                
            seed_data[N]['raw'].append(float(np.mean(recalls_raw)))
            seed_data[N]['pos'].append(float(np.mean(recalls_pos)))
            
    summary = {}
    for N in horizons:
        raw_arr = np.array(seed_data[N]['raw'])
        pos_arr = np.array(seed_data[N]['pos'])
        summary[str(N)] = {
            'raw_mean': round(float(np.mean(raw_arr)), 4),
            'raw_min': round(float(np.min(raw_arr)), 4),
            'raw_max': round(float(np.max(raw_arr)), 4),
            'pos_mean': round(float(np.mean(pos_arr)), 4),
            'pos_min': round(float(np.min(pos_arr)), 4),
            'pos_max': round(float(np.max(pos_arr)), 4),
        }
        
    out = {
        'num_seeds': len(seeds),
        'trials_per_seed': trials,
        'dimension': d,
        'summary': summary
    }
    
    out_dir = "benchmark_results"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "lie_capacity_multiseed.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Benchmark written to {out_path}")
    return out

if __name__ == "__main__":
    benchmark_capacity_multiseed()
