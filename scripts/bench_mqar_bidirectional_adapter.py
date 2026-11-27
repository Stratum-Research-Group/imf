"""
scripts/bench_mqar_bidirectional_adapter.py
Evaluates multi-query associative recall (MQAR) using a hybrid dual-readout adapter:
Combines symmetric state M^(S) (associative memory) with antisymmetric sector M^(A) (directionality).
Measures forward, retrograde (reverse), and bidirectional accuracy.
"""
import json
import os
import torch
import numpy as np

def run_bidirectional_mqar_benchmark():
    d = 32
    num_pairs = 8
    num_trials = 100
    results = {}

    forward_correct = 0
    reverse_correct = 0
    bidirectional_correct = 0

    for _ in range(num_trials):
        keys = torch.randn(num_pairs, d, dtype=torch.float64)
        keys = keys / torch.norm(keys, dim=-1, keepdim=True)
        vals = torch.randn(num_pairs, d, dtype=torch.float64)
        vals = vals / torch.norm(vals, dim=-1, keepdim=True)

        # SAVG Split Memory:
        # Symmetric sector M_S = sum (v k^T + k v^T)
        # Antisymmetric sector M_A = sum (v k^T - k v^T)
        M_S = torch.zeros(d, d, dtype=torch.float64)
        M_A = torch.zeros(d, d, dtype=torch.float64)

        for i in range(num_pairs):
            W_sym = torch.outer(vals[i], keys[i]) + torch.outer(keys[i], vals[i])
            W_anti = torch.outer(vals[i], keys[i]) - torch.outer(keys[i], vals[i])
            M_S = 0.98 * M_S + W_sym
            M_A = 0.98 * M_A + W_anti

        # Forward query: given k_i, predict v_i
        # Readout: M_fwd = 0.5 * (M_S + M_A) = outer(v, k)
        q_idx = np.random.randint(0, num_pairs)
        q_k = keys[q_idx]
        M_fwd = 0.5 * (M_S + M_A)
        pred_fwd = M_fwd @ q_k
        sims_fwd = [torch.dot(pred_fwd, vals[j]).item() for j in range(num_pairs)]
        if np.argmax(sims_fwd) == q_idx:
            forward_correct += 1

        # Reverse query: given v_i, predict k_i (Retrograde factual query)
        # Readout: M_rev = 0.5 * (M_S - M_A) = outer(k, v)
        q_v = vals[q_idx]
        M_rev = 0.5 * (M_S - M_A)
        pred_rev = M_rev @ q_v
        sims_rev = [torch.dot(pred_rev, keys[j]).item() for j in range(num_pairs)]
        if np.argmax(sims_rev) == q_idx:
            reverse_correct += 1

        if (np.argmax(sims_fwd) == q_idx) and (np.argmax(sims_rev) == q_idx):
            bidirectional_correct += 1

    results = {
        "num_pairs": num_pairs,
        "num_trials": num_trials,
        "forward_recall_accuracy": forward_correct / num_trials,
        "retrograde_reverse_recall_accuracy": reverse_correct / num_trials,
        "bidirectional_joint_accuracy": bidirectional_correct / num_trials,
        "architecture": "SAVG Dual-Sector Readout (0.5 * (M_S +- M_A))",
        "evaluation_type": "DUAL_READOUT_OUTER_PRODUCT_SYNTHETIC_CHECK"
    }

    out_file = os.path.join("benchmark_results", "mqar_bidirectional_adapter.json")
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Bidirectional MQAR results written to {out_file}: Forward {forward_correct}%, Reverse {reverse_correct}%")
    return results

if __name__ == "__main__":
    run_bidirectional_mqar_benchmark()
