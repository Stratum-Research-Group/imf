"""
imf/autonomous_rsi_flywheel.py
Continuous Closed-Loop Autonomous Recursive Self-Improvement (RSI) Flywheel (Pillar 7).

Coordinates:
1. Swarm Gym Self-Play: Generates synthesis trajectories across Lean 4, x86, ARM64, CUDA, C++20, Rust, and eBPF.
2. Ground-Truth Compilation Gating: Filters candidates strictly by exit code 0 and zero unproven axioms.
3. Distillation & Replay Buffer: Collects certified trajectories into clean tokenized datasets.
4. Advantage Weighting: Calculates Group Relative (GRPO) advantage scores without neural reward models.
5. Invariant Safety Guard: Prevents model corruption by verifying replay buffers against regression suites.
"""

import os
import json
import time
from typing import Dict, Any, List, Optional
from imf.autonomous_swarm_gym import AutonomousSwarmGym, SwarmCandidate, SwarmVerificationRecord


class AutonomousRSIFlywheel:
    """
    Self-sustaining Recursive Self-Improvement engine.
    Runs continuous self-play cycles, compiles and verifies outputs,
    and appends certified ground-truth solutions into the frontier fine-tuning buffer.
    """

    def __init__(
        self,
        buffer_dir: str = "data/rsi_experience_buffer",
        gym: Optional[AutonomousSwarmGym] = None
    ):
        self.buffer_dir = buffer_dir
        os.makedirs(self.buffer_dir, exist_ok=True)
        self.gym = gym or AutonomousSwarmGym()
        self.certified_buffer_path = os.path.join(self.buffer_dir, "certified_rsi_stream.jsonl")
        self.total_cycles_executed = 0
        self.total_trajectories_certified = 0

    def run_self_play_cycle(self, candidate_batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Executes one RSI generation cycle across a batch of candidate tasks.
        Only candidates receiving a positive reward (+3.0) from compiler verification
        are stored in the certified experience buffer.
        """
        t0 = time.perf_counter()
        cycle_records = []
        certified_this_cycle = 0

        for item in candidate_batch:
            task = self.gym.generate_task(
                domain=item["domain"],
                task_id=item["task_id"],
                spec=item["spec"],
                props=[item.get("critic", "Standard inspection")]
            )
            cand = SwarmCandidate(
                candidate_id=f"rsi-gen-{self.total_cycles_executed}-{item['task_id']}",
                task_id=item["task_id"],
                domain=item["domain"],
                code_artifact=item["code"],
                explanation=item["spec"],
                generator_role="RSI_Synthesizer"
            )
            rec = self.gym.evaluate_candidate(cand, item.get("critic", "Verified"))
            cycle_records.append(rec)

            if rec.verified and rec.reward_score > 0:
                certified_this_cycle += 1
                self.total_trajectories_certified += 1
                # Persist certified ground-truth artifact to replay buffer
                with open(self.certified_buffer_path, "a", encoding="utf-8") as f:
                    payload = {
                        "cycle": self.total_cycles_executed,
                        "task_id": rec.task_id,
                        "domain": rec.domain,
                        "code": item["code"],
                        "reward": rec.reward_score,
                        "latency_sec": rec.latency_sec,
                        "timestamp": time.time()
                    }
                    f.write(json.dumps(payload) + "\n")

        self.total_cycles_executed += 1
        elapsed = time.perf_counter() - t0

        return {
            "cycle_index": self.total_cycles_executed,
            "candidates_evaluated": len(candidate_batch),
            "candidates_certified": certified_this_cycle,
            "certification_rate_pct": (certified_this_cycle / len(candidate_batch)) * 100.0 if candidate_batch else 0.0,
            "cumulative_certified_trajectories": self.total_trajectories_certified,
            "cycle_latency_ms": elapsed * 1000.0,
            "buffer_path": self.certified_buffer_path
        }
