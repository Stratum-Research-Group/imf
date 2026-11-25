"""
imf/rsi_priority_replay.py
Prioritized Experience Replay (PER) for Recursive Self-Improvement (RSI) Distillation.
Samples mathematical deduction trajectories from data/rsi_experience_buffer/
weighted by deduction depth, proof complexity, and student distillation loss.
Author: Nicholas Charles Mynhardt (Stratum Research Group)
"""

import json
import heapq
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


class RSIPriorityReplayBuffer:
    """
    Proportional Prioritized Experience Replay Buffer for Mathematical RSI.
    P(i) = p_i^alpha / sum_k p_k^alpha
    Importance sampling weight: w_i = (N * P(i))^(-beta) / max_w
    """
    def __init__(self, capacity: int = 100_000, alpha: float = 0.6, beta: float = 0.4):
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta
        self.buffer: List[Dict[str, Any]] = []
        self.priorities = np.zeros(capacity, dtype=np.float32)
        self.pos = 0
        self.size = 0
        self.max_priority = 1.0

    def add(self, trajectory: Dict[str, Any], initial_priority: Optional[float] = None):
        """Adds a verified theorem deduction trajectory to the buffer."""
        p = initial_priority if initial_priority is not None else self.max_priority
        if self.size < self.capacity:
            self.buffer.append(trajectory)
            self.size += 1
        else:
            self.buffer[self.pos] = trajectory

        self.priorities[self.pos] = p
        self.pos = (self.pos + 1) % self.capacity

    def sample(self, batch_size: int) -> Tuple[List[Dict[str, Any]], np.ndarray, np.ndarray]:
        """
        Samples a batch of trajectories weighted by priority.
        Returns:
            samples: List of trajectory dicts
            indices: Array of sampled buffer indices
            weights: Normalized importance sampling weights
        """
        if self.size == 0:
            raise ValueError("Cannot sample from an empty replay buffer.")

        cur_priorities = self.priorities[:self.size]
        probs = cur_priorities ** self.alpha
        sum_probs = probs.sum()
        if sum_probs == 0:
            probs = np.ones(self.size, dtype=np.float32) / self.size
        else:
            probs = probs / sum_probs

        indices = np.random.choice(self.size, size=batch_size, p=probs, replace=(self.size < batch_size))
        samples = [self.buffer[idx] for idx in indices]

        # Importance sampling weights
        total = self.size
        weights = (total * probs[indices]) ** (-self.beta)
        weights /= (weights.max() + 1e-8)

        return samples, indices, weights.astype(np.float32)

    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray):
        """Updates priorities with new TD errors / distillation losses."""
        for idx, err in zip(indices, td_errors):
            p = float(np.abs(err) + 1e-5)
            self.priorities[idx] = p
            if p > self.max_priority:
                self.max_priority = p

    def load_from_jsonl(self, jsonl_path: Path, max_samples: int = 50_000):
        """Loads and scores trajectories from an RSI stream file."""
        if not jsonl_path.exists():
            return 0

        loaded = 0
        with open(jsonl_path, "r") as f:
            for line in f:
                if loaded >= max_samples:
                    break
                try:
                    rec = json.loads(line)
                    # Heuristic score based on proof length and family difficulty
                    code_len = len(rec.get("code", ""))
                    fam_idx = rec.get("family_idx", 0)
                    priority = 1.0 + (code_len / 200.0) + (fam_idx % 8) * 0.2
                    self.add(rec, initial_priority=priority)
                    loaded += 1
                except Exception:
                    continue
        return loaded


if __name__ == "__main__":
    buf = RSIPriorityReplayBuffer(capacity=1000)
    for i in range(100):
        buf.add({"step": i, "statement": f"theorem_{i}"}, initial_priority=float(i + 1))
    
    samples, idxs, w = buf.sample(10)
    print(f"Sampled {len(samples)} items, indices: {idxs}, min_w: {w.min():.3f}, max_w: {w.max():.3f}")
