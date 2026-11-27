"""
scripts/bench_lie_capacity.py
Associative memory capacity benchmark for Lie Rolling KV Cache (d=32).
Measures empirical retrieval accuracy across token horizons N.
"""
import json
import os
import numpy as np

def benchmark_capacity():
    d = 32
    results = {}
    horizons = [2, 4, 8, 16, 32, 64, 128]
    trials = 100

    for N in horizons:
        recalls = []
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

            correct = 0
            for i in range(N):
                pred_v = M @ keys[i]
                sims = [np.dot(pred_v, vals[j]) / (np.linalg.norm(pred_v) * np.linalg.norm(vals[j]) + 1e-9) for j in range(N)]
                if np.argmax(sims) == i:
                    correct += 1
            recalls.append(correct / N)

        results[N] = {
            "mean_accuracy": float(np.mean(recalls)),
            "std_accuracy": float(np.std(recalls))
        }

    out_path = os.path.join("benchmark_results", "lie_capacity.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Benchmark written to {out_path}")
    return results

if __name__ == "__main__":
    benchmark_capacity()
