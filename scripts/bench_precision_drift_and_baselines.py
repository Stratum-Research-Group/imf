"""
scripts/bench_precision_drift_and_baselines.py
Evaluates:
1. Low-precision (FP32, FP16, BF16) isometry drift over 1,000 steps across 20 pseudo-random seeds.
   Computes median, min, max, and writes consolidated results to benchmark_results/precision_drift_multiseed.json
   and benchmark_results/precision_and_mqar.json.
2. Synthetic recall check against baseline linear memory formulations.
"""
import json
import os
import torch
import numpy as np

def run_precision_and_mqar_evaluation(num_seeds=20, T=1000, d=32):
    results = {}

    # -------------------------------------------------------------
    # 1. Multi-Seed Precision Drift Audit (20 Seeds)
    # -------------------------------------------------------------
    precisions = ["float32", "float16", "bfloat16"]
    seed_drifts = {p: [] for p in precisions}

    for seed in range(num_seeds):
        torch.manual_seed(seed)
        np.random.seed(seed)

        # Skew generator A in float64
        A = torch.randn(d, d, dtype=torch.float64)
        A = 0.5 * (A - A.T)
        I = torch.eye(d, dtype=torch.float64)
        U_fp64 = torch.linalg.solve(I - 0.5 * A, I + 0.5 * A)

        # Baseline initial random state M0 in float64
        M0_f64 = torch.randn(d, d, dtype=torch.float64)
        M0_f64 = 0.5 * (M0_f64 - M0_f64.T)
        norm0 = torch.linalg.norm(M0_f64, 'fro').item()

        for prec_name in precisions:
            dtype = getattr(torch, prec_name)
            U = U_fp64.to(dtype)
            M_curr = M0_f64.to(dtype)

            for _ in range(T):
                M_curr = U @ M_curr @ U.T

            norm_final = torch.linalg.norm(M_curr.to(torch.float64), 'fro').item()
            rel_drift = abs(norm_final - norm0) / norm0
            seed_drifts[prec_name].append(rel_drift)

    multiseed_summary = {
        "num_seeds": num_seeds,
        "steps": T,
        "fp32_median": float(np.median(seed_drifts["float32"])),
        "fp32_min": float(np.min(seed_drifts["float32"])),
        "fp32_max": float(np.max(seed_drifts["float32"])),
        "fp16_median": float(np.median(seed_drifts["float16"])),
        "fp16_min": float(np.min(seed_drifts["float16"])),
        "fp16_max": float(np.max(seed_drifts["float16"])),
        "bf16_median": float(np.median(seed_drifts["bfloat16"])),
        "bf16_min": float(np.min(seed_drifts["bfloat16"])),
        "bf16_max": float(np.max(seed_drifts["bfloat16"])),
    }

    os.makedirs("benchmark_results", exist_ok=True)
    multiseed_file = os.path.join("benchmark_results", "precision_drift_multiseed.json")
    with open(multiseed_file, "w") as f:
        json.dump(multiseed_summary, f, indent=2)
    print(f"Multi-seed precision summary written to {multiseed_file}")

    results["precision_drift_multiseed"] = multiseed_summary

    # -------------------------------------------------------------
    # 2. Synthetic Recall Check (N=8 Pairs, d=32)
    # -------------------------------------------------------------
    num_pairs = 8
    num_trials = 100

    imf_correct = 0
    mamba_correct = 0
    transformer_correct = 0

    torch.manual_seed(42)
    np.random.seed(42)

    for _ in range(num_trials):
        keys = torch.randn(num_pairs, d, dtype=torch.float64)
        keys = keys / torch.norm(keys, dim=-1, keepdim=True)
        vals = torch.randn(num_pairs, d, dtype=torch.float64)
        vals = vals / torch.norm(vals, dim=-1, keepdim=True)

        # IMF Lie rolling accumulation
        M = torch.zeros(d, d, dtype=torch.float64)
        A = torch.randn(d, d, dtype=torch.float64)
        A = 0.5 * (A - A.T)
        U = torch.linalg.solve(torch.eye(d, dtype=torch.float64) - 0.5 * A, torch.eye(d, dtype=torch.float64) + 0.5 * A)

        for i in range(num_pairs):
            W = torch.outer(vals[i], keys[i]) - torch.outer(keys[i], vals[i])
            M = U @ M @ U.T + W

        q_idx = np.random.randint(0, num_pairs)
        query = keys[q_idx]

        # IMF raw prediction
        pred_imf = M @ query
        sims_imf = [torch.dot(pred_imf, vals[j]).item() for j in range(num_pairs)]
        if np.argmax(sims_imf) == q_idx:
            imf_correct += 1

        # Mamba-2 SSM (Linear State outer-product with decay)
        S = torch.zeros(d, d, dtype=torch.float64)
        decay = 0.98
        for i in range(num_pairs):
            S = decay * S + torch.outer(vals[i], keys[i])
        pred_mamba = S @ query
        sims_mamba = [torch.dot(pred_mamba, vals[j]).item() for j in range(num_pairs)]
        if np.argmax(sims_mamba) == q_idx:
            mamba_correct += 1

        # Transformer (Softmax Attention over all keys)
        scores = torch.softmax(torch.matmul(keys, query) * 5.0, dim=0)
        pred_trans = torch.sum(scores.unsqueeze(-1) * vals, dim=0)
        sims_trans = [torch.dot(pred_trans, vals[j]).item() for j in range(num_pairs)]
        if np.argmax(sims_trans) == q_idx:
            transformer_correct += 1

    results["synthetic_recall_check"] = {
        "num_trials": num_trials,
        "num_pairs": num_pairs,
        "transformer_dense_accuracy": transformer_correct / num_trials,
        "mamba2_linear_accuracy": mamba_correct / num_trials,
        "imf_lie_accuracy": imf_correct / num_trials,
        "note": "Synthetic exact unit-vector lookups without distractors; not trained checkpoints."
    }

    out_file = os.path.join("benchmark_results", "precision_and_mqar.json")
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Benchmark results written to {out_file}")
    return results

if __name__ == "__main__":
    run_precision_and_mqar_evaluation()
