"""
Empirical Benchmark: Unidirectional Autoregressive Deduction vs. Bidirectional ETH-Cut Deduction.

Evaluates deductive transitivity and proof completion on long deduction chains (k in [4, 16] hops):
A -> B -> C -> D -> ... -> Target.
Measures whether meet-in-the-middle cut factorization prevents exponential reasoning decay.
"""

import math
import time
import torch
import torch.nn as nn
import torch.nn.functional as F

from imf.eth_cut_reasoning import BidirectionalCutReasoning


class DeductionChainBenchmark:
    def __init__(self, d_model: int = 64, num_hops_list = [4, 8, 12, 16]):
        self.d_model = d_model
        self.num_hops_list = num_hops_list
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def run_benchmark(self, num_trials: int = 100):
        print(f"[*] Running ETH-Cut Factorized Deduction Benchmark across k in {self.num_hops_list} on {self.device}...")

        # Unidirectional standard transformer/SSM linear step simulator
        step_op = nn.Linear(self.d_model, self.d_model, bias=False).to(self.device)
        nn.init.orthogonal_(step_op.weight)

        # Bidirectional Cut Reasoning Layer
        cut_layer = BidirectionalCutReasoning(d_model=self.d_model, num_cuts=4).to(self.device)

        print("\n" + "=" * 76)
        print(f"{'Hops (k)':<12} | {'Unidirectional Acc':<22} | {'ETH-Cut Factored Acc':<22} | {'Gain':<12}")
        print("=" * 76)

        results = {}

        for k in self.num_hops_list:
            unidir_correct = 0
            cut_correct = 0

            for _ in range(num_trials):
                # Random premise vector P and sequence of orthogonal relations R_1...R_k
                p = torch.randn(1, 1, self.d_model, device=self.device)
                p = F.normalize(p, dim=-1)

                # Ground truth target: sequential application of k steps
                current = p
                trajectory = [current]
                for _ in range(k):
                    # Noisy step evolution
                    noise = torch.randn_like(current) * 0.08
                    current = F.normalize(step_op(current) + noise, dim=-1)
                    trajectory.append(current)

                target = trajectory[-1]
                mid_point = k // 2
                true_mid = trajectory[mid_point]

                # 1. Unidirectional Forward Rollout (suffers exponential noise accumulation)
                unidir_pred = p
                for _ in range(k):
                    unidir_pred = F.normalize(step_op(unidir_pred), dim=-1)

                unidir_sim = F.cosine_similarity(unidir_pred.squeeze(), target.squeeze(), dim=-1).item()
                if unidir_sim > 0.40:
                    unidir_correct += 1

                # 2. Bidirectional Cut Rollout (Meet at middle cut k // 2)
                # Forward rollout from Premise to Mid
                fwd_mid = p
                for _ in range(mid_point):
                    fwd_mid = F.normalize(step_op(fwd_mid), dim=-1)

                # Backward rollout from Target to Mid (using adjoint / transpose)
                bwd_mid = target
                for _ in range(k - mid_point):
                    bwd_mid = F.normalize(torch.matmul(bwd_mid, step_op.weight), dim=-1)

                # Meet and factorize at cut interface
                verified_mid, _ = cut_layer(fwd_mid, bwd_mid)
                cut_sim = F.cosine_similarity(verified_mid.squeeze(), true_mid.squeeze(), dim=-1).item()
                if cut_sim > 0.40:
                    cut_correct += 1

            unidir_acc = (unidir_correct / num_trials) * 100
            cut_acc = (cut_correct / num_trials) * 100
            gain = cut_acc - unidir_acc
            results[k] = {"unidir": unidir_acc, "cut": cut_acc, "gain": gain}

            print(f"{k:<12} | {unidir_acc:<21.1f}% | {cut_acc:<21.1f}% | +{gain:<10.1f}%")

        print("=" * 76)
        return results


if __name__ == "__main__":
    bench = DeductionChainBenchmark()
    bench.run_benchmark()
