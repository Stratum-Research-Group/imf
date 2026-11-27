"""
scripts/bench_lie_capacity.py
Associative memory capacity benchmark for Lie Rolling KV Cache (d=32).
Measures both raw un-rotated query accuracy and position-aware relative rotation readout accuracy.
"""
import json
import os
import numpy as np

def benchmark_capacity():
    np.random.seed(42)
    d = 32
    results = {}
    horizons = [2, 4, 8, 16, 32, 64, 128]
    trials = 100

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

                # 1. Raw readout: query with un-rotated k_i
                pred_raw = M @ keys[i]
                sims_raw = [np.dot(pred_raw, vals[j]) for j in range(N)]
                if np.argmax(sims_raw) == i:
                    correct_raw += 1

                # 2. Position-aware readout: query with rotated key Um @ k_i, un-rotate with Um^T
                pred_pos = Um.T @ (M @ (Um @ keys[i]))
                sims_pos = [np.dot(pred_pos, vals[j]) for j in range(N)]
                if np.argmax(sims_pos) == i:
                    correct_pos += 1

            recalls_raw.append(correct_raw / N)
            recalls_pos.append(correct_pos / N)

        results[N] = {
            "raw_readout_accuracy": float(np.mean(recalls_raw)),
            "position_aware_accuracy": float(np.mean(recalls_pos))
        }

    out_path = os.path.join("benchmark_results", "lie_capacity.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Benchmark written to {out_path}")
    return results

if __name__ == "__main__":
    benchmark_capacity()
