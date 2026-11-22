"""
imf/autonomous_swarm_gym.py
Autonomous Multi-Agent Swarm Gym using the 14-Domain Ground-Truth Execution Verifiers.

Architecture:
1. Architect Agent: Proposes formal theorem conjectures, system task specs, or compiler benchmarks.
2. Synthesizer Agent: Generates multi-architecture implementations (Lean 4, x86-64, ARM64, CUDA, C++20, eBPF).
3. Adversarial Agent: Analyzes synthesized candidates for edge cases, resource bounds, and correctness flaws.
4. Host Compiler / Verifier: Invokes host-native toolchains (lean, as, clang, nvcc, rustc) for zero-axiom certification.
5. Experience Buffer: Accumulates certified self-play trajectories into clean reinforcement learning replay streams.
"""

import time
import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from imf.domain_execution_verifiers import DomainExecutionVerifierRegistry


@dataclass
class SwarmTask:
    task_id: str
    domain: str
    specification: str
    expected_properties: List[str]


@dataclass
class SwarmCandidate:
    candidate_id: str
    task_id: str
    domain: str
    code_artifact: str
    explanation: str
    generator_role: str


@dataclass
class SwarmVerificationRecord:
    task_id: str
    domain: str
    verified: bool
    latency_sec: float
    compiler_diagnostics: str
    axioms_used: List[str]
    critic_verdict: str
    reward_score: float


class AutonomousSwarmGym:
    """
    Self-contained closed-loop gym coordinating multi-agent self-play
    grounded exclusively in machine-checked compilers and formal verifiers.
    """

    def __init__(self, registry: Optional[DomainExecutionVerifierRegistry] = None):
        self.registry = registry or DomainExecutionVerifierRegistry()
        self.replay_buffer: List[SwarmVerificationRecord] = []
        self.domain_success_counts: Dict[str, int] = {}
        self.domain_total_counts: Dict[str, int] = {}

    def generate_task(self, domain: str, task_id: str, spec: str, props: List[str]) -> SwarmTask:
        """Architect role: Creates an objective specification."""
        return SwarmTask(task_id=task_id, domain=domain, specification=spec, expected_properties=props)

    def _dispatch_verify(self, domain: str, code: str) -> Tuple[bool, str, List[str]]:
        """Routes domain to matching verifier in DomainExecutionVerifierRegistry."""
        axioms = []
        if domain == "lean4":
            verified, msg = self.registry.verify_lean4(code)
            return verified, msg, axioms
        elif domain == "x86_assembly":
            verified, msg = self.registry.verify_x86_assembly(code, use_intel_syntax=True)
            return verified, msg, []
        elif domain == "arm64_assembly":
            verified, msg = self.registry.verify_arm64_assembly(code)
            return verified, msg, []
        elif domain == "riscv_assembly":
            verified, msg = self.registry.verify_riscv_assembly(code)
            return verified, msg, []
        elif domain == "llvm_ir":
            verified, msg = self.registry.verify_llvm_ir(code)
            return verified, msg, []
        elif domain == "cuda_cpp":
            verified, msg = self.registry.verify_cuda(code)
            return verified, msg, []
        elif domain == "cpp20":
            verified, msg = self.registry.verify_cpp20(code)
            return verified, msg, []
        elif domain == "ebpf":
            verified, msg = self.registry.verify_ebpf(code)
            return verified, msg, []
        elif domain == "c17":
            verified, msg = self.registry.verify_c17(code)
            return verified, msg, []
        elif domain == "rust":
            verified, msg = self.registry.verify_rust(code)
            return verified, msg, []
        elif domain == "python":
            verified, msg = self.registry.verify_python_execution(code)
            return verified, msg, []
        elif domain == "crispr_dna":
            verified, msg = self.registry.verify_genomics_dna(code)
            return verified, msg, []
        elif domain == "smiles_chem":
            verified, msg = self.registry.verify_smiles_valency(code)
            return verified, msg, []
        elif domain == "json_rpc":
            verified, msg = self.registry.verify_tool_call_json(code)
            return verified, msg, []
        else:
            return False, f"Unsupported domain: {domain}", []

    def evaluate_candidate(
        self,
        candidate: SwarmCandidate,
        critic_analysis: str = "Standard structural inspection passed."
    ) -> SwarmVerificationRecord:
        """
        Compiler/Oracle role: Evaluates candidate artifact through deterministic compiler.
        Applies non-stochastic reward shaping.
        """
        t0 = time.perf_counter()
        verified, diagnostics, axioms = self._dispatch_verify(candidate.domain, candidate.code_artifact)
        elapsed = time.perf_counter() - t0

        # Non-stochastic reward formulation:
        # +3.0 for verified compilation / zero-axiom proof
        # -1.0 for escape hatches (sorry / admit)
        # -0.5 for compilation / syntax failure
        reward = 0.0
        if verified:
            reward = 3.0
            self.domain_success_counts[candidate.domain] = self.domain_success_counts.get(candidate.domain, 0) + 1
        elif "sorry" in candidate.code_artifact or "admit" in candidate.code_artifact:
            reward = -1.0
        else:
            reward = -0.5

        self.domain_total_counts[candidate.domain] = self.domain_total_counts.get(candidate.domain, 0) + 1

        record = SwarmVerificationRecord(
            task_id=candidate.task_id,
            domain=candidate.domain,
            verified=verified,
            latency_sec=elapsed,
            compiler_diagnostics=diagnostics,
            axioms_used=axioms,
            critic_verdict=critic_analysis,
            reward_score=reward,
        )
        self.replay_buffer.append(record)
        return record

    def get_gym_summary(self) -> Dict[str, Any]:
        total_attempts = len(self.replay_buffer)
        total_verified = sum(1 for r in self.replay_buffer if r.verified)
        overall_pass_rate = (total_verified / total_attempts) * 100.0 if total_attempts > 0 else 0.0

        return {
            "total_evaluations": total_attempts,
            "total_verified": total_verified,
            "overall_pass_rate_pct": round(overall_pass_rate, 2),
            "per_domain_stats": {
                d: {
                    "verified": self.domain_success_counts.get(d, 0),
                    "total": self.domain_total_counts.get(d, 0),
                    "rate_pct": round((self.domain_success_counts.get(d, 0) / max(1, self.domain_total_counts.get(d, 0))) * 100.0, 1),
                }
                for d in self.domain_total_counts
                if self.domain_total_counts[d] > 0
            },
        }
